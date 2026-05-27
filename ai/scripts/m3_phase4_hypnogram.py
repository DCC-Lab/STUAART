"""Mouse3 phase 4 — whole-recording sleep/wake scoring (the deployable detector).

The "simplest accurate method" applied end-to-end:
  1. rolling movement index  = median |Δm_total| over a 4 s sliding window
  2. threshold               = sleep if MI < CUT (learned in phase 3: 0.107 g/sample)
  3. min-bout hysteresis     = drop sleep/wake runs shorter than MIN_BOUT_S
                               (reuses presence.remove_short_runs)

Produces a hypnogram over the full recording, overlays the annotated sleeping
bouts (valid only inside the annotated span), and reports bout statistics +
frame-level agreement.

Output: data/processed/m3_sleep_bouts.csv
        figures/m3_phase4_hypnogram.png
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy.ndimage import median_filter
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mousepipe import mouse3 as m3
from mousepipe.presence import remove_short_runs

INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
FIGS = ROOT / "figures"

CUT = 0.107          # g/sample — Youden threshold from phase 3
MIN_BOUT_S = 10.0    # ignore sleep/wake flips shorter than this (real bouts are >= 13 s)
WIN_S = 4.0


def runs_of(mask: np.ndarray, t_ms: np.ndarray) -> list[tuple[int, int]]:
    """Return (start_ms, end_ms) for each True run."""
    if not mask.any():
        return []
    d = np.diff(mask.astype(np.int8))
    starts = np.where(d == 1)[0] + 1
    ends = np.where(d == -1)[0] + 1
    if mask[0]:
        starts = np.r_[0, starts]
    if mask[-1]:
        ends = np.r_[ends, len(mask)]
    return [(int(t_ms[s]), int(t_ms[e - 1])) for s, e in zip(starts, ends)]


def main() -> None:
    frames = pl.read_parquet(INTERIM / "m3_frames.parquet").sort("t_ms")
    t_ms = frames["t_ms"].to_numpy().astype(np.int64)
    m_total = frames["m_total"].to_numpy().astype(np.float64)
    is_loaded = frames["is_loaded"].to_numpy().astype(bool)
    fs = m3.TARGET_HZ_M3

    # --- detector ------------------------------------------------------------
    d = np.abs(np.diff(m_total, prepend=m_total[0]))
    mi = median_filter(d, size=int(WIN_S * fs), mode="nearest")
    raw_sleep = (mi < CUT) & is_loaded            # off-scale is never sleep
    # hysteresis: drop sleep/wake flips shorter than MIN_BOUT_S, then keep only
    # sleep bouts that survive the min-duration filter (clean, non-fragmented).
    smoothed = remove_short_runs(raw_sleep, t_ms, min_duration_ms=int(MIN_BOUT_S * 1000))
    sleep = np.zeros_like(smoothed)
    for s, e in runs_of(smoothed, t_ms):
        if (e - s) >= MIN_BOUT_S * 1000:
            lo, hi = np.searchsorted(t_ms, s), np.searchsorted(t_ms, e, side="right")
            sleep[lo:hi] = True

    # --- ground truth (annotated sleeping) -----------------------------------
    sync = m3.derive_sync_offset(t_ms, m_total)
    events = m3.parse_mouse3_labels(ROOT / m3.M3_DIR, offset_ms=sync["offset_ms"])
    sleep_iv = m3.merge_intervals(events, "sleeping")
    span = m3.labeled_span(events, int(sync["load_step_scale_s"] * 1000))
    gt_sleep = np.zeros(len(t_ms), dtype=bool)
    for s, e in sleep_iv:
        lo, hi = np.searchsorted(t_ms, s), np.searchsorted(t_ms, e, side="right")
        gt_sleep[lo:hi] = True

    # --- agreement inside the annotated span (scored frames only) ------------
    scored = (t_ms >= span[0]) & (t_ms <= span[1]) & is_loaded
    y_true = gt_sleep[scored].astype(int)
    y_pred = sleep[scored].astype(int)
    bacc = balanced_accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred)
    print(f"[detector] CUT={CUT} g/sample, min-bout {MIN_BOUT_S}s")
    print(f"[in-span agreement] balanced acc {bacc:.3f}")
    print(f"  confusion (rows true active/sleep, cols pred active/sleep):\n{cm}")
    gt_min = gt_sleep[scored].sum() / fs / 60
    pr_min = sleep[scored].sum() / fs / 60
    print(f"  annotated sleep in span: {gt_min:.1f} min;  detected: {pr_min:.1f} min")

    # --- bout statistics (whole recording) -----------------------------------
    bouts = runs_of(sleep, t_ms)
    durs = np.array([(e - s) / 1000 for s, e in bouts])
    durs = durs[durs > 0]
    total_min = sleep.sum() / fs / 60
    rec_min = (t_ms.max() - t_ms.min()) / 1000 / 60
    print(f"\n[whole recording] {len(bouts)} detected sleep bouts, "
          f"total {total_min:.1f} min ({total_min/rec_min:.1%} of recording)")
    if len(durs):
        print(f"  bout durations s: median {np.median(durs):.0f}, "
              f"max {durs.max():.0f}, >60s: {(durs>60).sum()}")
    # first sleep onset (sleep latency) relative to mouse-in
    onset_min = (bouts[0][0] - span[0]) / 1000 / 60 if bouts else float("nan")
    print(f"  first sustained sleep onset: {bouts[0][0]/1000/60:.1f} min "
          f"({onset_min:.1f} min after mouse-in)" if bouts else "")

    pl.DataFrame({"start_ms": [b[0] for b in bouts], "end_ms": [b[1] for b in bouts],
                  "duration_s": [(b[1]-b[0])/1000 for b in bouts]}
                 ).write_csv(PROCESSED / "m3_sleep_bouts.csv")

    # --- figure --------------------------------------------------------------
    tmin = t_ms / 1000 / 60
    fig, ax = plt.subplots(3, 1, figsize=(15, 8), sharex=True)
    ax[0].plot(tmin, m_total, lw=0.25)
    ax[0].axvspan(span[0]/1000/60, span[1]/1000/60, color="grey", alpha=0.08)
    ax[0].set(title="Mouse3 m_total (grey = annotated span)", ylabel="g")

    ax[1].semilogy(tmin, np.maximum(mi, 1e-3), lw=0.25, color="tab:orange")
    ax[1].axhline(CUT, color="r", ls="--", label=f"cut {CUT}")
    ax[1].set(title="rolling movement index", ylabel="|Δm| g"); ax[1].legend(loc="upper right")

    ax[2].fill_between(tmin, 0, gt_sleep.astype(int), step="mid",
                       color="tab:purple", alpha=0.5, label="annotated sleep")
    ax[2].fill_between(tmin, 0, -sleep.astype(int), step="mid",
                       color="tab:green", alpha=0.6, label="detected sleep")
    ax[2].axvspan(span[0]/1000/60, span[1]/1000/60, color="grey", alpha=0.08)
    ax[2].set(title=f"Hypnogram — in-span balanced acc {bacc:.3f}",
              xlabel="min", yticks=[-1, 0, 1], yticklabels=["detected", "wake", "annotated"])
    ax[2].legend(loc="upper right")
    fig.tight_layout(); fig.savefig(FIGS / "m3_phase4_hypnogram.png", dpi=110)
    print(f"\nwrote {PROCESSED/'m3_sleep_bouts.csv'}, {FIGS/'m3_phase4_hypnogram.png'}")


if __name__ == "__main__":
    main()
