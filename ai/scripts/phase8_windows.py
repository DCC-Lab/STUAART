"""Phase 8 — L8 windowing for classification.

Trims onset/offset of every gesture (margin = 500 ms) before extracting
overlapping 2-s windows at 0.5-s stride. Rest windows must be at least
500 ms away from any non-rest frame.

Outputs:
  data/interim/phase8_window_stats.csv     — per-class window counts
  data/interim/phase8_interval_durations.csv — all intervals + flag for "made the cut"
  data/processed/windows_train.parquet     — final training windows (signal[160])
  figures/phase8_windows.png               — duration distribution + per-class samples
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt

from mousepipe import TARGET_HZ
from mousepipe.labels import CLASS_TO_GESTURE
from mousepipe.windows import build_windows, WINDOW_LEN_S, STRIDE_S, MARGIN_S


def main() -> None:
    interim   = ROOT / "data" / "interim"
    processed = ROOT / "data" / "processed"
    figures   = ROOT / "figures"
    processed.mkdir(parents=True, exist_ok=True)

    print(f"window={WINDOW_LEN_S}s ({int(WINDOW_LEN_S*TARGET_HZ)} samples)  stride={STRIDE_S}s  margin={MARGIN_S}s")

    df = pl.read_parquet(interim / "phase7_labeled.parquet")
    print(f"input grid: {df.height:,} frames; labelled span: {int(df['is_labeled'].sum()):,}")

    windows, stats = build_windows(df)

    print()
    print(f"{'class':>6}  {'gesture':>12}  {'n_intervals':>11}  {'n_with_core':>11}  {'n_windows':>9}")
    for c in sorted(stats.keys()):
        s = stats[c]
        print(f"{c:>6}  {CLASS_TO_GESTURE.get(c,'?'):>12}  "
              f"{s['n_intervals']:>11}  {s['n_core_intervals']:>11}  {s['n_windows']:>9}")
    print(f"\ntotal windows: {windows.height:,}")

    # Save stats
    pl.DataFrame([{"class": c, "gesture": CLASS_TO_GESTURE.get(c,"?"), **s} for c, s in stats.items()]
                 ).sort("class").write_csv(interim / "phase8_window_stats.csv")

    # Save all interval durations with "made cut" flag
    cls = df["class"].to_numpy()
    t   = df["t_ms"].to_numpy()
    seg = df["segment_id"].to_numpy()
    is_lab = df["is_labeled"].to_numpy()
    min_dur_ms = int((WINDOW_LEN_S + 2 * MARGIN_S) * 1000)
    rows = []
    for c in (1, 2, 3, 4):
        m = (cls == c) & is_lab
        if not m.any(): continue
        change = np.diff(m.astype(np.int8))
        rises = np.where(change == 1)[0] + 1
        falls = np.where(change == -1)[0] + 1
        if m[0]: rises = np.concatenate(([0], rises))
        if m[-1]: falls = np.concatenate((falls, [len(m)]))
        for s, e in zip(rises, falls):
            dur_ms = int(t[e-1] - t[s])
            rows.append({
                "class": int(c), "gesture": CLASS_TO_GESTURE[c],
                "t_start_ms": int(t[s]), "t_end_ms": int(t[e-1]),
                "duration_ms": dur_ms,
                "made_cut": dur_ms >= min_dur_ms,
                "segment_id": int(seg[s]),
            })
    dur_df = pl.DataFrame(rows).sort(["class", "t_start_ms"])
    dur_df.write_csv(interim / "phase8_interval_durations.csv")
    print(f"\nintervals ≥ {min_dur_ms} ms: {int(dur_df['made_cut'].sum())} / {dur_df.height}")

    # Save windows
    out_path = processed / "windows_train.parquet"
    windows.write_parquet(out_path)
    print(f"wrote {out_path}  ({out_path.stat().st_size/1e6:.2f} MB)")

    # ----- Figure -----
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)

    # (0,0) Interval duration histogram per class
    ax = axes[0, 0]
    bins = np.arange(0, 70, 1)
    for c, color in zip((1, 2, 3, 4), ("C0", "C3", "C2", "C1")):
        d = dur_df.filter(pl.col("class") == c)["duration_ms"].to_numpy() / 1000.0
        ax.hist(d, bins=bins, alpha=0.5, color=color, label=f"{CLASS_TO_GESTURE[c]} (n={len(d)})")
    ax.axvline((WINDOW_LEN_S + 2 * MARGIN_S), color="black", ls="--", lw=1,
               label=f"min for window ({WINDOW_LEN_S + 2*MARGIN_S}s)")
    ax.set_xlabel("interval duration (s)"); ax.set_ylabel("count")
    ax.set_title("Phase 8 — Gesture interval durations; dashed line = min for one window")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # (0,1) Per-class window counts
    ax = axes[0, 1]
    classes = sorted(stats.keys())
    counts  = [stats[c]["n_windows"] for c in classes]
    colors  = {0: "lightgrey", 1: "C0", 2: "C3", 3: "C2", 4: "C1"}
    ax.bar(range(len(classes)), counts,
           color=[colors[c] for c in classes],
           tick_label=[f"{c}\n{CLASS_TO_GESTURE[c]}" for c in classes])
    for i, n in enumerate(counts):
        ax.text(i, n, f"{n:,}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("# windows"); ax.set_yscale("log")
    ax.set_title(f"Phase 8 — Training windows per class ({WINDOW_LEN_S}s, stride {STRIDE_S}s)")
    ax.grid(alpha=0.3, axis="y", which="both")

    # (1,0) Sample of grooming windows
    ax = axes[1, 0]
    fs = TARGET_HZ
    n_samples_per_class = 6
    win_n = int(WINDOW_LEN_S * fs)
    t_w = np.arange(win_n) / fs
    if (windows["label"] == 1).any():
        grooms = windows.filter(pl.col("label") == 1)
        n_show = min(n_samples_per_class, grooms.height)
        idx = np.linspace(0, grooms.height - 1, n_show).astype(int)
        for i in idx:
            sig = np.array(grooms["signal"][int(i)])
            ax.plot(t_w, sig, lw=0.7, alpha=0.7)
    ax.set_title("Phase 8 — 6 grooming windows (m_total over 2 s)")
    ax.set_xlabel("time within window (s)"); ax.set_ylabel("m_total (g)")
    ax.grid(alpha=0.3)

    # (1,1) Sample of rest windows
    ax = axes[1, 1]
    if (windows["label"] == 0).any():
        rests = windows.filter(pl.col("label") == 0)
        n_show = min(n_samples_per_class, rests.height)
        idx = np.linspace(0, rests.height - 1, n_show).astype(int)
        for i in idx:
            sig = np.array(rests["signal"][int(i)])
            ax.plot(t_w, sig, lw=0.7, alpha=0.7)
    ax.set_title("Phase 8 — 6 rest windows (m_total over 2 s)")
    ax.set_xlabel("time within window (s)"); ax.set_ylabel("m_total (g)")
    ax.grid(alpha=0.3)

    fig_path = figures / "phase8_windows.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
