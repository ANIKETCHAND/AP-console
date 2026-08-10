"""
Video forensic analysis.

Strategy: sample N evenly-spaced frames, run the image-forensics pipeline on
each, then add two temporal signals that are specific to video:

  1. Blink-rate irregularity
     Real humans blink every ~2.5-7s (12-20/min). Early face-swap/reenactment
     models under- or over-produce blinks because blinking wasn't well
     represented in training data (Li, Chang & Lyu, 2018, "In Ictu Oculi").
     We approximate blink state per sampled frame using Haar eye-cascade
     presence/absence as a coarse proxy.

  2. Temporal texture inconsistency
     Frame-to-frame differencing inside the face bounding box should evolve
     smoothly for real video. Frame-blended/re-rendered faces often show
     jittery, non-smooth residuals.
"""

import cv2
import numpy as np

from .image_detector import analyze_image, detect_faces, EYE_CASCADE, _to_gray

MAX_SAMPLED_FRAMES = 24


def _sample_frames(path, max_frames=MAX_SAMPLED_FRAMES):
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    if total <= 0:
        frames = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
        cap.release()
        return frames[:max_frames], fps

    idxs = np.linspace(0, total - 1, min(max_frames, total)).astype(int)
    frames = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, frame = cap.read()
        if ok:
            frames.append(frame)
    cap.release()
    return frames, fps


def _eyes_open_in_frame(frame, face_box):
    if EYE_CASCADE is None or not hasattr(EYE_CASCADE, "detectMultiScale") or getattr(EYE_CASCADE, "empty", lambda: True)():
        return None
    x, y, w, h = face_box
    upper_face = frame[y:y + int(h * 0.6), x:x + w]
    if upper_face.size == 0:
        return None
    try:
        gray = _to_gray(upper_face)
        eyes = EYE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(15, 15))
        return len(eyes) >= 2
    except Exception:
        return None


def blink_rate_score(frames, fps):
    """Returns 0-100 anomaly score plus estimated blinks/min."""
    states = []
    for frame in frames:
        faces = detect_faces(frame)
        if not faces:
            states.append(None)
            continue
        biggest = max(faces, key=lambda f: f[2] * f[3])
        states.append(_eyes_open_in_frame(frame, biggest))

    valid = [s for s in states if s is not None]
    if len(valid) < 4:
        return 0.0, None

    transitions = 0
    for a, b in zip(valid, valid[1:]):
        if a and not b:
            transitions += 1

    duration_s = max(len(frames) / max(fps, 1), 1)
    blinks_per_min = transitions * (60 / duration_s)

    natural_low, natural_high = 8, 25
    if blinks_per_min < natural_low:
        dev = (natural_low - blinks_per_min) / natural_low
    elif blinks_per_min > natural_high:
        dev = (blinks_per_min - natural_high) / natural_high
    else:
        dev = 0
    score = float(np.clip(dev * 70, 0, 100))
    return score, round(blinks_per_min, 1)


def temporal_consistency_score(frames):
    """Jitter in frame-to-frame face-region residuals. Returns 0-100.

    Real handheld video sits in a natural jitter band: sensor noise, micro
    head movement, and compression give frame-to-frame residuals some
    variance, but not too much. Two failure modes both look unnatural:
      - too HIGH jitter: glitchy, erratic re-rendering artifacts
      - too LOW jitter: over-blended/interpolated faces that are smoother
        than a real camera ever produces (this used to be scored as
        "not suspicious," which is backwards -- it's a real deepfake tell
        as often as jitter is)
    """
    residual_energies = []
    prev_face_region = None
    for frame in frames:
        faces = detect_faces(frame)
        if not faces:
            continue
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        region = cv2.resize(_to_gray(frame[y:y + h, x:x + w]), (96, 96)).astype(np.float32)
        if prev_face_region is not None:
            residual_energies.append(np.abs(region - prev_face_region).mean())
        prev_face_region = region

    if len(residual_energies) < 3:
        return 0.0

    residual_energies = np.array(residual_energies)
    mean_r = residual_energies.mean() + 1e-6
    jitter = residual_energies.std() / mean_r

    natural_low, natural_high = 0.15, 0.35
    if jitter < natural_low:
        dev = (natural_low - jitter) / natural_low
    elif jitter > natural_high:
        dev = (jitter - natural_high) / natural_high
    else:
        dev = 0
    score = float(np.clip(dev * 90, 0, 100))
    return score


def analyze_video(path):
    frames, fps = _sample_frames(path)
    if not frames:
        return {"error": "Could not read any frames from this video."}

    per_frame_results = [analyze_image(f) for f in frames]
    frame_confidences = [r["manipulation_confidence"] for r in per_frame_results]

    blink_score, blinks_per_min = blink_rate_score(frames, fps)
    temporal_score = temporal_consistency_score(frames)

    # Use the 75th-percentile frame confidence instead of the mean so that a
    # handful of heavily-manipulated frames are not drowned out by clean ones.
    sorted_fc = sorted(frame_confidences)
    p75_frame_conf = float(np.percentile(sorted_fc, 75)) if sorted_fc else 0.0
    avg_frame_conf = float(np.mean(frame_confidences))

    # Check if any faces were detected across frames — needed for signal weighting.
    faces_in_frames = sum(r.get("faces_detected", 0) for r in per_frame_results)
    has_faces = faces_in_frames > 0

    # Give frame-level signals more weight; blink/temporal often score 0 when
    # the cascade can't locate faces (common for compressed downloaded video).
    weights = {"frames": 0.55, "blink": 0.25, "temporal": 0.20}
    weighted_avg = (weights["frames"] * p75_frame_conf +
                    weights["blink"] * blink_score +
                    weights["temporal"] * temporal_score)

    # Floor: the strongest single signal directly anchors the overall score.
    strongest_signal = max(p75_frame_conf, blink_score, temporal_score)
    floor = strongest_signal  # no haircut — a real signal sets the minimum

    # Boost logic — triggers are intentionally low because modern deepfakes
    # are designed to pass classical forensics and will rarely score above 40%
    # on pure heuristics; even a modest elevation across frames is meaningful.
    #
    # Additionally: if we detected faces in frames but blink/temporal both
    # read 0, that means the face-region temporal checks silently failed —
    # which itself is suspicious (real people blink, real video has jitter).
    face_cascade_silent = has_faces and blink_score == 0 and temporal_score == 0
    elevated_signals = sum([
        p75_frame_conf > 25,   # lowered from 35 — modern deepfakes hover ~30-35%
        blink_score > 25,
        temporal_score > 25,
        face_cascade_silent,   # cascades detected faces but gave no temporal signal
    ])
    if elevated_signals >= 3:
        boost = 22.0
    elif elevated_signals == 2:
        boost = 15.0
    elif elevated_signals == 1:
        boost = 10.0
    else:
        boost = 0.0

    total = max(weighted_avg, floor) + boost

    return {
        "manipulation_confidence": round(float(np.clip(total, 0, 100)), 1),
        "frames_analyzed": len(frames),
        "signals": {
            "avg_frame_artifact_score": round(avg_frame_conf, 1),
            "p75_frame_artifact_score": round(p75_frame_conf, 1),
            "blink_rate_anomaly_score": round(blink_score, 1),
            "estimated_blinks_per_min": blinks_per_min,
            "temporal_consistency_score": round(temporal_score, 1),
        },
        "frame_confidence_timeline": [round(c, 1) for c in frame_confidences],
    }
