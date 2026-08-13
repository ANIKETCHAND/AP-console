"""
Image forensic analysis.

This module does NOT use a trained deepfake-classification neural network
(no labeled GAN/faceswap dataset is available in this environment). Instead
it implements four classic, published forensic signal heuristics and fuses
them into a single manipulation-probability score:

  1. Frequency-domain (FFT) artifact analysis
     GAN / diffusion decoders leave periodic upsampling artifacts in the
     high-frequency band of the magnitude spectrum (Zhang et al., 2019,
     "Detecting and Simulating Artifacts in GAN Fake Images").

  2. Error Level Analysis (ELA)
     Re-compressing a JPEG and diffing against the original exposes regions
     that were edited/pasted at a different compression history.

  3. Block-wise noise-variance inconsistency
     Camera sensor noise is statistically uniform across an untouched photo.
     Spliced/synthetic regions break that uniformity.

  4. Facial symmetry / illumination consistency
     Synthetic faces frequently show subtle left/right asymmetries in
     texture and lighting that real photographed faces don't.

See backend/README (or the project README) for how to swap this out for a
trained classifier (e.g. a fine-tuned XceptionNet on FaceForensics++) in a
production setting.
"""

import io

import cv2
import numpy as np
from PIL import Image

try:
    if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
        FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        EYE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    else:
        FACE_CASCADE = None
        EYE_CASCADE = None
except Exception:
    FACE_CASCADE = None
    EYE_CASCADE = None


def _to_gray(img_bgr):
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


def detect_faces(img_bgr):
    if FACE_CASCADE is None or not hasattr(FACE_CASCADE, "detectMultiScale") or getattr(FACE_CASCADE, "empty", lambda: True)():
        return []
    try:
        gray = _to_gray(img_bgr)
        faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        return list(faces)
    except Exception:
        return []


def frequency_artifact_score(img_bgr):
    """High-frequency energy ratio + spectral periodicity. Returns 0-100.

    NOTE ON CALIBRATION: earlier versions of this function assumed real
    camera photos sit at a high/low frequency ratio of ~0.25-0.45. That
    assumption does not hold — measuring it against a set of known-genuine
    reference photos gave ratios of 0.72-0.78, i.e. ordinary photos with
    normal texture detail were being scored as if they deviated heavily
    from "normal," which produced false "manipulated" verdicts on real
    images. The band below is set from that empirical measurement, with a
    wide tolerance because natural photos vary a lot by subject/lens/ISO.
    """
    gray = _to_gray(img_bgr).astype(np.float32)
    gray = cv2.resize(gray, (256, 256))
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = np.log1p(np.abs(fshift))

    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    low_mask = r <= min(h, w) * 0.15
    high_mask = r >= min(h, w) * 0.35

    low_energy = magnitude[low_mask].mean()
    high_energy = magnitude[high_mask].mean()
    ratio = high_energy / (low_energy + 1e-6)

    # Wide tolerance band centered on the empirically-measured natural
    # range. Only ratios clearly outside this band (near-total absence of
    # high-frequency detail, or an unnatural excess/periodic spike caught
    # separately below) contribute to the score.
    natural_low, natural_high = 0.45, 1.05
    if ratio < natural_low:
        deviation = (natural_low - ratio) / natural_low
    elif ratio > natural_high:
        deviation = (ratio - natural_high) / natural_high
    else:
        deviation = 0.0
    score = np.clip(deviation * 90, 0, 100)

    # Periodicity check: real sensor noise is close to isotropic; grid-like
    # upsampling artifacts show strong peaks at regular angles. This part
    # tested consistently low on genuine photos and is left as-is.
    angles = np.linspace(0, np.pi, 18, endpoint=False)
    ring = (r > min(h, w) * 0.3) & (r < min(h, w) * 0.45)
    angle_map = np.arctan2(y - cy, x - cx) % np.pi
    bucket_vals = [magnitude[ring & (np.abs(angle_map - a) < 0.09)].mean()
                   if np.any(ring & (np.abs(angle_map - a) < 0.09)) else 0
                   for a in angles]
    bucket_vals = np.array(bucket_vals)
    periodicity = 0
    if bucket_vals.std() > 0:
        periodicity = np.clip((bucket_vals.max() - bucket_vals.mean()) / (bucket_vals.std() + 1e-6) * 8, 0, 100)

    return float(np.clip(0.6 * score + 0.4 * periodicity, 0, 100))


