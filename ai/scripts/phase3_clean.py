"""Phase 3 — L3 per-channel cleaning.

Outputs:
  data/interim/phase3_cleaned.parquet     — adds r{1,2,3} cleaned, sum cleaned, spike_r{1,2,3}
  data/interim/phase3_spike_summary.csv   — fraction of samples flagged per channel
  data/interim/phase3_top_spikes.csv      — the 50 worst raw outliers and what they became
  figures/phase3_cleaning.png             — before/after on the r2 = -100 outlier and on a generic slice
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from mousepipe.channel_clean import clean_channel, HAMPEL_WINDOW, HAMPEL_K, SAVGOL_WINDOW, SAVGOL_POLY


def main() -> None:
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    print(f"Hampel: window={HAMPEL_WINDOW} samples ({HAMPEL_WINDOW*12.5:.0f} ms), k={HAMPEL_K}")
    print(f"SavGol: window={SAVGOL_WINDOW} samples ({SAVGOL_WINDOW*12.5:.0f} ms), poly={SAVGOL_POLY}")
    print()

    df = pl.read_parquet(interim / "phase2_segmented.parquet")
    seg = df["segment_id"].to_numpy()

    cleaned = {}
    spikes  = {}
    for ch in ("r1", "r2", "r3"):
        raw = df[ch].to_numpy()
        c, s = clean_channel(raw, seg)
        cleaned[ch] = c
        spikes[ch]  = s
        n_spike = int(s.sum())
        print(f"  {ch}: {n_spike:,} samples flagged as spikes  ({100*n_spike/len(s):.3f} %)")

    # Build output frame
    out = df.with_columns(
        # rename raw columns and add cleaned ones
        pl.col("r1").alias("r1_raw"),
        pl.col("r2").alias("r2_raw"),
        pl.col("r3").alias("r3_raw"),
        pl.col("sum").alias("sum_raw"),
    ).drop("r1", "r2", "r3", "sum").with_columns(
        pl.Series("r1", cleaned["r1"]),
        pl.Series("r2", cleaned["r2"]),
        pl.Series("r3", cleaned["r3"]),
        pl.Series("spike_r1", spikes["r1"]),
        pl.Series("spike_r2", spikes["r2"]),
        pl.Series("spike_r3", spikes["r3"]),
    ).with_columns(
        (pl.col("r1") + pl.col("r2") + pl.col("r3")).alias("sum")
    )

    out_path = interim / "phase3_cleaned.parquet"
    out.write_parquet(out_path)
    print(f"\nwrote {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")

    # Spike summary
    summary = pl.DataFrame({
        "channel": ["r1", "r2", "r3"],
        "n_spike": [int(spikes[c].sum()) for c in ("r1","r2","r3")],
        "n_total": [len(spikes["r1"])] * 3,
        "pct":     [100*spikes[c].mean() for c in ("r1","r2","r3")],
        "raw_min": [float(df[c].min()) for c in ("r1","r2","r3")],
        "raw_max": [float(df[c].max()) for c in ("r1","r2","r3")],
        "clean_min": [float(cleaned[c].min()) for c in ("r1","r2","r3")],
        "clean_max": [float(cleaned[c].max()) for c in ("r1","r2","r3")],
    })
    summary.write_csv(interim / "phase3_spike_summary.csv")
    print(f"wrote {interim / 'phase3_spike_summary.csv'}")
    print()
    print("Per-channel summary:")
    print(summary)

    # Top spikes per channel (the biggest deviations that got corrected)
    rows = []
    for ch in ("r1","r2","r3"):
        raw = df[ch].to_numpy()
        cln = cleaned[ch]
        deltas = np.abs(raw - cln)
        idx = np.argsort(deltas)[::-1][:20]
        for i in idx:
            if deltas[i] < 0.1: break
            rows.append({
                "channel": ch,
                "t_ms": int(df["t_ms"][int(i)]),
                "row_idx": int(i),
                "raw_value": float(raw[i]),
                "cleaned_value": float(cln[i]),
                "delta": float(deltas[i]),
            })
    top_spikes = pl.DataFrame(rows).sort("delta", descending=True)
    top_spikes.write_csv(interim / "phase3_top_spikes.csv")
    print(f"wrote {interim / 'phase3_top_spikes.csv'}")

    # ----- Figure -----
    t_s = df["t_ms"].to_numpy() / 1000.0
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), constrained_layout=True)

    # Panel 1: zoom on the r2 = -100 spike at t ≈ 1019.5 s
    ax = axes[0]
    t_target = 1019.5
    m = (t_s > t_target - 1.5) & (t_s < t_target + 1.5)
    ax.plot(t_s[m], df["r2"].to_numpy()[m], "o-", lw=0.5, ms=3, label="r2 raw", color="red", alpha=0.6)
    ax.plot(t_s[m], cleaned["r2"][m],       "o-", lw=0.8, ms=3, label="r2 cleaned", color="green")
    sp = spikes["r2"][m]
    if sp.any():
        ax.scatter(t_s[m][sp], df["r2"].to_numpy()[m][sp], s=60, facecolors="none",
                   edgecolors="red", lw=1.5, label="flagged spike", zorder=5)
    ax.set_title("Phase 3 — Hampel kills the r2 = −100 g single-sample spike (zoom on t≈1019.5 s)")
    ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("r2 (g)")
    ax.legend(); ax.grid(alpha=0.3)

    # Panel 2: full timeline of sum_raw vs sum_clean (clipped)
    ax = axes[1]
    sum_raw = df["sum"].to_numpy()
    sum_cln = out["sum"].to_numpy()
    ax.plot(t_s / 60, sum_raw, lw=0.3, color="red", alpha=0.4, label="sum raw")
    ax.plot(t_s / 60, sum_cln, lw=0.3, color="green", alpha=0.8, label="sum cleaned")
    ax.set_ylim(-50, 50)
    ax.axhline(22, color="k", lw=0.5, alpha=0.5, ls="--", label="mouse weight ≈ 22 g")
    ax.set_title("Phase 3 — Full-timeline summed mass: raw (red) vs cleaned (green)")
    ax.set_xlabel("scale clock time (min)"); ax.set_ylabel("sum (g)")
    ax.legend(loc="upper right"); ax.grid(alpha=0.3)

    # Panel 3: normal mouse activity zoom (random 8s window inside labeled span)
    ax = axes[2]
    t_zoom = 1564.5  # middle of the long grooming bout
    m = (t_s > t_zoom - 4) & (t_s < t_zoom + 4)
    ax.plot(t_s[m], df["r1"].to_numpy()[m], lw=0.5, label="r1 raw", color="C0", alpha=0.45)
    ax.plot(t_s[m], df["r2"].to_numpy()[m], lw=0.5, label="r2 raw", color="C1", alpha=0.45)
    ax.plot(t_s[m], df["r3"].to_numpy()[m], lw=0.5, label="r3 raw", color="C2", alpha=0.45)
    ax.plot(t_s[m], cleaned["r1"][m], lw=1.0, label="r1 clean", color="C0")
    ax.plot(t_s[m], cleaned["r2"][m], lw=1.0, label="r2 clean", color="C1")
    ax.plot(t_s[m], cleaned["r3"][m], lw=1.0, label="r3 clean", color="C2")
    ax.set_title("Phase 3 — Per-channel raw vs cleaned during a real gesture (grooming bout, video_t=1564–1628s)")
    ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("mass (g)")
    ax.legend(loc="upper right", ncol=3, fontsize=8); ax.grid(alpha=0.3)

    fig_path = figures / "phase3_cleaning.png"
    fig.savefig(fig_path, dpi=130)
    print(f"\nwrote {fig_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
