"""Phase 5 — L5 off-scale gate.

Outputs:
  data/interim/phase5_gated.parquet
  data/interim/phase5_off_scale_episodes.csv
  figures/phase5_gate.png
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from mousepipe.presence import apply_off_scale_gate, THETA_ON_G, THETA_OFF_G, MIN_DURATION_MS


def episodes_from_mask(is_loaded: np.ndarray, t_ms: np.ndarray) -> pl.DataFrame:
    """Return one row per off-scale episode: (start_ms, end_ms, duration_ms)."""
    off = ~is_loaded
    if not off.any():
        return pl.DataFrame({"start_ms": [], "end_ms": [], "duration_ms": []},
                            schema={"start_ms": pl.Int64, "end_ms": pl.Int64, "duration_ms": pl.Int64})
    change = np.diff(off.astype(np.int8))
    rises = np.where(change == 1)[0] + 1
    falls = np.where(change == -1)[0] + 1
    if off[0]:
        rises = np.concatenate(([0], rises))
    if off[-1]:
        falls = np.concatenate((falls, [len(off)]))
    rows = []
    for s, e in zip(rises, falls):
        rows.append({"start_ms": int(t_ms[s]),
                     "end_ms":   int(t_ms[min(e, len(t_ms)-1)]),
                     "duration_ms": int(t_ms[min(e, len(t_ms)-1)] - t_ms[s])})
    return pl.DataFrame(rows).sort("start_ms")


def main() -> None:
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    df = pl.read_parquet(interim / "phase4_fused.parquet")
    t_ms = df["t_ms"].to_numpy()
    m_pre = df["m_total"].to_numpy()

    print(f"Schmitt thresholds: θ_on={THETA_ON_G} g, θ_off={THETA_OFF_G} g, min duration={MIN_DURATION_MS} ms")
    gated, is_loaded = apply_off_scale_gate(m_pre, t_ms)

    # Stats
    n = len(is_loaded)
    n_off = int((~is_loaded).sum())
    print(f"\nOff-scale fraction: {n_off / n * 100:.2f} %  ({n_off:,} / {n:,} samples)")

    eps = episodes_from_mask(is_loaded, t_ms)
    print(f"Off-scale episodes: {eps.height}")
    if eps.height:
        print(f"  duration ms — min: {eps['duration_ms'].min()}  med: {eps['duration_ms'].median()}  max: {eps['duration_ms'].max()}")
        print(f"  longest 5 episodes:")
        print(eps.sort("duration_ms", descending=True).head(5))

    # Save
    out = df.with_columns(
        pl.col("m_total").alias("m_total_pre_gate"),
        pl.Series("is_loaded", is_loaded),
        pl.Series("state", np.where(is_loaded, "loaded", "off_scale")),
    ).drop("m_total").with_columns(pl.Series("m_total", gated))

    # Reorder for readability
    out = out.select([
        "t_ms", "dt_ms", "segment_id",
        "r1_raw", "r2_raw", "r3_raw", "sum_raw",
        "r1_tared", "r2_tared", "r3_tared",
        "m_total_pre_gate", "is_loaded", "state", "m_total",
    ])

    out_path = interim / "phase5_gated.parquet"
    out.write_parquet(out_path)
    print(f"\nwrote {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")

    eps.write_csv(interim / "phase5_off_scale_episodes.csv")
    print(f"wrote {interim / 'phase5_off_scale_episodes.csv'}")

    # ----- Figure -----
    t_s = t_ms / 1000.0
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), constrained_layout=True)

    # Panel 1: full timeline with gate overlay
    ax = axes[0]
    ax.plot(t_s / 60, m_pre, lw=0.3, color="grey", alpha=0.5, label="m_total pre-gate")
    ax.plot(t_s / 60, gated, lw=0.3, color="C0", label="m_total (post-gate, clamped 0 off-scale)")
    # Highlight off-scale episodes
    for s in eps.head(50).iter_rows(named=True):
        ax.axvspan(s["start_ms"]/60_000, s["end_ms"]/60_000, color="red", alpha=0.2)
    ax.axhline(0, color="k", lw=0.4, alpha=0.5)
    ax.axhline(THETA_ON_G, color="green", lw=0.5, ls="--", alpha=0.5, label=f"θ_on={THETA_ON_G} g")
    ax.axhline(THETA_OFF_G, color="orange", lw=0.5, ls="--", alpha=0.5, label=f"θ_off={THETA_OFF_G} g")
    ax.set_ylim(-15, 50)
    ax.set_title("Phase 5 — Full timeline; red shading = off-scale episodes")
    ax.set_xlabel("scale clock time (min)"); ax.set_ylabel("m_total (g)")
    ax.legend(loc="upper right"); ax.grid(alpha=0.3)

    # Panel 2: zoom on the empty-cage→mouse-in transition; gate should flip ON at ~20 s
    ax = axes[1]
    m = t_s < 60
    ax.plot(t_s[m], m_pre[m], lw=0.6, color="grey", alpha=0.7, label="m_total pre-gate")
    ax.plot(t_s[m], gated[m], lw=1.0, color="C0", label="m_total post-gate")
    ax.fill_between(t_s[m], -5, 50, where=~is_loaded[m], color="red", alpha=0.15, label="off-scale")
    ax.axhline(0, color="k", lw=0.4, alpha=0.5)
    ax.axhline(THETA_ON_G, color="green", lw=0.5, ls="--", alpha=0.5)
    ax.axhline(THETA_OFF_G, color="orange", lw=0.5, ls="--", alpha=0.5)
    ax.set_xlim(0, 60); ax.set_ylim(-5, 50)
    ax.set_title("Phase 5 — First 60 s: gate is OFF during empty cage, flips ON at mouse insertion")
    ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("m_total (g)")
    ax.legend(loc="upper left", fontsize=8); ax.grid(alpha=0.3)

    # Panel 3: zoom on the LONGEST off-scale episode (after the first one)
    ax = axes[2]
    later = eps.filter(pl.col("start_ms") > 30_000).sort("duration_ms", descending=True)
    if later.height > 0:
        big = later.head(1)
        s_ms = int(big["start_ms"][0]); e_ms = int(big["end_ms"][0])
        s_s = s_ms / 1000.0; e_s = e_ms / 1000.0
        pad = max(2.0, (e_s - s_s) * 0.5)
        m = (t_s > s_s - pad) & (t_s < e_s + pad)
        ax.plot(t_s[m], m_pre[m], lw=0.6, color="grey", alpha=0.7, label="m_total pre-gate")
        ax.plot(t_s[m], gated[m], lw=1.0, color="C0", label="m_total post-gate")
        ax.fill_between(t_s[m], -5, 50, where=~is_loaded[m], color="red", alpha=0.15, label="off-scale episode")
        ax.axhline(0, color="k", lw=0.4, alpha=0.5)
        ax.axhline(THETA_ON_G, color="green", lw=0.5, ls="--", alpha=0.5)
        ax.axhline(THETA_OFF_G, color="orange", lw=0.5, ls="--", alpha=0.5)
        ax.set_title(f"Phase 5 — Longest mid-recording off-scale episode at t≈{s_s:.0f} s, duration {e_s - s_s:.1f} s")
        ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("m_total (g)")
        ax.legend(loc="upper right", fontsize=8); ax.grid(alpha=0.3)

    fig_path = figures / "phase5_gate.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
