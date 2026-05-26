"""L7 — Ground-truth processing & join.

Parses the XLS gesture annotations, applies the +43.5 s video→scale sync,
sorts and merges within-sheet overlaps, detects cross-gesture overlaps,
then rasterizes per-frame class labels onto the 80 Hz uniform grid.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import polars as pl
import xlrd

from . import SYNC_OFFSET_MS

DAY_SECONDS = 86400.0

# Class encoding
CLASS_IGNORE = -1
CLASS_NULL   = 0
GESTURE_TO_CLASS = {
    "grooming":    1,
    "eating":      2,
    "nesting":     3,
    "play_isopad": 4,
}
CLASS_TO_GESTURE = {v: k for k, v in GESTURE_TO_CLASS.items()}
CLASS_TO_GESTURE[CLASS_NULL]   = "none"
CLASS_TO_GESTURE[CLASS_IGNORE] = "ignore"

# Labelled span on the scale clock — derived from sync metadata.
LABELED_START_MS = SYNC_OFFSET_MS
LABELED_END_MS   = int(0.745691 * 3600 * 1000)  # 2684488 ms; matches "Stop recording" cell

GESTURE_SHEETS = {
    "Grooming_Table 1":         "grooming",
    "Eating_Table 1":           "eating",
    "Nesting_Table 1":          "nesting",
    "Play with isopad_Table 1": "play_isopad",
}


def parse_xls(xls_path: str | Path) -> pl.DataFrame:
    """L7a — Load gesture intervals from the XLS into a long-form table.

    Returns columns: gesture, on_scale, t_start_ms, t_end_ms (scale clock).
    """
    wb = xlrd.open_workbook(str(xls_path))
    rows: list[dict] = []
    for sheet, gesture in GESTURE_SHEETS.items():
        sh = wb.sheet_by_name(sheet)
        for r in range(1, sh.nrows):
            on_scale = sh.cell_value(r, 0)
            start    = sh.cell_value(r, 1)
            end      = sh.cell_value(r, 2)
            if start == "" or end == "":
                continue
            start_ms = int(float(start) * DAY_SECONDS * 1000) + SYNC_OFFSET_MS
            end_ms   = int(float(end)   * DAY_SECONDS * 1000) + SYNC_OFFSET_MS
            rows.append({
                "gesture": gesture,
                "on_scale": float(on_scale) if isinstance(on_scale, (int, float)) else None,
                "t_start_ms": start_ms,
                "t_end_ms": end_ms,
                "source_sheet": sheet,
                "source_row": r,
            })
    return pl.DataFrame(rows).sort(["gesture", "t_start_ms"])


def sort_and_merge_within_sheet(events: pl.DataFrame, touch_tolerance_ms: int = 0) -> tuple[pl.DataFrame, pl.DataFrame]:
    """L7b — Per-gesture: sort and merge overlapping/touching intervals.

    Returns (merged_events, merge_log).
    """
    merged_rows = []
    merge_log = []
    for gesture in events["gesture"].unique().to_list():
        sub = events.filter(pl.col("gesture") == gesture).sort("t_start_ms").to_dicts()
        if not sub:
            continue
        cur = dict(sub[0])
        for nxt in sub[1:]:
            if nxt["t_start_ms"] <= cur["t_end_ms"] + touch_tolerance_ms:
                # overlap — merge
                merge_log.append({
                    "gesture": gesture,
                    "kept_row":   cur["source_row"],
                    "merged_row": nxt["source_row"],
                    "kept_start_ms":   cur["t_start_ms"],
                    "kept_end_ms":     cur["t_end_ms"],
                    "merged_start_ms": nxt["t_start_ms"],
                    "merged_end_ms":   nxt["t_end_ms"],
                })
                cur["t_end_ms"] = max(cur["t_end_ms"], nxt["t_end_ms"])
            else:
                merged_rows.append(cur)
                cur = dict(nxt)
        merged_rows.append(cur)
    merged = pl.DataFrame(merged_rows).sort("t_start_ms")
    log    = pl.DataFrame(merge_log)
    return merged, log


def cross_gesture_overlaps(events: pl.DataFrame) -> pl.DataFrame:
    """L7d — Find time ranges covered by >1 gesture type. Returns (start_ms, end_ms, classes)."""
    sorted_ev = events.sort("t_start_ms").to_dicts()
    n = len(sorted_ev)
    overlaps = []
    for i, a in enumerate(sorted_ev):
        for j in range(i + 1, n):
            b = sorted_ev[j]
            if b["t_start_ms"] >= a["t_end_ms"]:
                break
            if a["gesture"] == b["gesture"]:
                continue
            overlaps.append({
                "t_start_ms": max(a["t_start_ms"], b["t_start_ms"]),
                "t_end_ms":   min(a["t_end_ms"],   b["t_end_ms"]),
                "gesture_a":  a["gesture"],
                "gesture_b":  b["gesture"],
            })
    if not overlaps:
        return pl.DataFrame({"t_start_ms": [], "t_end_ms": [], "gesture_a": [], "gesture_b": []},
                            schema={"t_start_ms": pl.Int64, "t_end_ms": pl.Int64,
                                    "gesture_a": pl.Utf8, "gesture_b": pl.Utf8})
    return pl.DataFrame(overlaps)


def rasterize(t_ms: np.ndarray, events: pl.DataFrame, overlaps: pl.DataFrame) -> np.ndarray:
    """L7e — Build a per-frame class index from gesture events + overlap mask.

    Default class = 0. Each event sets its class on contained frames.
    Then overlap regions override to -1.
    """
    cls = np.zeros(len(t_ms), dtype=np.int8)
    t = t_ms.astype(np.int64)
    for ev in events.iter_rows(named=True):
        lo = np.searchsorted(t, ev["t_start_ms"], side="left")
        hi = np.searchsorted(t, ev["t_end_ms"],   side="right")
        cls[lo:hi] = GESTURE_TO_CLASS[ev["gesture"]]
    for ov in overlaps.iter_rows(named=True):
        lo = np.searchsorted(t, ov["t_start_ms"], side="left")
        hi = np.searchsorted(t, ov["t_end_ms"],   side="right")
        cls[lo:hi] = CLASS_IGNORE
    return cls


def labeled_span_mask(t_ms: np.ndarray,
                      start_ms: int = LABELED_START_MS,
                      end_ms: int = LABELED_END_MS) -> np.ndarray:
    """L7f — True where the scale clock is inside the annotator's watched span."""
    return (t_ms >= start_ms) & (t_ms <= end_ms)
