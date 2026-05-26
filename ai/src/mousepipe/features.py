"""Hand-engineered features per 2-s window of m_total.

Features are organized into families:
  - Time-domain stats: spread, shape, range, robust spread
  - Trend: linear slope, residual stats after detrending
  - Frequency-band power: 0-2, 2-5, 5-10, 10-20, 20-40 Hz (last contaminated by aliasing)
  - Spectral shape: entropy, centroid, rolloff, dominant freq
  - Autocorrelation: peak height, peak lag, values at fixed lags
  - Envelope (Hilbert): mean, std, peakiness
  - Other: zero-crossing rate around mean

Reads: 1-D float32 window (length N at fs=80 Hz).
Returns: dict of {feature_name: float}.

Decisions in this module are informed by:
  - [[project-scale-aliasing-caveat]]: be cautious with 20–40 Hz band content
  - [[project-gesture-signal-character]]: gestures show less mass variability than rest;
    focus on shape, rhythm and envelope rather than energy
  - [[feedback-no-position-features]]: m_total only — never per-cell
"""
from __future__ import annotations
import numpy as np
from scipy import signal as sps
from scipy.stats import skew, kurtosis


FS_HZ = 80
BANDS = [
    ("p_0_2",   0.0,  2.0),
    ("p_2_5",   2.0,  5.0),
    ("p_5_10",  5.0, 10.0),
    ("p_10_20", 10.0, 20.0),
    ("p_20_40", 20.0, 40.0),
]


def extract_features(x: np.ndarray, fs: int = FS_HZ) -> dict[str, float]:
    """Compute the engineered feature vector for one window of `m_total`."""
    x = x.astype(np.float64)
    n = len(x)
    feats: dict[str, float] = {}

    # ---- Time-domain stats ----
    feats["mean"]   = float(np.mean(x))
    feats["std"]    = float(np.std(x))
    feats["mad"]    = float(np.median(np.abs(x - np.median(x))))   # robust spread
    feats["range"]  = float(np.ptp(x))
    feats["skew"]   = float(skew(x)) if feats["std"] > 1e-6 else 0.0
    feats["kurt"]   = float(kurtosis(x)) if feats["std"] > 1e-6 else 0.0
    feats["rms"]    = float(np.sqrt(np.mean(x ** 2)))

    # ---- Trend / detrended ----
    t = np.arange(n)
    slope, intercept = np.polyfit(t, x, deg=1)
    feats["slope"]  = float(slope)
    detr = x - (slope * t + intercept)
    feats["detr_std"] = float(np.std(detr))

    # ---- Zero-crossings of detrended signal (around 0) ----
    zc = int(((detr[:-1] * detr[1:]) < 0).sum())
    feats["zcr"] = float(zc) / (n / fs)  # crossings per second

    # ---- Frequency bands ----
    # Use Welch's PSD with reasonable resolution for 2-s windows (160 samples)
    nperseg = min(n, 128)
    f, P = sps.welch(detr, fs=fs, nperseg=nperseg, noverlap=nperseg // 2)
    total_power = float(np.trapezoid(P, f)) + 1e-12
    for name, lo, hi in BANDS:
        m = (f >= lo) & (f < hi)
        bp = float(np.trapezoid(P[m], f[m])) if m.any() else 0.0
        feats[name] = bp
        feats[f"{name}_frac"] = bp / total_power  # relative power

    # Spectral entropy (normalized)
    P_norm = P / (P.sum() + 1e-12)
    feats["spec_entropy"] = float(-np.sum(P_norm * np.log(P_norm + 1e-12)) / np.log(len(P_norm)))

    # Spectral centroid (Hz)
    feats["spec_centroid"] = float(np.sum(f * P) / (np.sum(P) + 1e-12))

    # Dominant frequency
    feats["dom_freq"] = float(f[int(np.argmax(P))])

    # ---- Autocorrelation features ----
    # Normalize detrended signal first
    x0 = detr - np.mean(detr)
    denom = np.dot(x0, x0) + 1e-12
    # Compute autocorrelation via full conv; take non-negative lags
    ac = np.correlate(x0, x0, mode="full") / denom
    ac = ac[n - 1:]  # lag 0 ... N-1
    # Values at specific lags (in samples)
    for lag_s in (0.1, 0.2, 0.5):
        lag_n = int(lag_s * fs)
        feats[f"ac_lag_{int(lag_s*1000)}ms"] = float(ac[lag_n]) if lag_n < len(ac) else 0.0
    # Position and height of first peak after lag 0
    # (find local max after a small leading window to avoid the lag-0 peak)
    skip = 3   # samples (~38 ms)
    if len(ac) > skip + 5:
        sub = ac[skip:]
        # First local max
        peak_rel = None
        for i in range(1, len(sub) - 1):
            if sub[i] > sub[i - 1] and sub[i] > sub[i + 1]:
                peak_rel = i
                break
        if peak_rel is not None:
            feats["ac_first_peak_lag_ms"] = float((peak_rel + skip) * 1000.0 / fs)
            feats["ac_first_peak_height"] = float(sub[peak_rel])
        else:
            feats["ac_first_peak_lag_ms"] = 0.0
            feats["ac_first_peak_height"] = 0.0
    else:
        feats["ac_first_peak_lag_ms"] = 0.0
        feats["ac_first_peak_height"] = 0.0

    # ---- Envelope (Hilbert transform of detrended signal) ----
    env = np.abs(sps.hilbert(detr))
    feats["env_mean"] = float(np.mean(env))
    feats["env_std"]  = float(np.std(env))
    # Peakiness: ratio of max to mean
    feats["env_peakiness"] = float(np.max(env) / (np.mean(env) + 1e-12))
    # Rise time approximation: time from 10 % to 90 % of max envelope
    e_max = np.max(env); lo = 0.1 * e_max; hi = 0.9 * e_max
    above_lo = np.where(env > lo)[0]
    above_hi = np.where(env > hi)[0]
    if len(above_lo) and len(above_hi):
        feats["env_rise_ms"] = float(max(0, above_hi[0] - above_lo[0]) * 1000.0 / fs)
    else:
        feats["env_rise_ms"] = 0.0

    return feats


def feature_names() -> list[str]:
    """Return the full feature name list (in deterministic order)."""
    # Use a single sample to discover names
    dummy = np.random.RandomState(0).randn(int(FS_HZ * 2)).astype(np.float32)
    return list(extract_features(dummy).keys())


def extract_features_batch(X: np.ndarray, fs: int = FS_HZ) -> np.ndarray:
    """Vectorise over rows. X: (B, N). Returns (B, F)."""
    rows = []
    names = feature_names()
    for i in range(X.shape[0]):
        f = extract_features(X[i], fs=fs)
        rows.append([f[n] for n in names])
    return np.asarray(rows, dtype=np.float32)
