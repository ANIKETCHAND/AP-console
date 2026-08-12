"""
Audio forensic analysis (voice-cloning / TTS detection).

Signals used, all grounded in published synthetic-speech-detection literature:

  1. Pitch (F0) contour smoothness
     Neural vocoders often produce an unnaturally smooth/regular pitch
     contour compared to the micro-jitter of a real human larynx.

  2. Spectral flatness / harmonic-to-noise consistency
     Vocoder outputs tend to have unusually flat or unusually clean spectra
     in the mid-high band vs. the natural breathiness of real speech.

  3. MFCC frame-to-frame variance
     Real speech has more micro-variation frame to frame; some TTS/voice
     conversion systems over-smooth MFCC trajectories.

  4. High-frequency energy roll-off
     Many vocoders leave a characteristic roll-off or artifact band above
     ~7–8kHz that differs from natural microphone recordings.

  5. Zero-crossing rate consistency
     Real speech shows highly variable ZCR; synthetic speech is more regular.
"""

import numpy as np

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

from scipy.io import wavfile
from scipy import signal


def _load(path, sr=22050):
    if HAS_LIBROSA:
        y, sr = librosa.load(path, sr=sr, mono=True)
        return y, sr
    try:
        sample_rate, data = wavfile.read(path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = data.astype(np.float32)
        if np.abs(data).max() > 0:
            data = data / np.abs(data).max()
        return data, sample_rate
    except Exception:
        return np.zeros(sr, dtype=np.float32), sr


# ── Signal 1: Pitch Smoothness ────────────────────────────────────────────
def pitch_smoothness_score(y, sr):
    """
    AI/TTS voices have unnaturally LOW pitch jitter (too smooth).
    Returns 0–100 anomaly score (higher = more likely synthetic).
    """
    if not HAS_LIBROSA:
        return 15.0
    try:
        f0, voiced_flag, _ = librosa.pyin(
            y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sr
        )
        f0 = f0[~np.isnan(f0)]
        if len(f0) < 10:
            return 0.0

        # Coefficient of variation of F0 differences (jitter proxy)
        diffs = np.abs(np.diff(f0))
        jitter = diffs.mean() / (f0.mean() + 1e-6)

        # Real human speech: jitter typically 0.01–0.05
        # Synthetic speech: jitter often < 0.008 (too smooth)
        if jitter < 0.008:
            score = (0.008 - jitter) / 0.008 * 100
        elif jitter > 0.08:
            # Also suspicious if extremely erratic (distortion)
            score = min((jitter - 0.08) / 0.05 * 40, 40)
        else:
            score = 0.0

        return float(np.clip(score, 0, 100))
    except Exception:
        return 15.0


# ── Signal 2: Spectral Flatness ───────────────────────────────────────────
def spectral_flatness_score(y, sr):
    """
    AI voices often have unusually low variance in spectral flatness.
    Returns 0–100 anomaly score.
    """
    if not HAS_LIBROSA:
        try:
            freqs, times, Sxx = signal.spectrogram(y, fs=sr)
            flatness = np.exp(np.mean(np.log(Sxx + 1e-10), axis=0)) / (np.mean(Sxx, axis=0) + 1e-10)
            variance = flatness.std()
            score = max(0, (0.015 - variance) / 0.015 * 100) if variance < 0.015 else 0
            return float(np.clip(score, 0, 100))
        except Exception:
            return 10.0
    try:
        flatness = librosa.feature.spectral_flatness(y=y)[0]
        # Real speech: flatness std typically > 0.015
        # Synthetic: very low std (too consistent)
        variance = flatness.std()
        if variance < 0.015:
            score = (0.015 - variance) / 0.015 * 100
        else:
            score = 0.0
        return float(np.clip(score, 0, 100))
    except Exception:
        return 10.0


# ── Signal 3: MFCC Variance ───────────────────────────────────────────────
def mfcc_variance_score(y, sr):
    """
    Real speech has high MFCC frame-to-frame variation.
    Over-smoothed trajectories = synthetic signal.
    Returns 0–100 anomaly score.
    """
    if not HAS_LIBROSA:
        return 15.0
    try:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        frame_diffs = np.abs(np.diff(mfcc, axis=1))
        mean_diff = frame_diffs.mean()

        # Real human speech MFCC delta: typically 4.0–9.0
        # Synthetic speech: often < 3.0 (over-smoothed)
        if mean_diff < 3.0:
            score = (3.0 - mean_diff) / 3.0 * 100
        elif mean_diff > 12.0:
            # Extremely noisy audio (not speech)
            score = min((mean_diff - 12.0) / 5.0 * 30, 30)
        else:
            score = 0.0

        return float(np.clip(score, 0, 100))
    except Exception:
        return 15.0


# ── Signal 4: High-Frequency Roll-Off ────────────────────────────────────
def high_freq_rolloff_score(y, sr):
    """
    Many vocoders produce a characteristic dip or excess in the 7–8kHz+ band.
    Returns 0–100 anomaly score.
    """
    if not HAS_LIBROSA:
        try:
            freqs, times, Sxx = signal.spectrogram(y, fs=sr)
            high_band = Sxx[freqs >= 7500, :]
            if high_band.size == 0:
                return 0.0
            ratio = high_band.mean() / (Sxx.mean() + 1e-6)
            if ratio < 0.05:
                score = (0.05 - ratio) / 0.05 * 80
            elif ratio > 0.6:
                score = (ratio - 0.6) / 0.4 * 50
            else:
                score = 0.0
            return float(np.clip(score, 0, 100))
        except Exception:
            return 10.0
    try:
        stft = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        high_band = stft[freqs >= 7500, :]
        full_band = stft
        if high_band.size == 0:
            return 0.0
        ratio = high_band.mean() / (full_band.mean() + 1e-6)
        # Natural speech: ratio typically 0.05–0.50
        # Too low: vocoder roll-off artifact
        # Too high: unusual for human voice
        if ratio < 0.05:
            score = (0.05 - ratio) / 0.05 * 80
        elif ratio > 0.60:
            score = (ratio - 0.60) / 0.40 * 50
        else:
            score = 0.0
        return float(np.clip(score, 0, 100))
    except Exception:
        return 10.0


# ── Signal 5: Zero-Crossing Rate Regularity ──────────────────────────────
def zcr_regularity_score(y, sr):
    """
    Real speech: highly variable ZCR.
    Synthetic speech: more regular (lower std deviation).
    Returns 0–100 anomaly score.
    """
    try:
        if HAS_LIBROSA:
            zcr = librosa.feature.zero_crossing_rate(y)[0]
        else:
            # Manual ZCR
            signs = np.sign(y)
            crossings = np.diff(signs) != 0
            frame_size = sr // 100
            frames = len(crossings) // frame_size
            zcr = np.array([crossings[i*frame_size:(i+1)*frame_size].mean() for i in range(frames)])

        zcr_std = zcr.std()
        # Real speech: ZCR std typically > 0.05
        # Synthetic: < 0.03 (too regular)
        if zcr_std < 0.03:
            score = (0.03 - zcr_std) / 0.03 * 80
        else:
            score = 0.0
        return float(np.clip(score, 0, 100))
    except Exception:
        return 10.0


# ── Main Entry Point ──────────────────────────────────────────────────────
def analyze_audio(path):
    y, sr = _load(path)
    if len(y) < sr * 0.5:
        return {"error": "Audio clip is too short to analyze reliably (need at least ~0.5s)."}

    pitch      = pitch_smoothness_score(y, sr)
    flatness   = spectral_flatness_score(y, sr)
    mfcc_var   = mfcc_variance_score(y, sr)
    rolloff    = high_freq_rolloff_score(y, sr)
    zcr        = zcr_regularity_score(y, sr)

    # Weighted combination — pitch and MFCC are most reliable indicators
    weights = {"pitch": 0.30, "flatness": 0.15, "mfcc": 0.30, "rolloff": 0.15, "zcr": 0.10}
    total = (
        weights["pitch"]    * pitch +
        weights["flatness"] * flatness +
        weights["mfcc"]     * mfcc_var +
        weights["rolloff"]  * rolloff +
        weights["zcr"]      * zcr
    )
    total = float(np.clip(total, 0, 100))

    # Clear verdict thresholds
    if total >= 45:
        verdict_label = "SYNTHETIC / AI-GENERATED"
    elif total >= 22:
        verdict_label = "LIKELY SYNTHETIC — SUSPICIOUS"
    else:
        verdict_label = "AUTHENTIC — NO MANIPULATION DETECTED"

    return {
        "manipulation_confidence": round(total, 1),
        "verdict_label": verdict_label,
        "duration_seconds": round(len(y) / sr, 2),
        "signals": {
            "pitch_smoothness_anomaly": round(pitch, 1),
            "spectral_flatness_anomaly": round(flatness, 1),
            "mfcc_variance_anomaly": round(mfcc_var, 1),
            "high_freq_rolloff_anomaly": round(rolloff, 1),
            "zcr_regularity_anomaly": round(zcr, 1),
        },
    }
