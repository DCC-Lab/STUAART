"""Phase 7g — Sync validation on the cleaned 80 Hz grid.

For each lag in ±5 s, shift the gesture indicator and measure how well it correlates
with the magnitude of mass deviation from baseline. Peak lag = suggested correction.

Two probe signals are compared:
  (a) rolling-std envelope of m_total (general "wiggle")
  (b) |m_total - baseline| (deviation magnitude)
Both should peak at the same lag; if they don't, the conclusion is shaky.

Outputs:
  data/interim/phase7g_sync_correlation.csv  — lag vs corr for both probes
  figures/phase7g_sync_correlation.png       — correlation profile + peak markers
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from mousepipe import TARGET_HZ
from mousepipe.labels import LABELED_START_MS, LABELED_END_MS


def normalize(x: np.ndarray) -> np.ndarray:
    x = x - x.mean()
    n = np.sqrt((x * x).sum())
    return x / (n if n > 0 else 1.0)


def main() -> None:
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    df = pl.read_parquet(interim / "phase7_labeled.parquet")
    # Restrict to labelled span AND single segment (segment 0 contains all labels)
    df = df.filter(pl.col("is_labeled") & (pl.col("segment_id") == 0))
    print(f"labelled frames in segment 0: {df.height:,}")

    t = df["t_ms"].to_numpy()
    m = df["m_total"].to_numpy()
    cls = df["class"].to_numpy()

    fs = TARGET_HZ  # 80 Hz uniform
    period_ms = 1000.0 / fs

    # Probe (a): rolling-std envelope (window = 0.5 s = 40 samples)
    W = 40
    kernel = np.ones(W) / W
    m_mean = np.convolve(m, kernel, mode="same")
    m_var  = np.convolve((m - m_mean) ** 2, kernel, mode="same")
    wiggle = np.sqrt(np.maximum(m_var, 0))

    # Probe (b): |m_total - baseline|, baseline = median over class==0 frames
    baseline = float(np.median(m[cls == 0]))
    abs_dev  = np.abs(m - baseline)
    # Smooth abs_dev with same window so they're comparable
    abs_dev_smooth = np.convolve(abs_dev, kernel, mode="same")

    # Gesture indicator: 1 where class > 0 (any gesture), 0 elsewhere. Exclude class=-1.
    gi = np.zeros_like(m)
    gi[cls > 0] = 1.0
    # Mask out class=-1 frames so they don't drive the correlation
    valid = cls >= 0

    print(f"baseline (median over class=0): {baseline:.3f} g")
    print(f"in-gesture wiggle mean:    {wiggle[cls > 0].mean():.3f}  (rest mean {wiggle[cls == 0].mean():.3f})")
    print(f"in-gesture abs_dev mean:   {abs_dev_smooth[cls > 0].mean():.3f}  (rest mean {abs_dev_smooth[cls == 0].mean():.3f})")

    # Lag scan: ±5 s in 12.5 ms steps
    max_lag_s = 5.0
    lags_samp = np.arange(-int(max_lag_s * fs), int(max_lag_s * fs) + 1)
    lags_s = lags_samp * (period_ms / 1000.0)

    def correlate_at_lag(probe, lag_samples):
        """Shift probe by lag (positive = probe later than gi); measure corr against gi."""
        if lag_samples == 0:
            a = probe[valid]; b = gi[valid]
        elif lag_samples > 0:
            a = probe[lag_samples:]; b = gi[:-lag_samples]
            mask = valid[lag_samples:] & valid[:-lag_samples]  # use valid mask shifted
            a = probe[lag_samples:][mask]; b = gi[:-lag_samples][mask]
        else:
            k = -lag_samples
            mask = valid[k:] & valid[:-k]
            a = probe[:-k][mask]; b = gi[k:][mask]
        if len(a) < 100:
            return np.nan
        return float((normalize(a) * normalize(b)).sum())

    print(f"\nscanning {len(lags_samp)} lags from {lags_s.min():.2f} s to {lags_s.max():.2f} s...")
    corr_wiggle = np.array([correlate_at_lag(wiggle, k) for k in lags_samp])
    corr_dev    = np.array([correlate_at_lag(abs_dev_smooth, k) for k in lags_samp])

    peak_wig_idx = int(np.nanargmax(corr_wiggle))
    peak_dev_idx = int(np.nanargmax(corr_dev))
    print(f"\nwiggle  peak: lag = {lags_s[peak_wig_idx]:+.3f} s  corr = {corr_wiggle[peak_wig_idx]:.4f}")
    print(f"abs_dev peak: lag = {lags_s[peak_dev_idx]:+.3f} s  corr = {corr_dev[peak_dev_idx]:.4f}")

    # Persist
    pl.DataFrame({
        "lag_s": lags_s,
        "corr_wiggle": corr_wiggle,
        "corr_abs_dev": corr_dev,
    }).write_csv(interim / "phase7g_sync_correlation.csv")

    # ----- Figure -----
    fig, ax = plt.subplots(1, 1, figsize=(13, 6), constrained_layout=True)
    ax.plot(lags_s, corr_wiggle, color="C0", lw=1, label=f"rolling-std (peak {lags_s[peak_wig_idx]:+.3f} s)")
    ax.plot(lags_s, corr_dev,    color="C1", lw=1, label=f"|m − baseline| (peak {lags_s[peak_dev_idx]:+.3f} s)")
    ax.axvline(0, color="k", lw=0.5, alpha=0.5, label="current sync (no change)")
    ax.axvline(lags_s[peak_wig_idx], color="C0", ls=":", lw=1, alpha=0.6)
    ax.axvline(lags_s[peak_dev_idx], color="C1", ls=":", lw=1, alpha=0.6)
    ax.set_xlabel("lag of signal probe vs gesture indicator (s)\nPositive = signal happens LATER than label; need to SHIFT labels LATER (increase offset).")
    ax.set_ylabel("correlation")
    ax.set_title("Phase 7g — Sync validation: cross-correlation of gesture indicator vs mass-deviation probes")
    ax.legend()
    ax.grid(alpha=0.3)
    fig_path = figures / "phase7g_sync_correlation.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
