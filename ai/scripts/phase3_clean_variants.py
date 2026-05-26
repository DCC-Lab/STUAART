"""Phase 3 variants — compare three low-pass cutoffs side by side.

For each channel we keep:
  r{c}_raw    : original
  r{c}_9hz    : Hampel + SavGol window=11   (-3dB ≈  9 Hz)
  r{c}_14hz   : Hampel + SavGol window=7    (-3dB ≈ 14 Hz)
  r{c}_20hz   : Hampel + SavGol window=5    (-3dB ≈ 20 Hz)
  r{c}_hampel : Hampel only (no low-pass)

Outputs:
  data/interim/phase3_variants.parquet
  figures/phase3_variants_grooming.png
  figures/phase3_variants_spectrum.png
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter, welch

from mousepipe.channel_clean import hampel


VARIANTS = {
    "9hz":  dict(window=11, poly=3, cutoff_hz=9),
    "14hz": dict(window=7,  poly=3, cutoff_hz=14),
    "20hz": dict(window=5,  poly=3, cutoff_hz=20),
}


def clean_with(cfg, x_segs):
    """x_segs is list of arrays, one per segment."""
    out_segs = []
    spike_segs = []
    for x in x_segs:
        xs = x.astype(np.float64)
        de_spiked, sp = hampel(xs)
        smooth = savgol_filter(de_spiked, window_length=cfg["window"], polyorder=cfg["poly"], mode="interp")
        out_segs.append(smooth.astype(np.float32))
        spike_segs.append(sp)
    return np.concatenate(out_segs), np.concatenate(spike_segs)


def hampel_only(x_segs):
    out_segs = []
    spike_segs = []
    for x in x_segs:
        xs = x.astype(np.float64)
        de_spiked, sp = hampel(xs)
        out_segs.append(de_spiked.astype(np.float32))
        spike_segs.append(sp)
    return np.concatenate(out_segs), np.concatenate(spike_segs)


def main() -> None:
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    df = pl.read_parquet(interim / "phase2_segmented.parquet")
    seg = df["segment_id"].to_numpy()
    seg_ids = np.unique(seg)

    out_cols = {
        "t_ms": df["t_ms"],
        "dt_ms": df["dt_ms"],
        "segment_id": df["segment_id"],
    }
    spike_summary = {}

    for ch in ("r1", "r2", "r3"):
        x = df[ch].to_numpy()
        out_cols[f"{ch}_raw"] = pl.Series(x)
        x_segs = [x[seg == sid] for sid in seg_ids]

        # Hampel-only
        h, sp = hampel_only(x_segs)
        out_cols[f"{ch}_hampel"] = pl.Series(h)
        spike_summary[ch] = int(sp.sum())

        # SavGol variants
        for name, cfg in VARIANTS.items():
            cleaned, _ = clean_with(cfg, x_segs)
            out_cols[f"{ch}_{name}"] = pl.Series(cleaned)

    out = pl.DataFrame(out_cols)
    for name in list(VARIANTS.keys()) + ["hampel"]:
        out = out.with_columns(
            (pl.col(f"r1_{name}") + pl.col(f"r2_{name}") + pl.col(f"r3_{name}")).alias(f"sum_{name}")
        )
    out = out.with_columns(
        (pl.col("r1_raw") + pl.col("r2_raw") + pl.col("r3_raw")).alias("sum_raw")
    )

    out_path = interim / "phase3_variants.parquet"
    out.write_parquet(out_path)
    print(f"wrote {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")
    print(f"spike fractions: {[(k, v/len(seg)*100) for k,v in spike_summary.items()]}")

    # --- Figure 1: time-domain comparison on the long grooming bout ---
    t_s = df["t_ms"].to_numpy() / 1000.0
    target_t = 1565.0  # inside the 1564–1628s grooming bout
    m = (t_s > target_t - 1.5) & (t_s < target_t + 1.5)

    fig, axes = plt.subplots(3, 1, figsize=(13, 11), constrained_layout=True, sharex=True)
    for ax, ch in zip(axes, ("r1", "r2", "r3")):
        ax.plot(t_s[m], out[f"{ch}_raw"].to_numpy()[m], lw=0.5, color="grey", alpha=0.5, label="raw")
        ax.plot(t_s[m], out[f"{ch}_hampel"].to_numpy()[m], lw=0.7, color="black", alpha=0.7, label="hampel only")
        ax.plot(t_s[m], out[f"{ch}_9hz"].to_numpy()[m], lw=1.3, label="9 Hz (win=11)", color="C0")
        ax.plot(t_s[m], out[f"{ch}_14hz"].to_numpy()[m], lw=1.3, label="14 Hz (win=7)", color="C1")
        ax.plot(t_s[m], out[f"{ch}_20hz"].to_numpy()[m], lw=1.3, label="20 Hz (win=5)", color="C2")
        ax.set_ylabel(f"{ch} (g)")
        ax.legend(loc="upper right", fontsize=8, ncol=5)
        ax.grid(alpha=0.3)
        ax.set_title(f"Phase 3 — {ch} during grooming bout (zoom on 3 s around t={target_t} s)")
    axes[-1].set_xlabel("scale clock time (s)")
    fig_path = figures / "phase3_variants_grooming.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"wrote {fig_path}")

    # --- Figure 2: power spectrum on the labeled span, from r3 (most active channel) ---
    # Use segment 0 only; restrict to the labeled span on scale clock [43.5, 2683.5] s
    seg0_mask = seg == 0
    t_seg = df["t_ms"].to_numpy()[seg0_mask] / 1000.0
    lab = (t_seg >= 43.5) & (t_seg <= 2683.5)
    fs_est = 1000.0 / np.median(np.diff(df["t_ms"].to_numpy()[seg0_mask][lab]))  # ~80 Hz
    print(f"effective fs in labeled span ≈ {fs_est:.2f} Hz (used for Welch)")

    fig, ax = plt.subplots(1, 1, figsize=(11, 6), constrained_layout=True)
    nperseg = 2048
    for name, color in [("raw", "grey"), ("hampel", "black"),
                        ("9hz", "C0"), ("14hz", "C1"), ("20hz", "C2")]:
        x = out[f"r3_{name}"].to_numpy()[seg0_mask][lab]
        f, P = welch(x, fs=fs_est, nperseg=min(nperseg, len(x)))
        ax.semilogy(f, P, label=name, color=color, lw=1.2 if name in VARIANTS else 0.9)
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("PSD (g² / Hz)")
    ax.set_title("Phase 3 — r3 power spectrum on labeled span; vertical dashes mark −3 dB cutoffs")
    for cutoff, c in [(9, "C0"), (14, "C1"), (20, "C2")]:
        ax.axvline(cutoff, color=c, ls="--", lw=1, alpha=0.6)
    ax.axvline(40, color="red", ls=":", lw=1, alpha=0.6, label="Nyquist (40 Hz)")
    ax.set_xlim(0, 40)
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    fig_path = figures / "phase3_variants_spectrum.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