def _estimate_jpeg_quality(raw_bytes):
    """Recover the quality factor the file was ORIGINALLY saved at, by reading
    its quantization tables. Returns None if this isn't a JPEG (PNG/BMP/WEBP
    have no prior compression history for ELA to compare against)."""
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.format != "JPEG":
            return None
        qtables = img.quantization
        if not qtables:
            return None
        # Standard IJG luminance quantization table (quality-50 baseline).
        std_luma = np.array([
            16, 11, 10, 16, 24, 40, 51, 61,
            12, 12, 14, 19, 26, 58, 60, 55,
            14, 13, 16, 24, 40, 57, 69, 56,
            14, 17, 22, 29, 51, 87, 80, 62,
            18, 22, 37, 56, 68, 109, 103, 77,
            24, 35, 55, 64, 81, 104, 113, 92,
            49, 64, 78, 87, 103, 121, 120, 101,
            72, 92, 95, 98, 112, 100, 103, 99,
        ], dtype=np.float64)
        table = np.array(qtables[0], dtype=np.float64)
        scale = (table / std_luma).mean()
        if scale <= 1e-6:
            return 100
        if scale <= 1.0:
            quality = round((2 - scale) * 50)
        else:
            quality = round(5000 / (scale * 100))
        return int(np.clip(quality, 1, 100))
    except Exception:
        return None


def error_level_analysis_score(img_bgr, raw_bytes=None):
    """Re-JPEG-compress and diff. Returns 0-100, or None if this signal
    isn't meaningful for the source format (see _estimate_jpeg_quality)."""
    source_quality = _estimate_jpeg_quality(raw_bytes) if raw_bytes else None
    if raw_bytes is not None and source_quality is None:
        # Not a JPEG originally (PNG/BMP/WEBP) — there's no prior JPEG
        # compression history to diff against. Forcing one through a JPEG
        # encoder here would measure image content, not editing, and
        # reliably false-flags genuine lossless-format photos.
        return None

    # Recompress at the SAME quality the file was already saved at, not a
    # fixed value. Diffing against a mismatched quality (e.g. always 90)
    # flags ordinary recompression history from social apps/screenshots as
    # if it were localized editing.
    quality = source_quality if source_quality is not None else 90
    ok, encoded = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return 0.0
    recompressed = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if recompressed is None or recompressed.shape != img_bgr.shape:
        recompressed = cv2.resize(recompressed, (img_bgr.shape[1], img_bgr.shape[0]))

    diff = cv2.absdiff(img_bgr, recompressed).astype(np.float32)
    diff_gray = cv2.cvtColor(diff.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)

    h, w = diff_gray.shape
    block = 16
    block_means = []
    for by in range(0, h - block, block):
        for bx in range(0, w - block, block):
            block_means.append(diff_gray[by:by + block, bx:bx + block].mean())
    block_means = np.array(block_means) if block_means else np.array([0.0])

    # High variance across blocks = some regions compressed differently
    # from the rest = signature of localized editing/splicing.
    #
    # NOTE: when recompression quality matches the source well (the
    # expected case for a genuine, unedited photo), the diff is tiny
    # (mean diff often < 1 out of 255). Dividing std by that near-zero
    # mean blows the ratio up toward infinity — a PERFECT match then
    # scores as maximally suspicious, which is backwards. A noise floor
    # on the denominator prevents that: below it we're just measuring
    # encoder rounding, not a meaningful signal.
    noise_floor = 1.5
    global_mean = max(block_means.mean(), noise_floor)
    cv = block_means.std() / global_mean
    score = np.clip(cv * 35, 0, 100)
    return float(score)


