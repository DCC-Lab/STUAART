"""Phase 2 — L2 clock-outlier handling: detect segment boundaries.

Outputs:
  data/interim/phase2_segmented.parquet   — phase 1 + dt_ms + segment_id
  data/interim/phase2_segments.csv        — one row per segment
  data/interim/phase2_large_gaps.csv      — every dt > 50 ms with surrounding context
  figures/phase2_segments.png             — full timeline coloured by segment + zoom on the gap
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from mousepipe.clock import assign_segments, segment_summary, SEGMENT_BREAK_MS


def main() -> None:
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    df = pl.read_parquet(interim / "phase1_parsed.parquet")
    df = assign_segments(df)

    n_seg = df["segment_id"].n_unique()
    print(f"detected {n_seg} segment(s) using break threshold dt > {SEGMENT_BREAK_MS} ms")

    seg = segment_summary(df)
    print()
    print("Segment summary:")
    print(seg)

    # Save segmented data
    out = interim / "phase2_segmented.parquet"
    df.write_parquet(out)
    print(f"\nwrote {out}")

    seg.write_csv(interim / "phase2_segments.csv")
    print(f"wrote {interim / 'phase2_segments.csv'}")

    # Every dt > 50 ms — these are noteworthy even if below the segment threshold
    big_gaps = (
        df.with_columns(pl.arange(0, df.height).alias("row_idx"))
          .filter(pl.col("dt_ms") > 50)
          .select(["row_idx", "t_ms", "dt_ms", "r1", "r2", "r3", "sum", "segment_id"])
    )
    big_gaps.write_csv(interim / "phase2_large_gaps.csv")
    print(f"wrote {interim / 'phase2_large_gaps.csv'}  ({big_gaps.height} rows)")
    print()
    print("Δt > 50 ms (potentially worth knowing, even if not a segment break):")
    print(big_gaps)

    # ----- Figure -----
    t_s = df["t_ms"].to_numpy() / 1000.0
    s = df["sum"].to_numpy()
    seg_id = df["segment_id"].to_numpy()

    fig, axes = plt.subplots(2, 1, figsize=(13, 8), constrained_layout=True)

    # Panel 1: full timeline coloured by segment
    ax = axes[0]
    colors = plt.cm.tab10(np.linspace(0, 1, max(2, n_seg)))
    for sid in range(n_seg):
        mask = seg_id == sid
        ax.plot(t_s[mask] / 60.0, s[mask], lw=0.3, color=colors[sid % len(colors)],
                label=f"segment {sid}")
    ax.set_title(f"Phase 2 — Segmentation (gaps > {SEGMENT_BREAK_MS} ms break the series)")
    ax.set_xlabel("scale clock time (minutes)")
    ax.set_ylabel("r1 + r2 + r3 (g)")
    ax.set_ylim(-100, 100)
    ax.axhline(22, color="g", lw=0.5, alpha=0.5, ls="--")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)

    # Panel 2: zoom on the 2.57 s gap
    if big_gaps.height > 0:
        # find biggest gap
        biggest = big_gaps.sort("dt_ms", descending=True).head(1)
        t_gap_ms = int(biggest["t_ms"][0])
        t_gap_s = t_gap_ms / 1000.0
        ax = axes[1]
        window_s = 8
        m = (t_s > t_gap_s - window_s) & (t_s < t_gap_s + window_s)
        ax.plot(t_s[m], df["r1"].to_numpy()[m], lw=0.7, label="r1", alpha=0.8)
        ax.plot(t_s[m], df["r2"].to_numpy()[m], lw=0.7, label="r2", alpha=0.8)
        ax.plot(t_s[m], df["r3"].to_numpy()[m], lw=0.7, label="r3", alpha=0.8)
        ax.plot(t_s[m], s[m], lw=1.0, label="sum", color="k")
        ax.axvspan(t_gap_s - biggest["dt_ms"][0] / 1000.0, t_gap_s, color="red", alpha=0.15,
                   label=f"gap: {int(biggest['dt_ms'][0])} ms")
        ax.set_title(f"Phase 2 — Zoom on the largest dropout at scale_t ≈ {t_gap_s:.1f} s")
        ax.set_xlabel("scale clock time (s)")
        ax.set_ylabel("mass (g)")
        ax.legend(loc="upper left", ncol=2, fontsize=8)
        ax.grid(alpha=0.3)

    fig_path = figures / "phase2_segments.png"
    fig.savefig(fig_path, dpi=130)
    print(f"\nwrote {fig_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
