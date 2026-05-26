"""Phase 15 — Visual ground-truth alignment check.

Plots m_total with colour-banded gesture intervals at multiple scales:
  1. Full labelled span (~44 min)
  2. The single eating interval (a landmark — there's only one)
  3. The longest grooming bout
  4. The longest nesting bout
  5. The longest play_isopad bout
  6. A class-transition (where a non-grooming interval ends and a grooming begins, or similar)

User can scan for whether the signal envelope matches the labelled time windows.
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

from mousepipe.labels import CLASS_TO_GESTURE


CLASS_COLORS = {
    -1: "black",
    0:  "#dddddd",       # rest = light grey
    1:  "tab:blue",      # grooming
    2:  "tab:red",       # eating
    3:  "tab:green",     # nesting
    4:  "tab:orange",    # play_isopad
}
LABEL_NAMES = {-1: "ignore", 0: "rest", 1: "grooming", 2: "eating", 3: "nesting", 4: "play_isopad"}


def runs_of_class(t_s: np.ndarray, cls: np.ndarray, target: int) -> list[tuple[float, float]]:
    """Return [(t0, t1), …] for contiguous runs of class==target."""
    m = cls == target
    if not m.any():
        return []
    diff = np.diff(m.astype(np.int8))
    starts = np.where(diff == 1)[0] + 1
    ends   = np.where(diff == -1)[0] + 1
    if m[0]:  starts = np.concatenate(([0], starts))
    if m[-1]: ends   = np.concatenate((ends, [len(m)]))
    return [(float(t_s[s]), float(t_s[min(e, len(t_s)-1)])) for s, e in zip(starts, ends)]


def shade_classes(ax, t_s, cls, alpha=0.25):
    for c, color in CLASS_COLORS.items():
        if c in (0,):  # don't shade rest
            continue
        for (lo, hi) in runs_of_class(t_s, cls, c):
            ax.axvspan(lo, hi, color=color, alpha=alpha, linewidth=0)


def gesture_intervals_table(df: pl.DataFrame) -> pl.DataFrame:
    """Return one row per labelled gesture interval (class>0)."""
    cls = df["class"].to_numpy()
    t   = df["t_ms"].to_numpy() / 1000.0
    rows = []
    for c in (1, 2, 3, 4):
        for (s, e) in runs_of_class(t, cls, c):
            rows.append({"class": int(c), "gesture": LABEL_NAMES[c],
                         "t_start_s": s, "t_end_s": e, "duration_s": e - s})
    return pl.DataFrame(rows)


def main():
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"

    df = pl.read_parquet(interim / "phase7_labeled.parquet")
    t_s = df["t_ms"].to_numpy() / 1000.0
    m   = df["m_total"].to_numpy()
    cls = df["class"].to_numpy()
    lab = df["is_labeled"].to_numpy()

    intervals = gesture_intervals_table(df)
    print("All gesture intervals on scale clock:")
    with pl.Config(tbl_rows=200):
        print(intervals.sort("t_start_s"))

    # Pick anchor intervals for zoom panels
    longest = {c: intervals.filter(pl.col("class") == c).sort("duration_s", descending=True).head(1)
               for c in (1, 2, 3, 4)}
    # Find a class-boundary zoom: two different gesture classes within 30 s of each other
    sorted_iv = intervals.sort("t_start_s").to_dicts()
    transition = None
    for i, a in enumerate(sorted_iv):
        for b in sorted_iv[i+1:]:
            if b["t_start_s"] > a["t_end_s"] + 30:
                break
            if b["class"] != a["class"]:
                transition = (a, b)
                break
        if transition:
            break

    # === Figure ===
    fig = plt.figure(figsize=(15, 16), constrained_layout=True)
    gs = fig.add_gridspec(7, 1, height_ratios=[2.2, 1.5, 1.5, 1.5, 1.5, 1.5, 0.4])

    # ---- Panel 0: full labelled span ----
    ax0 = fig.add_subplot(gs[0])
    lab_mask = lab
    ax0.plot(t_s[lab_mask] / 60.0, m[lab_mask], lw=0.3, color="black", alpha=0.7)
    shade_classes(ax0, t_s / 60.0, cls, alpha=0.30)
    # also shade labelled-span bounds
    lo_s, hi_s = float(t_s[lab_mask].min()), float(t_s[lab_mask].max())
    ax0.set_xlim(lo_s/60, hi_s/60)
    ax0.set_ylim(-5, 35)
    ax0.set_title("Phase 15 — Full labelled span: m_total with colour-banded gesture intervals")
    ax0.set_xlabel("scale clock time (min)"); ax0.set_ylabel("m_total (g)")
    ax0.grid(alpha=0.3)

    # ---- Panel 1: eating (the unique landmark) ----
    ax1 = fig.add_subplot(gs[1])
    eat = longest[2].row(0, named=True)
    lo, hi = eat["t_start_s"] - 20, eat["t_end_s"] + 20
    m_zoom = (t_s > lo) & (t_s < hi)
    ax1.plot(t_s[m_zoom], m[m_zoom], lw=0.6, color="black")
    shade_classes(ax1, t_s, cls, alpha=0.30)
    ax1.set_xlim(lo, hi)
    ax1.set_title(f"Zoom — EATING (the only one) — labelled scale_t {eat['t_start_s']:.1f}…{eat['t_end_s']:.1f} s "
                  f"(duration {eat['duration_s']:.0f} s)  — KEY LANDMARK for sync check")
    ax1.set_xlabel("scale clock time (s)"); ax1.set_ylabel("m_total (g)")
    ax1.grid(alpha=0.3)

    # ---- Panel 2: longest grooming ----
    ax2 = fig.add_subplot(gs[2])
    g = longest[1].row(0, named=True)
    lo, hi = g["t_start_s"] - 10, g["t_end_s"] + 10
    m_zoom = (t_s > lo) & (t_s < hi)
    ax2.plot(t_s[m_zoom], m[m_zoom], lw=0.5, color="black")
    shade_classes(ax2, t_s, cls, alpha=0.30)
    ax2.set_xlim(lo, hi)
    ax2.set_title(f"Zoom — longest GROOMING — scale_t {g['t_start_s']:.1f}…{g['t_end_s']:.1f} s "
                  f"({g['duration_s']:.0f} s)")
    ax2.set_xlabel("scale clock time (s)"); ax2.set_ylabel("m_total (g)")
    ax2.grid(alpha=0.3)

    # ---- Panel 3: longest nesting ----
    ax3 = fig.add_subplot(gs[3])
    n = longest[3].row(0, named=True)
    lo, hi = n["t_start_s"] - 10, n["t_end_s"] + 10
    m_zoom = (t_s > lo) & (t_s < hi)
    ax3.plot(t_s[m_zoom], m[m_zoom], lw=0.5, color="black")
    shade_classes(ax3, t_s, cls, alpha=0.30)
    ax3.set_xlim(lo, hi)
    ax3.set_title(f"Zoom — longest NESTING — scale_t {n['t_start_s']:.1f}…{n['t_end_s']:.1f} s "
                  f"({n['duration_s']:.0f} s)")
    ax3.set_xlabel("scale clock time (s)"); ax3.set_ylabel("m_total (g)")
    ax3.grid(alpha=0.3)

    # ---- Panel 4: longest play_isopad ----
    ax4 = fig.add_subplot(gs[4])
    p = longest[4].row(0, named=True)
    lo, hi = p["t_start_s"] - 10, p["t_end_s"] + 10
    m_zoom = (t_s > lo) & (t_s < hi)
    ax4.plot(t_s[m_zoom], m[m_zoom], lw=0.5, color="black")
    shade_classes(ax4, t_s, cls, alpha=0.30)
    ax4.set_xlim(lo, hi)
    ax4.set_title(f"Zoom — longest PLAY_ISOPAD — scale_t {p['t_start_s']:.1f}…{p['t_end_s']:.1f} s "
                  f"({p['duration_s']:.0f} s)")
    ax4.set_xlabel("scale clock time (s)"); ax4.set_ylabel("m_total (g)")
    ax4.grid(alpha=0.3)

    # ---- Panel 5: class transition ----
    ax5 = fig.add_subplot(gs[5])
    if transition is not None:
        a, b = transition
        lo, hi = a["t_start_s"] - 5, b["t_end_s"] + 5
        m_zoom = (t_s > lo) & (t_s < hi)
        ax5.plot(t_s[m_zoom], m[m_zoom], lw=0.5, color="black")
        shade_classes(ax5, t_s, cls, alpha=0.30)
        ax5.set_xlim(lo, hi)
        ax5.set_title(f"Zoom — class transition: {a['gesture']} → {b['gesture']} "
                      f"(scale_t {a['t_start_s']:.0f}…{b['t_end_s']:.0f} s)")
        ax5.set_xlabel("scale clock time (s)"); ax5.set_ylabel("m_total (g)")
        ax5.grid(alpha=0.3)

    # ---- Legend strip ----
    ax_leg = fig.add_subplot(gs[6])
    ax_leg.axis("off")
    handles = [Patch(facecolor=CLASS_COLORS[c], alpha=0.6, label=LABEL_NAMES[c])
               for c in (1, 2, 3, 4, -1)]
    handles.append(Patch(facecolor="none", edgecolor="black", label="rest (no shading)"))
    ax_leg.legend(handles=handles, loc="center", ncol=6, fontsize=11)

    fig_path = figures / "phase15_alignment_check.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"\nwrote {fig_path}")

    # ALSO: write the gesture interval table for the user to reference numerically
    intervals.write_csv(interim / "phase15_gesture_intervals.csv")
    print(f"wrote {interim / 'phase15_gesture_intervals.csv'}")


if __name__ == "__main__":
    main()