def noise_inconsistency_score(img_bgr):
    """Block-wise local noise variance uniformity. Returns 0-100."""
    gray = _to_gray(img_bgr).astype(np.float32)
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    residual = gray - denoised

    h, w = residual.shape
    block = 24
    variances = []
    for by in range(0, h - block, block):
        for bx in range(0, w - block, block):
            variances.append(residual[by:by + block, bx:bx + block].var())
    variances = np.array(variances) if variances else np.array([0.0])

    mean_v = variances.mean() + 1e-6
    cv = variances.std() / mean_v
    # Real camera photos routinely have cv in the 0.4-1.2 range due to
    # natural contrast variation (sky vs. skin vs. fabric etc.). The old
    # threshold of 0.4 fired on virtually every genuine photo.
    # Raise the dead-band to 1.2 and use a gentler slope so that only
    # images with strongly non-uniform noise (spliced/blended regions)
    # produce a meaningful score.
    score = np.clip((cv - 1.2) * 25, 0, 100)
    return float(score)


def facial_symmetry_score(img_bgr, face_box):
    """Compare left/right half of the detected face. Returns 0-100.

    NOTE ON CALIBRATION: the previous "natural" band (8-22) was measured
    incorrectly. A real, unedited face crop (non-studio lighting, slight
    head angle — i.e. an ordinary photo) measured 39.8, well outside that
    band, so normal photos were being flagged as synthetic just for not
    being perfectly frontal and evenly lit. Widened the band and softened
    the slope to match. This signal is inherently noisy (pose/lighting
    dominate over any GAN-averaging effect) so it's also weighted lightly
    in the final fusion below.
    """
    x, y, w, h = face_box
    face = img_bgr[y:y + h, x:x + w]
    if face.size == 0:
        return 0.0
    face = cv2.resize(face, (200, 200))
    gray = _to_gray(face).astype(np.float32)
    left = gray[:, :100]
    right = cv2.flip(gray[:, 100:], 1)

    diff = np.abs(left - right)
    asymmetry = diff.mean()
    # Natural faces have plenty of asymmetry from pose and lighting alone;
    # extremely LOW asymmetry is the more reliable tell of a GAN-averaged/
    # synthetic face. Extremely HIGH asymmetry is a weak signal on its own
    # (ordinary side-lit photos produce it too), so it contributes less.
    natural_low, natural_high = 6, 42
    if asymmetry < natural_low:
        dev = (natural_low - asymmetry) / natural_low
        score = np.clip(dev * 80, 0, 100)
    elif asymmetry > natural_high:
        dev = (asymmetry - natural_high) / natural_high
        score = np.clip(dev * 35, 0, 100)  # gentler slope, weak signal alone
    else:
        score = 0
    return float(score)


def analyze_image(img_bgr, raw_bytes=None):
    faces = detect_faces(img_bgr)
    freq = frequency_artifact_score(img_bgr)
    ela = error_level_analysis_score(img_bgr, raw_bytes=raw_bytes)
    noise = noise_inconsistency_score(img_bgr)

    symmetry_scores = [facial_symmetry_score(img_bgr, f) for f in faces]
    symmetry = float(np.mean(symmetry_scores)) if symmetry_scores else None

    weights = {"freq": 0.30, "ela": 0.25, "noise": 0.25, "symmetry": 0.20}
    total_weight = weights["freq"] + weights["noise"]
    total = weights["freq"] * freq + weights["noise"] * noise

    if ela is not None:
        total += weights["ela"] * ela
        total_weight += weights["ela"]

    if symmetry is not None:
        total += weights["symmetry"] * symmetry
        total_weight += weights["symmetry"]

    confidence = float(np.clip(total / total_weight, 0, 100))
    valid_signals = [s for s in [freq, ela, noise, symmetry] if s is not None]
    max_signal = max(valid_signals) if valid_signals else 0.0

    if max_signal >= 50.0:
        confidence = float(np.clip(0.50 * confidence + 0.50 * max_signal, 0, 100))

    return {
        "manipulation_confidence": round(confidence, 1),
        "faces_detected": len(faces),
        "signals": {
            "frequency_artifact_score": round(freq, 1),
            "error_level_analysis_score": round(ela, 1) if ela is not None else None,
            "noise_inconsistency_score": round(noise, 1),
            "facial_symmetry_score": round(symmetry, 1) if symmetry is not None else None,
        },
    }
