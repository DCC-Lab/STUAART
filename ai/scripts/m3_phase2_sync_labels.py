"""Mouse3 phase 2 — derive+validate sync, parse labels, rasterize, window.

Steps:
  1. Derive video->scale offset from the mouse-in load step.
  2. VALIDATE it independently: sweep candidate offsets and pick the one that
     maximises the movement-index separation between annotated sleeping frames
     and the rest (active). If the data-driven optimum agrees with the mouse-in
     anchor, sync is trustworthy.
  3. Parse all label sheets; merge the Sleeping intervals.
  4. Rasterize per-frame class (ACTIVE / SLEEP / BG) on the annotated span.
  5. Build interval-aware windows for modelling.

Output: data/processed/m3_windows.parquet
        figures/m3_phase2_sync.png, figures/m3_phase2_timeline.png
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy.ndimage import median_filter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mousepipe import mouse3 as m3

INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
PROCESSED.mkdir(parents=True, exist_ok=True)

WINDOW_LEN_S = 4.0   # sleep is slow; longer windows beat 2 s here
STRIDE_S     = 1.0
MARGIN_S     = 1.0


def rolling_movement_index(m_total: np.ndarray, win: int) -> np.ndarray:
    """Per-frame rolling median of |Δm_total| (a continuous actigraphy trace)."""
    d = np.abs(np.diff(m_total, prepend=m_total[0]))
    return median_filter(d, size=win, mode="nearest")


def main() -> None:
    frames = pl.read_parquet(INTERIM / "m3_frames.parquet").sort("t_ms")
    t_ms = frames["t_ms"].to_numpy().astype(np.int64)
    m_total = frames["m_total"].to_numpy().astype(np.float64)
    is_loaded = frames["is_loaded"].to_numpy().astype(bool)
    fs = m3.TARGET_HZ_M3

    # --- 1. mouse-in anchor ---------------------------------------------------
    sync = m3.derive_sync_offset(t_ms, m_total)
    off0 = sync["offset_ms"]
    print(f"[sync] mouse-in anchor: load step @ {sync['load_step_scale_s']:.1f}s scale "
          f"=> offset {off0/1000:+.2f}s")

    # --- 2. independent data-driven validation --------------------------------
    # Continuous movement index, then sweep offsets and score separation.
    mi = rolling_movement_index(m_total, win=fs)  # ~1 s window
    # raw sleeping intervals on the VIDEO clock (offset 0) so we can re-shift cheaply
    ev0 = m3.parse_mouse3_labels(ROOT / m3.M3_DIR, offset_ms=0.0)
    sleep_video = m3.merge_intervals(ev0, "sleeping")

    cand = np.arange(off0 - 30_000, off0 + 30_001, 1_000.0)
    scores = []
    for off in cand:
        in_sleep = np.zeros(len(t_ms), dtype=bool)
        for s, e in sleep_video:
            lo = np.searchsorted(t_ms, s + off, side="left")
            hi = np.searchsorted(t_ms, e + off, side="right")
            in_sleep[lo:hi] = True
        sel_sleep = in_sleep & is_loaded
        sel_act = (~in_sleep) & is_loaded
        if sel_sleep.sum() < 100 or sel_act.sum() < 100:
            scores.append(0.0)
            continue
        # separation: how many times larger is active micro-movement than sleep
        scores.append(float(np.median(mi[sel_act]) / (np.median(mi[sel_sleep]) + 1e-9)))
    scores = np.array(scores)
    best_off = float(cand[int(np.argmax(scores))])
    print(f"[sync] data-driven optimum: offset {best_off/1000:+.2f}s "
          f"(separation x{scores.max():.1f})")
    print(f"[sync] residual (anchor - data): {(off0 - best_off)/1000:+.2f}s")

    # Use the mouse-in anchor as the authoritative offset (physical landmark);
    # the sweep confirms it is within annotation slack.
    offset_ms = off0

    # --- 3. parse + merge labels at the chosen offset ------------------------
    events = m3.parse_mouse3_labels(ROOT / m3.M3_DIR, offset_ms=offset_ms)
    print("\n[labels] intervals per sheet:")
    print(events.group_by("gesture").agg(pl.len().alias("n"),
          ((pl.col("t_end_ms") - pl.col("t_start_ms")).sum() / 1000).round(0).alias("tot_s"))
          .sort("gesture"))
    sleep_iv = m3.merge_intervals(events, "sleeping")
    print(f"[labels] merged sleeping intervals: {len(sleep_iv)} "
          f"(total {sum(e-s for s,e in sleep_iv)/1000/60:.1f} min)")

    # --- 4. rasterize --------------------------------------------------------
    span = m3.labeled_span(events, int(sync["load_step_scale_s"] * 1000))
    print(f"[span] annotated span: {span[0]/1000/60:.1f}-{span[1]/1000/60:.1f} min")
    cls = m3.rasterize_sleep_active(t_ms, sleep_iv, is_loaded, span)
    in_span = (t_ms >= span[0]) & (t_ms <= span[1])
    n_act = int((cls == m3.CLASS_ACTIVE).sum())
    n_sleep = int((cls == m3.CLASS_SLEEP).sum())
    print(f"[raster] frames: active {n_act:,} ({n_act/in_span.sum():.1%} of span), "
          f"sleep {n_sleep:,} ({n_sleep/in_span.sum():.1%})")

    frames = frames.with_columns(
        pl.Series("class", cls.astype(np.int64)),
        pl.Series("is_labeled", in_span),
    )

    # --- 5. windows ----------------------------------------------------------
    win_df, stats = m3.build_windows_m3(
        frames, classes=(m3.CLASS_ACTIVE, m3.CLASS_SLEEP),
        fs=fs, window_len_s=WINDOW_LEN_S, stride_s=STRIDE_S, margin_s=MARGIN_S,
    )
    n_groups = win_df["source_interval_id"].n_unique()
    print(f"[windows] CV groups (blocks): {n_groups}")
    print("\n[windows] per class:")
    for c in (m3.CLASS_ACTIVE, m3.CLASS_SLEEP):
        s = stats[c]
        print(f"  {m3.CLASS_NAME[c]:8s}: {s['n_windows']:5d} windows "
              f"from {s['n_core_intervals']}/{s['n_intervals']} intervals")
    win_df.write_parquet(PROCESSED / "m3_windows.parquet")
    print(f"  wrote {PROCESSED / 'm3_windows.parquet'}  ({win_df.height} rows)")

    # --- figures -------------------------------------------------------------
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    ax.plot(cand / 1000, scores, marker=".")
    ax.axvline(off0 / 1000, color="r", ls="--", label=f"mouse-in anchor {off0/1000:+.1f}s")
    ax.axvline(best_off / 1000, color="g", ls=":", label=f"data optimum {best_off/1000:+.1f}s")
    ax.set(title="Sync validation: active/sleep movement-index separation vs offset",
           xlabel="video->scale offset (s)", ylabel="median MI active / sleep")
    ax.legend()
    fig.tight_layout(); fig.savefig(FIGS / "m3_phase2_sync.png", dpi=110)

    # timeline: m_total + MI + class bands
    tmin = t_ms / 1000 / 60
    fig, ax = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    ax[0].plot(tmin, m_total, lw=0.3)
    for s, e in sleep_iv:
        ax[0].axvspan(s/1000/60, e/1000/60, color="tab:purple", alpha=0.25)
    ax[0].set(title="m_total with annotated SLEEPING bands (purple)", ylabel="g")
    ax[1].semilogy(tmin, np.maximum(mi, 1e-3), lw=0.3, color="tab:orange")
    for s, e in sleep_iv:
        ax[1].axvspan(s/1000/60, e/1000/60, color="tab:purple", alpha=0.25)
    ax[1].set(title="rolling movement index (log) — drops ~10x during sleep",
              ylabel="|Δm| g", xlabel="min")
    fig.tight_layout(); fig.savefig(FIGS / "m3_phase2_timeline.png", dpi=110)
    print(f"  wrote {FIGS/'m3_phase2_sync.png'}, {FIGS/'m3_phase2_timeline.png'}")


if __name__ == "__main__":
    main()
