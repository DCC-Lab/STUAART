"""Phase 4 — L4 tare correction + fusion.

Uses the 20 Hz-cleaned per-channel signal (r{i}_20hz from phase 3).
Subtracts per-channel median over the empty-cage window [0, 18] s.
Sums to m_total.

Outputs:
  data/interim/phase4_fused.parquet
  data/interim/phase4_tare_values.csv
  figures/phase4_tare_fusion.png
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from mousepipe import EMPTY_CAGE_END_S
from mousepipe.tare_fuse import fuse


def main() -> None:
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    df = pl.read_parquet(interim / "phase3_variants.parquet")
    print(f"in: {df.height:,} rows, {df.width} cols (using 20 Hz variant)")

    fused, tare = fuse(df, source_suffix="_20hz")
    print()
    print("Per-channel tare offsets (median over scale_t ∈ [0, 18] s, in g):")
    for ch, v in tare.items():
        print(f"  {ch}: {v:+.4f}")

    # Persist tare values
    pl.DataFrame({"channel": list(tare.keys()), "tare_g": list(tare.values())}).write_csv(
        interim / "phase4_tare_values.csv"
    )

    # Slim output: keep what downstream needs, drop the 5x duplicates of L3 variants
    out = fused.select([
        "t_ms", "dt_ms", "segment_id",
        "r1_raw", "r2_raw", "r3_raw", "sum_raw",
        "r1_tared", "r2_tared", "r3_tared", "m_total",
    ])
    out_path = interim / "phase4_fused.parquet"
    out.write_parquet(out_path)
    print(f"\nwrote {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")

    # Sanity stats
    pre_mask = fused["t_ms"] <= int(EMPTY_CAGE_END_S * 1000)
    post_mask = (fused["t_ms"] > 20_000) & (fused["t_ms"] < 6_000_000)
    print()
    print("Verification:")
    print(f"  empty cage (t<{EMPTY_CAGE_END_S}s): "
          f"m_total mean = {fused.filter(pre_mask)['m_total'].mean():+.4f} g  "
          f"std = {fused.filter(pre_mask)['m_total'].std():.4f}")
    print(f"  mouse-in  (20s..end): "
          f"m_total mean = {fused.filter(post_mask)['m_total'].mean():+.4f} g  "
          f"median = {fused.filter(post_mask)['m_total'].median():+.4f} g")

    # ----- Figure -----
    t_s = fused["t_ms"].to_numpy() / 1000.0
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), constrained_layout=True)

    # Panel 1: distribution of pre-mouse channel values + tare markers
    ax = axes[0]
    pre_df = fused.filter(pre_mask)
    bins = np.linspace(-1, 1, 60)
    for ch, color in zip(("r1", "r2", "r3"), ("C0", "C1", "C2")):
        ax.hist(pre_df[f"{ch}_20hz"].to_numpy(), bins=bins, alpha=0.5,
                color=color, label=f"{ch}: median = {tare[ch]:+.3f} g")
        ax.axvline(tare[ch], color=color, ls="--", lw=1.2)
    ax.set_title(f"Phase 4 — Empty-cage histogram per channel (scale_t < {EMPTY_CAGE_END_S} s) — vertical lines = tare offsets")
    ax.set_xlabel("channel reading (g)"); ax.set_ylabel("count")
    ax.legend(); ax.grid(alpha=0.3)

    # Panel 2: first 60 s — verify post-tare empty cage sits at 0, mouse-in jumps to ~22 g
    ax = axes[1]
    m = t_s < 60
    ax.plot(t_s[m], fused["sum_raw"].to_numpy()[m], lw=0.7, color="grey", alpha=0.6, label="sum (untared)")
    ax.plot(t_s[m], fused["m_total"].to_numpy()[m], lw=0.9, color="black", label="m_total (tared)")
    ax.axvspan(0, EMPTY_CAGE_END_S, color="green", alpha=0.10, label="empty-cage anchor")
    ax.axvline(20, color="red", ls="--", lw=1, alpha=0.7, label="≈ mouse insertion")
    ax.axvline(43.5, color="purple", ls=":", lw=1, alpha=0.7, label="video starts")
    ax.axhline(0, color="k", lw=0.4, alpha=0.5)
    ax.set_title("Phase 4 — First 60 s after taring (empty cage → mouse in → video start)")
    ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("mass (g)")
    ax.legend(loc="upper left", fontsize=8, ncol=2); ax.grid(alpha=0.3)

    # Panel 3: full timeline of m_total
    ax = axes[2]
    ax.plot(t_s / 60, fused["m_total"].to_numpy(), lw=0.3, color="C0")
    ax.set_title("Phase 4 — Full timeline of m_total (after tare + sum)")
    ax.set_xlabel("scale clock time (min)"); ax.set_ylabel("m_total (g)")
    ax.axhline(0, color="k", lw=0.4, alpha=0.5)
    ax.axhline(22, color="g", lw=0.5, ls="--", alpha=0.6, label="≈ mouse weight")
    ax.set_ylim(-20, 60)
    ax.legend(); ax.grid(alpha=0.3)

    fig_path = figures / "phase4_tare_fusion.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
