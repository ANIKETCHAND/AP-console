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
MAX_CONSECUTIVE_FRAMES = 48
MAX_CONSECUTIVE_SECONDS = 6


def _sample_frames(path, max_frames=MAX_SAMPLED_FRAMES):
    """Evenly-spaced frames across the WHOLE video, for per-frame forensic
    scoring (artifact/ELA/noise/symmetry). Good for broad coverage, but the
    gaps between frames make this unsuitable for anything that needs real
    elapsed time between frames (blink rate, jitter) — see
    _sample_consecutive_frames for that."""
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


def _sample_consecutive_frames(path, max_frames=MAX_CONSECUTIVE_FRAMES,
                                max_seconds=MAX_CONSECUTIVE_SECONDS):
    """A short run of genuinely BACK-TO-BACK frames (not evenly spread across
    the video). Blink rate and frame-to-frame jitter are only meaningful
    when the elapsed time between samples is the real inter-frame interval
    — computing them on widely-spaced samples (as the evenly-spread sampler
    above does) silently measures normal head movement / scene change over
    seconds and reports it as if it were per-frame jitter, wildly inflating
    both signals. This grabs a real short clip instead."""
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    n_target = min(max_frames, int(max_seconds * fps)) if fps > 0 else max_frames

    if total <= 0:
        frames = []
        while len(frames) < n_target:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
        cap.release()
        return frames, fps

    n = min(n_target, total)
    # Start a third of the way in rather than frame 0 — avoids fade-ins/
    # intro cards/black frames that some clips open with.
    start = max(0, (total - n) // 3)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    frames = []
    for _ in range(n):
        ok, frame = cap.read()
        if not ok:
            break
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


def _debounce_states(states):
    """Haar-cascade eye detection flickers frame-to-frame even on a static,
    genuine face (lighting micro-changes, cascade jitter) — a single-frame
    True/False/True blip is almost always cascade noise, not a real blink.
    Collapse any run shorter than 2 frames into its neighboring state before
    counting transitions, so we count actual open->closed->open blink
    events instead of sensor noise."""
    if len(states) < 3:
        return states
    out = list(states)
    for i in range(1, len(out) - 1):
        if out[i] is None:
            continue
        if out[i] != out[i - 1] and out[i] != out[i + 1] and out[i - 1] == out[i + 1] and out[i - 1] is not None:
            out[i] = out[i - 1]
    return out


def blink_rate_score(frames, fps):
    """Returns 0-100 anomaly score plus estimated blinks/min.

    IMPORTANT: `frames` must be a genuinely consecutive run (see
    _sample_consecutive_frames) — the elapsed time used below assumes
    real, unbroken inter-frame spacing. Passing evenly-spread frames here
    (as an earlier version did) understates the elapsed time by however
    much the video was down-sampled, which can inflate the apparent
    blink rate by 10-100x on anything longer than a couple of seconds."""
    states = []
    for frame in frames:
        faces = detect_faces(frame)
        if not faces:
            states.append(None)
            continue
        biggest = max(faces, key=lambda f: f[2] * f[3])
        states.append(_eyes_open_in_frame(frame, biggest))

    states = _debounce_states(states)
    valid = [s for s in states if s is not None]
    if len(valid) < 6:
        # Not enough reliable eye detections to say anything — stay silent
        # rather than guess off a handful of noisy samples.
        return 0.0, None

    transitions = 0
    for a, b in zip(valid, valid[1:]):
        if a and not b:
            transitions += 1

    duration_s = max(len(frames) / max(fps, 1), 1e-3)
    blinks_per_min = transitions * (60 / duration_s)
    # Cap at a physiologically-plausible ceiling. Anything far beyond this
    # on a short clip is almost certainly detector noise, not a real signal
    # — reporting an implausible number as if it were trustworthy evidence
    # is worse than reporting nothing.
    blinks_per_min = min(blinks_per_min, 90.0)

    natural_low, natural_high = 6, 30
    if blinks_per_min < natural_low:
        dev = (natural_low - blinks_per_min) / natural_low
    elif blinks_per_min > natural_high:
        dev = (blinks_per_min - natural_high) / natural_high
    else:
        dev = 0
    score = float(np.clip(dev * 55, 0, 100))
    return score, round(blinks_per_min, 1)


def temporal_consistency_score(frames):
    """Jitter in frame-to-frame face-region residuals. Returns 0-100.

    IMPORTANT: `frames` must be a genuinely consecutive run — see the note
    on blink_rate_score above; the same sampling bug applied here.

    Real handheld video sits in a natural jitter band: sensor noise, micro
    head movement, and compression give frame-to-frame residuals some
    variance, but not too much. Two failure modes both look unnatural:
      - too HIGH jitter: glitchy, erratic re-rendering artifacts
      - too LOW jitter: over-blended/interpolated faces that are smoother
        than a real camera ever produces
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

    if len(residual_energies) < 6:
        return 0.0

    residual_energies = np.array(residual_energies)
    mean_r = residual_energies.mean() + 1e-6
    jitter = residual_energies.std() / mean_r

    natural_low, natural_high = 0.10, 0.55
    if jitter < natural_low:
        dev = (natural_low - jitter) / natural_low
    elif jitter > natural_high:
        dev = (jitter - natural_high) / natural_high
    else:
        dev = 0
    score = float(np.clip(dev * 55, 0, 100))
    return score


def analyze_video(path):
    frames, fps = _sample_frames(path)
    if not frames:
        return {"error": "Could not read any frames from this video."}

    consecutive_frames, cfps = _sample_consecutive_frames(path)

    per_frame_results = [analyze_image(f) for f in frames]
    frame_confidences = [r["manipulation_confidence"] for r in per_frame_results]

    blink_score, blinks_per_min = blink_rate_score(consecutive_frames, cfps)
    temporal_score = temporal_consistency_score(consecutive_frames)

    # Use the mean/median frame confidence, not the 75th percentile.
    # Percentile-based scoring cherry-picks the worst few frames out of
    # every clip — and with heuristic per-frame signals (which have real
    # false-positive noise on ANY frame, real or fake), some frames will
    # always look "worse" than others by chance.
    avg_frame_conf = float(np.mean(frame_confidences))
    median_frame_conf = float(np.median(frame_confidences))

    faces_in_frames = sum(r.get("faces_detected", 0) for r in per_frame_results)
    has_faces = faces_in_frames > 0

    # Blink/temporal signals frequently read 0 simply because the Haar
    # cascade failed to find eyes/faces — that is an absence of signal, not
    # evidence of anything. Only fold them in when they actually had face
    # data to compute from, and even then keep their weight modest since
    # they are the noisiest signals in this pipeline.
    signals = [(median_frame_conf, 0.7)]
    if has_faces and blinks_per_min is not None:
        signals.append((blink_score, 0.15))
        signals.append((temporal_score, 0.15))

    total_weight = sum(w for _, w in signals)
    total = sum(s * w for s, w in signals) / total_weight if total_weight else median_frame_conf

    return {
        "manipulation_confidence": round(float(np.clip(total, 0, 100)), 1),
        "frames_analyzed": len(frames),
        "signals": {
            "avg_frame_artifact_score": round(avg_frame_conf, 1),
            "median_frame_artifact_score": round(median_frame_conf, 1),
            "blink_rate_anomaly_score": round(blink_score, 1),
            "estimated_blinks_per_min": blinks_per_min,
            "temporal_consistency_score": round(temporal_score, 1),
        },
        "frame_confidence_timeline": [round(c, 1) for c in frame_confidences],
    }
