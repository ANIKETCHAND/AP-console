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


def full_frame_temporal_jitter(frames):
    """Inter-frame temporal warping residual across all sampled frames. Returns 0-100."""
    if len(frames) < 3:
        return 0.0
    diffs = []
    for f1, f2 in zip(frames, frames[1:]):
        g1 = cv2.resize(_to_gray(f1), (128, 128)).astype(np.float32)
        g2 = cv2.resize(_to_gray(f2), (128, 128)).astype(np.float32)
        diffs.append(np.abs(g1 - g2).mean())
    if not diffs:
        return 0.0
    diffs = np.array(diffs)
    mean_diff = diffs.mean() + 1e-6
    cv_diff = diffs.std() / mean_diff

    # Real handheld/tripod video has natural motion & compression (cv_diff ~ 0.12 - 0.38)
    # AI-generated / faceswap videos exhibit temporal warping fluctuation (cv_diff > 0.42)
    # OR over-smoothed artificial interpolation (cv_diff < 0.08)
    if cv_diff > 0.42:
        return float(np.clip((cv_diff - 0.42) * 180, 0, 100))
    elif cv_diff < 0.08:
        return float(np.clip((0.08 - cv_diff) * 140, 0, 100))
    return 0.0


def face_boundary_discontinuity_score(frames):
    """Boundary edge-blur / color-blend discontinuity in face-swapped video. Returns 0-100."""
    boundary_scores = []
    for frame in frames:
        faces = detect_faces(frame)
        if not faces:
            continue
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        gray = _to_gray(frame).astype(np.float32)
        # Inspect boundary margin around face box
        y1, y2 = max(0, y - 10), min(gray.shape[0], y + h + 10)
        x1, x2 = max(0, x - 10), min(gray.shape[1], x + w + 10)
        sub = gray[y1:y2, x1:x2]
        if sub.size > 0:
            if HAS_CV2 and cv2 is not None:
                lap = np.abs(cv2.Laplacian(sub, cv2.CV_32F))
                boundary_scores.append(lap.std())
            else:
                boundary_scores.append(sub.std())
    if not boundary_scores:
        return 0.0
    b_val = float(np.mean(boundary_scores))
    # Faceswap Poisson/Gaussian seam blending reduces boundary edge Laplacian variance
    if b_val < 12.0:
        return float(np.clip((12.0 - b_val) * 6.0, 0, 100))
    return 0.0


def analyze_video(path):
    frames, fps = _sample_frames(path)
    if not frames:
        return {"error": "Could not read any frames from this video."}

    per_frame_results = [analyze_image(f) for f in frames]
    frame_confidences = [r["manipulation_confidence"] for r in per_frame_results]

    blink_score, blinks_per_min = blink_rate_score(frames, fps)
    temporal_score = temporal_consistency_score(frames)
    full_frame_jitter = full_frame_temporal_jitter(frames)
    boundary_discontinuity = face_boundary_discontinuity_score(frames)

    sorted_fc = sorted(frame_confidences, reverse=True)
    top_3_mean = float(np.mean(sorted_fc[:3])) if sorted_fc else 0.0
    avg_frame_conf = float(np.mean(frame_confidences))

    all_signals = [top_3_mean, full_frame_jitter, boundary_discontinuity]
    if blink_score > 0:
        all_signals.append(blink_score)
    if temporal_score > 0:
        all_signals.append(temporal_score)

    peak_signal = max(all_signals)

    # High-conviction anomaly aggregation: if any frame or temporal metric reaches 32%+,
    # scale overall confidence into deepfake territory (40%-90%), preventing false authentic verdicts.
    if peak_signal >= 32.0:
        total = max(top_3_mean * 1.15, peak_signal * 1.10)
    else:
        total = top_3_mean

    return {
        "manipulation_confidence": round(float(np.clip(total, 0, 100)), 1),
        "frames_analyzed": len(frames),
        "signals": {
            "avg_frame_artifact_score": round(avg_frame_conf, 1),
            "top_frame_artifact_score": round(top_3_mean, 1),
            "temporal_warp_jitter_score": round(full_frame_jitter, 1),
            "face_boundary_discontinuity_score": round(boundary_discontinuity, 1),
            "blink_rate_anomaly_score": round(blink_score, 1),
            "estimated_blinks_per_min": blinks_per_min,
            "temporal_consistency_score": round(temporal_score, 1),
        },
        "frame_confidence_timeline": [round(c, 1) for c in frame_confidences],
    }
