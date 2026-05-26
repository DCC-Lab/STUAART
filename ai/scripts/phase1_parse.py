"""Phase 1 — L1 parse the raw mass CSV.

Outputs:
  data/interim/phase1_parsed.parquet   — cleaned rows (t_ms, r1, r2, r3, sum)
  data/interim/phase1_parsed_head.csv  — first 1000 rows (browser-friendly preview)
  data/interim/phase1_dt_distribution.csv — distribution of inter-sample dt
  figures/phase1_overview.png          — 3-panel: full timeline, first 60 s zoom, dt hist
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from mousepipe import RAW_CSV
from mousepipe.io_raw import load_raw


def main() -> None:
    raw_path = ROOT / RAW_CSV
    print(f"Reading {raw_path}")
    df = load_raw(raw_path)
    meta = df.attrs
    print(f"  raw rows         : {meta['n_raw_rows']:,}")
    print(f"  sentinel dropped : {meta['n_sentinel_dropped']:,}")
    print(f"  rows kept        : {meta['n_kept']:,}")
    print(f"  time span        : {df['t_ms'].min()/1000:.2f} .. {df['t_ms'].max()/1000:.2f} s "
          f"({(df['t_ms'].max()-df['t_ms'].min())/60_000:.2f} min)")

    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    # Persist parquet (full) + small CSV preview.
    parquet_out = interim / "phase1_parsed.parquet"
    df.write_parquet(parquet_out)
    print(f"  wrote {parquet_out}  ({parquet_out.stat().st_size/1e6:.1f} MB)")

    head_csv = interim / "phase1_parsed_head.csv"
    df.head(1000).write_csv(head_csv)
    print(f"  wrote {head_csv}")

    # Δt distribution.
    dt = df["t_ms"].diff().drop_nulls().to_numpy()
    dt_counts = (
        pl.DataFrame({"dt_ms": dt})
        .group_by("dt_ms")
        .len()
        .sort("len", descending=True)
    )
    dt_csv = interim / "phase1_dt_distribution.csv"
    dt_counts.write_csv(dt_csv)
    print(f"  wrote {dt_csv}")

    # Summary stats.
    print()
    print("Δt summary (ms):")
    print(f"  min={dt.min()}  p50={int(np.median(dt))}  p99={int(np.percentile(dt, 99))}  max={dt.max()}")
    print(f"  count(dt > 500 ms) = {(dt > 500).sum()}   (these become segment breaks in L2)")

    # ----- Figure -----
    t_s = df["t_ms"].to_numpy() / 1000.0
    s = df["sum"].to_numpy()
    r1 = df["r1"].to_numpy(); r2 = df["r2"].to_numpy(); r3 = df["r3"].to_numpy()

    fig, axes = plt.subplots(3, 1, figsize=(13, 10), constrained_layout=True)

    # Panel 1: full timeline of sum
    ax = axes[0]
    ax.plot(t_s / 60.0, s, lw=0.3, color="#1f77b4")
    ax.set_title("Phase 1 — Summed mass over the full recording (raw, untared)")
    ax.set_xlabel("scale clock time (minutes)")
    ax.set_ylabel("r1 + r2 + r3 (g)")
    ax.set_ylim(-100, 100)  # clip extreme outliers for visibility
    ax.axhline(0, color="k", lw=0.5, alpha=0.3)
    ax.axhline(22, color="g", lw=0.5, alpha=0.5, ls="--", label="~22 g (mouse weight)")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)

    # Panel 2: zoom on first 60 s — empty cage → mouse insertion
    ax = axes[1]
    m_zoom = t_s < 60
    ax.plot(t_s[m_zoom], r1[m_zoom], lw=0.6, label="r1", alpha=0.8)
    ax.plot(t_s[m_zoom], r2[m_zoom], lw=0.6, label="r2", alpha=0.8)
    ax.plot(t_s[m_zoom], r3[m_zoom], lw=0.6, label="r3", alpha=0.8)
    ax.plot(t_s[m_zoom], s[m_zoom],  lw=1.0, label="sum", color="k")
    ax.axvspan(0, 18, color="green", alpha=0.10, label="empty cage (tare zone)")
    ax.axvline(20, color="red", ls="--", lw=1, alpha=0.7, label="≈ mouse insertion")
    ax.axvline(43.5, color="purple", ls=":", lw=1, alpha=0.7, label="video starts")
    ax.set_title("Phase 1 — First 60 s: empty cage → mouse in → video start")
    ax.set_xlabel("scale clock time (s)")
    ax.set_ylabel("mass (g)")
    ax.legend(loc="upper left", ncol=2, fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 60)

    # Panel 3: log-scale histogram of Δt
    ax = axes[2]
    ax.hist(dt, bins=np.arange(0, 60, 1), color="#2ca02c", edgecolor="black", lw=0.3)
    ax.set_yscale("log")
    ax.set_title("Phase 1 — Inter-sample time gap (Δt) distribution; expect ~12 ms")
    ax.set_xlabel("Δt (ms)")
    ax.set_ylabel("count (log scale)")
    ax.axvline(12, color="orange", ls="--", lw=1, label="median ≈ 12 ms")
    ax.axvline(500, color="red", ls="--", lw=1, label="L2 segment-break threshold (500 ms)")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    ax.set_xlim(0, 60)

    fig_path = figures / "phase1_overview.png"
    fig.savefig(fig_path, dpi=130)
    print(f"\nwrote {fig_path}")
    plt.close(fig)


if __name__ == "__main__":
    main()
