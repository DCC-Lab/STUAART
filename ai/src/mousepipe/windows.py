"""L8 — Build training windows from the labelled 80 Hz grid.

Strategy:
- Trim a fixed margin from each end of every gesture interval (handles sync
  uncertainty + mechanical settling + annotator imprecision).
- Drop intervals whose remaining "core" is shorter than the window length.
- Emit overlapping windows of fixed length and stride inside each core.
- For class 0 (rest), only emit windows whose entire span is at least `margin`
  away from any non-rest frame — so we never train a "rest" window on
  gesture-edge content.

Features: m_total only (no per-cell features — see feedback memory).
"""
from __future__ import annotations
import numpy as np
import polars as pl

from . import TARGET_HZ
from .labels import CLASS_NULL, CLASS_IGNORE

WINDOW_LEN_S = 2.0
STRIDE_S     = 0.5
MARGIN_S     = 0.5


def _events_from_class(cls: np.ndarray, target_class: int) -> list[tuple[int, int]]:
    """Return list of (start_idx, end_idx_exclusive) for runs of `target_class`."""
    if len(cls) == 0:
        return []
    m = cls == target_class
    if not m.any():
        return []
    change = np.diff(m.astype(np.int8))
    rises = np.where(change == 1)[0] + 1
    falls = np.where(change == -1)[0] + 1
    if m[0]:
        rises = np.concatenate(([0], rises))
    if m[-1]:
        falls = np.concatenate((falls, [len(m)]))
    return list(zip(rises.tolist(), falls.tolist()))


def build_windows(
    df: pl.DataFrame,
    classes_to_window: tuple[int, ...] = (1, 2, 3, 4),  # gesture classes
    include_rest: bool = True,
    window_len_s: float = WINDOW_LEN_S,
    stride_s: float = STRIDE_S,
    margin_s: float = MARGIN_S,
    fs: int = TARGET_HZ,
) -> tuple[pl.DataFrame, dict]:
    """Slice the 80 Hz frame stream into training windows.

    Inputs in df: `t_ms`, `m_total`, `class`, `is_labeled`, `segment_id`.

    Returns (windows_df, stats):
      windows_df has one row per window with columns:
        t_start_ms, t_end_ms, label, signal[N]  (N = window_len_s * fs)
      stats: per-class counts of intervals, core-intervals (after margin), windows.
    """
    win_n    = int(round(window_len_s * fs))
    stride_n = int(round(stride_s    * fs))
    margin_n = int(round(margin_s    * fs))

    # Restrict to labelled span; segments are honoured by the run finder below.
    df = df.filter(pl.col("is_labeled")).sort("t_ms")
    t_ms = df["t_ms"].to_numpy()
    m_total = df["m_total"].to_numpy().astype(np.float32)
    cls = df["class"].to_numpy().astype(np.int8)
    seg = df["segment_id"].to_numpy()

    # Find a "non-rest" mask used to enforce the rest-window margin. We treat
    # class -1 (ignore) the same as a gesture for distance purposes — we don't
    # want rest windows to touch overlap regions either.
    non_rest = cls != CLASS_NULL

    # Pre-compute distance from each frame to the nearest non-rest frame.
    # Vectorised via cumulative dilation: any frame within margin_n samples of
    # a non-rest frame is "near a boundary" and not a clean rest frame.
    near_boundary = np.zeros_like(cls, dtype=bool)
    if non_rest.any():
        idx = np.arange(len(cls))
        # Mark all non-rest frames as near-boundary.
        near_boundary |= non_rest
        # Extend boundary mask by margin_n samples in both directions.
        for shift in range(1, margin_n + 1):
            near_boundary[shift:]  |= non_rest[:-shift]
            near_boundary[:-shift] |= non_rest[shift:]

    rows = []
    stats: dict[int, dict] = {}
    interval_counter = 0

    # Gesture-class windows
    for c in classes_to_window:
        events = _events_from_class(cls, c)
        n_events = len(events)
        n_core   = 0
        n_win    = 0
        for s, e in events:
            # Must not cross a segment boundary
            if seg[s] != seg[e - 1]:
                continue
            core_s = s + margin_n
            core_e = e - margin_n
            if core_e - core_s < win_n:
                continue
            n_core += 1
            interval_counter += 1
            for ws in range(core_s, core_e - win_n + 1, stride_n):
                rows.append({
                    "t_start_ms": int(t_ms[ws]),
                    "t_end_ms":   int(t_ms[ws + win_n - 1]),
                    "label": c,
                    "source_interval_id": interval_counter,
                    "signal": m_total[ws : ws + win_n].tolist(),
                })
                n_win += 1
        stats[c] = {"n_intervals": n_events, "n_core_intervals": n_core, "n_windows": n_win}

    # Rest (class 0) windows: walk runs of NOT-near-boundary AND class==0 AND
    # within a single segment.
    if include_rest:
        clean_rest = (cls == CLASS_NULL) & (~near_boundary)
        n_events = 0
        n_core   = 0
        n_win    = 0
        for s, e in _events_from_class(clean_rest.astype(np.int8), 1):
            n_events += 1
            if seg[s] != seg[e - 1]:
                continue
            if e - s < win_n:
                continue
            n_core += 1
            interval_counter += 1
            for ws in range(s, e - win_n + 1, stride_n):
                rows.append({
                    "t_start_ms": int(t_ms[ws]),
                    "t_end_ms":   int(t_ms[ws + win_n - 1]),
                    "label": CLASS_NULL,
                    "source_interval_id": interval_counter,
                    "signal": m_total[ws : ws + win_n].tolist(),
                })
                n_win += 1
        stats[CLASS_NULL] = {"n_intervals": n_events, "n_core_intervals": n_core, "n_windows": n_win}

    win_df = pl.DataFrame(rows, schema={
        "t_start_ms": pl.Int64,
        "t_end_ms":   pl.Int64,
        "label":      pl.Int8,
        "source_interval_id": pl.Int32,
        "signal":     pl.List(pl.Float32),
    })
    return win_df, stats
