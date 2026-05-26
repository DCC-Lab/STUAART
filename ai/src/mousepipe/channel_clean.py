"""L3 — Per-channel cleaning: Hampel filter for spikes + Savitzky–Golay low-pass.

Applied independently per channel and per segment so we never bridge a hardware dropout.
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter

# Defaults
HAMPEL_WINDOW = 25       # samples ≈ 300 ms at 80 Hz
HAMPEL_K      = 3.0      # threshold in robust σ units
SAVGOL_WINDOW = 11       # samples ≈ 135 ms; preserves transients
SAVGOL_POLY   = 3


def hampel(x: np.ndarray, window: int = HAMPEL_WINDOW, k: float = HAMPEL_K) -> tuple[np.ndarray, np.ndarray]:
    """Robust spike rejector.

    Replaces a sample with the rolling median whenever its deviation exceeds
    k * 1.4826 * MAD over a centered window.

    Returns (cleaned, spike_mask).
    """
    med = median_filter(x, size=window, mode="reflect")
    mad = median_filter(np.abs(x - med), size=window, mode="reflect")
    sigma = 1.4826 * mad
    # Avoid divide-by-zero for perfectly quiet regions: if sigma is 0, fall back to a tiny floor.
    sigma = np.maximum(sigma, 1e-6)
    spike = np.abs(x - med) > k * sigma
    out = x.copy()
    out[spike] = med[spike]
    return out, spike


def lowpass_savgol(x: np.ndarray, window: int = SAVGOL_WINDOW, poly: int = SAVGOL_POLY) -> np.ndarray:
    """Light Savitzky–Golay low-pass. Preserves polynomial structure up to `poly`."""
    if len(x) < window:
        return x.copy()
    return savgol_filter(x, window_length=window, polyorder=poly, mode="interp")


def clean_channel(x: np.ndarray, seg_id: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Apply hampel + savgol per segment. Returns (cleaned, spike_mask)."""
    cleaned = np.empty_like(x, dtype=np.float32)
    spike   = np.zeros(x.shape, dtype=bool)
    for sid in np.unique(seg_id):
        m = seg_id == sid
        xs = x[m].astype(np.float64)
        de_spiked, sp = hampel(xs)
        smooth = lowpass_savgol(de_spiked)
        cleaned[m] = smooth.astype(np.float32)
        spike[m]   = sp
    return cleaned, spike
