"""Phase 6 — L6 uniform 80 Hz resample.

Outputs:
  data/interim/phase6_resampled.parquet   — uniform 12.5 ms grid per segment
  data/interim/phase6_resample_summary.csv
  figures/phase6_resample.png             — irregular vs uniform on three slices
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from mousepipe.resample import resample_all, PERIOD_MS
from mousepipe import TARGET_HZ


def main() -> None:
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    df = pl.read_parquet(interim / "phase5_gated.parquet")
    print(f"in:  {df.height:,} rows, irregular ({TARGET_HZ:.0f} Hz nominal)")

    out = resample_all(df)
    print(f"out: {out.height:,} rows on uniform {PERIOD_MS:.2f} ms grid")

    # Per-segment row counts
    seg = df["segment_id"].to_numpy()
    seg_out = out["segment_id"].to_numpy()
    summary_rows = []
    for sid in sorted(np.unique(seg)):
        n_in  = int((seg == sid).sum())
        n_out = int((seg_out == sid).sum())
        m_in  = df.filter(pl.col("segment_id") == sid)
        m_out = out.filter(pl.col("segment_id") == sid)
        dur_in_s  = (m_in["t_ms"].max()  - m_in["t_ms"].min())  / 1000.0
        dur_out_s = (m_out["t_ms"].max() - m_out["t_ms"].min()) / 1000.0
        summary_rows.append({
            "segment_id": int(sid),
            "n_in":  n_in,
            "n_out": n_out,
            "ratio_out_in": round(n_out / n_in, 4),
            "duration_s_in":  round(dur_in_s, 3),
            "duration_s_out": round(dur_out_s, 3),
        })
    summary = pl.DataFrame(summary_rows)
    summary.write_csv(interim / "phase6_resample_summary.csv")
    print()
    print("Per-segment summary:")
    print(summary)

    # Verify grid uniformity within each segment
    dt = out.with_columns(pl.col("t_ms").diff().over("segment_id").alias("dt"))["dt"].drop_nulls().to_numpy()
    print()
    print(f"Δt within segments after resample: min={dt.min():.4f} ms, max={dt.max():.4f} ms (should equal {PERIOD_MS} ms)")

    out_path = interim / "phase6_resampled.parquet"
    out.write_parquet(out_path)
    print(f"\nwrote {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")

    # ----- Figure -----
    t_in_s  = df["t_ms"].to_numpy()  / 1000.0
    t_out_s = out["t_ms"].to_numpy() / 1000.0
    m_in    = df["m_total"].to_numpy()
    m_out   = out["m_total"].to_numpy()

    fig, axes = plt.subplots(3, 1, figsize=(13, 11), constrained_layout=True)

    # Panel 1: empty cage → mouse-in (uniform grid should be smooth)
    ax = axes[0]
    mask_in  = t_in_s < 60
    mask_out = t_out_s < 60
    ax.plot(t_in_s[mask_in],   m_in[mask_in],   "o", ms=2, alpha=0.4, color="grey", label="irregular input")
    ax.plot(t_out_s[mask_out], m_out[mask_out], "-", lw=0.8, color="C0", label="80 Hz uniform")
    ax.set_title("Phase 6 — First 60 s on the uniform 80 Hz grid")
    ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("m_total (g)")
    ax.legend(); ax.grid(alpha=0.3)

    # Panel 2: zoom on a few seconds of fine jitter to show interpolation does no harm
    ax = axes[1]
    target = 1565.0
    mask_in  = (t_in_s  > target - 1) & (t_in_s  < target + 1)
    mask_out = (t_out_s > target - 1) & (t_out_s < target + 1)
    ax.plot(t_in_s[mask_in],   m_in[mask_in],   "o-", ms=4, lw=0.6, color="grey", alpha=0.7, label="irregular input")
    ax.plot(t_out_s[mask_out], m_out[mask_out], "x-", ms=4, lw=0.6, color="C0", label="80 Hz uniform")
    ax.set_title(f"Phase 6 — 2-s zoom around t={target} s (inside grooming bout)")
    ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("m_total (g)")
    ax.legend(); ax.grid(alpha=0.3)

    # Panel 3: the segment boundary should show a clean break — derive the actual gap from data
    ax = axes[2]
    seg_end_seg0_ms   = df.filter(pl.col("segment_id") == 0)["t_ms"].max()
    seg_start_seg1_ms = df.filter(pl.col("segment_id") == 1)["t_ms"].min()
    gap_lo_s = seg_end_seg0_ms / 1000.0
    gap_hi_s = seg_start_seg1_ms / 1000.0
    gap_s    = gap_hi_s - gap_lo_s
    center_s = (gap_lo_s + gap_hi_s) / 2

    pad_s = 4.0
    mask_in  = (t_in_s  > center_s - pad_s) & (t_in_s  < center_s + pad_s)
    mask_out = (t_out_s > center_s - pad_s) & (t_out_s < center_s + pad_s)
    ax.plot(t_in_s[mask_in],   m_in[mask_in],   "o", ms=3, alpha=0.5, color="grey", label="irregular input")
    so = out["segment_id"].to_numpy()
    for sid, color in [(0, "C0"), (1, "C2")]:
        m = mask_out & (so == sid)
        if m.any():
            ax.plot(t_out_s[m], m_out[m], "-", lw=0.9, color=color, label=f"80 Hz seg {sid}")
    ax.axvspan(gap_lo_s, gap_hi_s, color="red", alpha=0.20, label=f"{gap_s:.2f} s gap (no data)")
    ax.set_title(f"Phase 6 — Segment boundary; the {gap_s:.2f} s gap from {gap_lo_s:.2f}s to {gap_hi_s:.2f}s is NOT bridged")
    ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("m_total (g)")
    ax.legend(); ax.grid(alpha=0.3)

    fig_path = figures / "phase6_resample.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
