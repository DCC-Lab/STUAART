"""Phase 7 — L7 ground-truth parsing, alignment, and rasterization.

Outputs:
  data/interim/phase7_gesture_events_raw.csv   — every interval as parsed (after sync, before merge)
  data/interim/phase7_within_sheet_merges.csv  — log of merges performed in L7b
  data/interim/phase7_gesture_events.csv       — final tidy event table (post-merge)
  data/interim/phase7_overlap_regions.csv      — cross-gesture overlap regions (class = -1)
  data/interim/phase7_class_summary.csv        — frame count per class
  data/interim/phase7_labeled.parquet          — phase 6 + class + is_labeled per frame
  figures/phase7_labels.png                    — labeled timeline + zooms + class bars
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from mousepipe import GT_XLS, SYNC_OFFSET_MS
from mousepipe.labels import (
    parse_xls, sort_and_merge_within_sheet, cross_gesture_overlaps,
    rasterize, labeled_span_mask,
    GESTURE_TO_CLASS, CLASS_TO_GESTURE, CLASS_IGNORE, CLASS_NULL,
    LABELED_START_MS, LABELED_END_MS,
)


def main() -> None:
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    # L7a — parse
    events_raw = parse_xls(ROOT / GT_XLS)
    print(f"parsed {events_raw.height} intervals from XLS")
    print(f"  gesture counts: {dict(events_raw.group_by('gesture').len().iter_rows())}")
    events_raw.write_csv(interim / "phase7_gesture_events_raw.csv")

    # L7b — sort + merge within-sheet overlaps
    events, merge_log = sort_and_merge_within_sheet(events_raw)
    print(f"\nmerged {merge_log.height} within-sheet overlaps")
    if merge_log.height:
        print(merge_log)
    merge_log.write_csv(interim / "phase7_within_sheet_merges.csv")
    events.write_csv(interim / "phase7_gesture_events.csv")
    print(f"  final tidy events: {events.height} rows")

    # L7d — cross-gesture overlaps
    overlaps = cross_gesture_overlaps(events)
    print(f"\ncross-gesture overlap regions: {overlaps.height}")
    if overlaps.height:
        print(overlaps)
    overlaps.write_csv(interim / "phase7_overlap_regions.csv")

    # Load resampled grid
    grid = pl.read_parquet(interim / "phase6_resampled.parquet")
    t_ms = grid["t_ms"].to_numpy()
    print(f"\ngrid: {grid.height:,} frames @ 80 Hz")

    # L7e — rasterize
    cls = rasterize(t_ms, events, overlaps)

    # L7f — labelled span mask
    is_lab = labeled_span_mask(t_ms)

    print()
    print("Class counts on full grid:")
    for c in (CLASS_IGNORE, CLASS_NULL, 1, 2, 3, 4):
        n = int((cls == c).sum())
        n_lab = int(((cls == c) & is_lab).sum())
        gesture = CLASS_TO_GESTURE.get(c, "?")
        print(f"  class {c:+d}  ({gesture:>11}): {n:>8,} total   {n_lab:>8,} in labelled span")
    n_lab = int(is_lab.sum())
    print(f"  is_labeled                : {n_lab:,} / {len(t_ms):,}  ({100*n_lab/len(t_ms):.2f} %)")

    # Class summary CSV
    summary_rows = []
    for c, g in CLASS_TO_GESTURE.items():
        summary_rows.append({
            "class": c, "gesture": g,
            "n_frames_total": int((cls == c).sum()),
            "n_frames_labeled": int(((cls == c) & is_lab).sum()),
        })
    summary = pl.DataFrame(summary_rows).sort("class")
    summary.write_csv(interim / "phase7_class_summary.csv")

    # Assemble output frame
    out = grid.with_columns(
        pl.Series("class", cls, dtype=pl.Int8),
        pl.Series("is_labeled", is_lab, dtype=pl.Boolean),
    )
    out_path = interim / "phase7_labeled.parquet"
    out.write_parquet(out_path)
    print(f"\nwrote {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")

    # ----- Figure -----
    t_s = t_ms / 1000.0
    m_total = grid["m_total"].to_numpy()

    color_map = {-1: "black", 0: "lightgrey", 1: "C0", 2: "C3", 3: "C2", 4: "C1"}
    label_map = {-1: "ignore", 0: "none", 1: "grooming", 2: "eating", 3: "nesting", 4: "play_isopad"}

    fig, axes = plt.subplots(4, 1, figsize=(14, 13), constrained_layout=True)

    # Panel 1: full labelled span — m_total + class strip below
    ax = axes[0]
    lab_mask = is_lab
    ax.plot(t_s[lab_mask] / 60, m_total[lab_mask], lw=0.3, color="grey", alpha=0.7)
    # class strip: a row of coloured points at y=-3
    for c, color in color_map.items():
        m = (cls == c) & lab_mask
        if m.any():
            ax.scatter(t_s[m] / 60, np.full(m.sum(), -3.0), s=2, color=color)
    ax.axvspan(LABELED_START_MS / 60_000, LABELED_END_MS / 60_000, color="yellow", alpha=0.05,
               label="labelled span")
    ax.set_ylim(-6, 35)
    ax.set_title("Phase 7 — Labelled span: m_total (grey) + class strip at y=-3")
    ax.set_xlabel("scale clock time (min)"); ax.set_ylabel("m_total (g)")
    legend = [Patch(facecolor=c, label=label_map[k]) for k, c in color_map.items()]
    ax.legend(handles=legend, loc="upper right", ncol=3, fontsize=8)
    ax.grid(alpha=0.3)

    # Panel 2: zoom on the long grooming bout 1564–1628 s (video), so 1607.5–1671.5 s on scale
    ax = axes[1]
    z_lo, z_hi = 1600, 1680
    m = (t_s > z_lo) & (t_s < z_hi)
    ax.plot(t_s[m], m_total[m], lw=0.5, color="grey")
    # Coloured background by class
    classes_here = cls[m]
    times_here   = t_s[m]
    for c, color in color_map.items():
        if c == 0: continue
        in_c = classes_here == c
        if in_c.any():
            # find contiguous runs
            change = np.diff(in_c.astype(np.int8))
            starts = np.concatenate(([0], np.where(change == 1)[0] + 1))
            ends   = np.concatenate((np.where(change == -1)[0] + 1, [len(in_c)]))
            for s, e in zip(starts, ends):
                if not in_c[s]: continue
                ax.axvspan(times_here[s], times_here[min(e, len(times_here)-1)], color=color, alpha=0.25)
    ax.set_title(f"Phase 7 — Zoom on long grooming bout (scale_t {z_lo}–{z_hi} s)")
    ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("m_total (g)")
    ax.legend(handles=legend, loc="upper right", ncol=3, fontsize=8); ax.grid(alpha=0.3)

    # Panel 3: zoom on a cross-gesture overlap region
    if overlaps.height:
        ov = overlaps.sort("t_start_ms").row(0, named=True)
        ax = axes[2]
        c_lo = ov["t_start_ms"] / 1000 - 5
        c_hi = ov["t_end_ms"]   / 1000 + 5
        m = (t_s > c_lo) & (t_s < c_hi)
        ax.plot(t_s[m], m_total[m], lw=0.5, color="grey")
        classes_here = cls[m]; times_here = t_s[m]
        for c, color in color_map.items():
            if c == 0: continue
            in_c = classes_here == c
            if in_c.any():
                change = np.diff(in_c.astype(np.int8))
                starts = np.concatenate(([0], np.where(change == 1)[0] + 1))
                ends   = np.concatenate((np.where(change == -1)[0] + 1, [len(in_c)]))
                for s, e in zip(starts, ends):
                    if not in_c[s]: continue
                    ax.axvspan(times_here[s], times_here[min(e, len(times_here)-1)], color=color, alpha=0.30)
        ax.set_title(f"Phase 7 — Zoom on first cross-gesture overlap "
                     f"({ov['gesture_a']} × {ov['gesture_b']}, marked class=-1)")
        ax.set_xlabel("scale clock time (s)"); ax.set_ylabel("m_total (g)")
        ax.legend(handles=legend, loc="upper right", ncol=3, fontsize=8); ax.grid(alpha=0.3)

    # Panel 4: bar of frame counts per class (in labelled span)
    ax = axes[3]
    classes = [-1, 0, 1, 2, 3, 4]
    counts  = [int(((cls == c) & is_lab).sum()) for c in classes]
    durations_s = [c * 12.5 / 1000 for c in counts]
    bars = ax.bar(range(len(classes)), counts, color=[color_map[c] for c in classes],
                  tick_label=[f"{c}\n{label_map[c]}" for c in classes])
    for b, d in zip(bars, durations_s):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(), f"{int(d)} s",
                ha="center", va="bottom", fontsize=9)
    ax.set_title("Phase 7 — Frame counts per class (labelled span only)")
    ax.set_ylabel("frames @ 80 Hz")
    ax.set_yscale("log")
    ax.grid(alpha=0.3, axis="y", which="both")

    fig_path = figures / "phase7_labels.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
