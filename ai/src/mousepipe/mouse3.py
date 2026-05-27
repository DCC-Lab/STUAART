"""Mouse3 layer — adapt the dataset-1 pipeline to the 3-hour recording.

Differences from dataset 1 (see MOUSE3_REPORT.md / plan):
  - Native sample rate ~33 Hz (30 ms), not 80 Hz  -> TARGET_HZ_M3 = 25 (no upsampling).
  - Annotations are CSV sheets with H:MM:SS video timestamps, with a brand-new
    *Sleeping* sheet (dataset 1 had no sleep label).
  - No explicit video->scale sync delay in the info sheet; we derive it from the
    mouse-in load step (mouse placed in at video 0:02:38).

Task framing (locked with the user):
  - Binary sleep/wake scoring over the whole recording:
        ACTIVE  = on-scale AND not annotated sleeping, inside the annotated span
        SLEEP   = on-scale AND inside an annotated sleeping interval
        BG/ignore = off-scale, or outside the annotated span (never scored)
  - m_total only (the per-sheet "On scale" 1/2/3 column is position metadata -> excluded).
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import polars as pl

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
M3_DIR = "Mouse3-3heures-10Hz"
RAW_CSV = "2025.10.28-RawWeightData-80Hz.csv"  # filename says 80Hz; data is ~33Hz
LABEL_SHEETS = {
    "Sleeping-Table 1.csv":         "sleeping",
    "Grooming-Table 1.csv":         "grooming",
    "Eating-Table 1.csv":           "eating",
    "Play with isopad-Table 1.csv": "play_isopad",
}

TARGET_HZ_M3 = 25                       # 40 ms grid; < native Nyquist (16.5 Hz), keeps 5-10 Hz band
PERIOD_MS_M3 = 1000.0 / TARGET_HZ_M3    # 40 ms
MOUSE_IN_VIDEO_S = 2 * 60 + 38          # "Mouse in 0:02:38" -> 158 s of video time

# Per-frame class encoding (chosen so windows.build_windows can window classes
# (1, 2) with include_rest=False; class 0 is the never-windowed background).
CLASS_BG     = 0   # off-scale, or outside the annotated span
CLASS_ACTIVE = 1
CLASS_SLEEP  = 2
CLASS_NAME = {CLASS_ACTIVE: "active", CLASS_SLEEP: "sleeping", CLASS_BG: "bg"}


# ----------------------------------------------------------------------------
# Sync
# ----------------------------------------------------------------------------
def derive_sync_offset(t_ms: np.ndarray, m_sum: np.ndarray,
                       thr_g: float = 10.0, hold_s: float = 5.0,
                       mouse_in_video_s: float = MOUSE_IN_VIDEO_S) -> dict:
    """Derive the video->scale offset from the mouse-in load step.

    The cage is empty until the mouse is placed in at video time `mouse_in_video_s`.
    On the scale clock that instant is the first *sustained* jump above `thr_g`.
    Returns dict with offset_ms (scale_ms = video_ms + offset_ms) and diagnostics.
    """
    t = t_ms.astype(np.float64)
    m = m_sum.astype(np.float64)
    load_t = None
    n = len(t)
    i = 0
    while i < n:
        if m[i] > thr_g:
            end = t[i] + hold_s * 1000.0
            j = i
            ok = True
            while j < n and t[j] < end:
                if m[j] < thr_g * 0.5:
                    ok = False
                    break
                j += 1
            if ok:
                load_t = t[i]
                break
            i = j
        else:
            i += 1
    if load_t is None:
        raise ValueError("No sustained load step found; cannot derive sync.")
    offset_ms = float(load_t - mouse_in_video_s * 1000.0)
    return {
        "offset_ms": offset_ms,
        "load_step_scale_s": float(load_t / 1000.0),
        "mouse_in_video_s": float(mouse_in_video_s),
    }


# ----------------------------------------------------------------------------
# Label parsing
# ----------------------------------------------------------------------------
def _hms_to_s(hms: str) -> float:
    """'H:MM:SS' -> seconds (video clock)."""
    parts = [p for p in hms.strip().split(":") if p != ""]
    h, m, s = (int(parts[0]), int(parts[1]), int(parts[2]))
    return h * 3600 + m * 60 + s


def parse_mouse3_labels(m3_dir: str | Path, offset_ms: float) -> pl.DataFrame:
    """Read all label sheets into a long table on the scale clock.

    Columns: gesture, on_scale, t_start_ms, t_end_ms, source_sheet, source_row.
    Robust to the CSV quirks (CRLF, no trailing newline, non-breaking header
    spaces): we read by column position, not header name.
    """
    m3_dir = Path(m3_dir)
    rows: list[dict] = []
    for fname, gesture in LABEL_SHEETS.items():
        df = pl.read_csv(m3_dir / fname, has_header=True, infer_schema=False,
                         truncate_ragged_lines=True)
        cols = df.columns  # [On scale, Start, End, Delta]
        for r, rec in enumerate(df.iter_rows(named=False)):
            on_scale, start, end = rec[0], rec[1], rec[2]
            if start is None or end is None or str(start).strip() == "":
                continue
            try:
                start_ms = int(_hms_to_s(str(start)) * 1000 + offset_ms)
                end_ms   = int(_hms_to_s(str(end))   * 1000 + offset_ms)
            except (ValueError, IndexError):
                continue
            if end_ms <= start_ms:
                continue
            try:
                on = float(on_scale)
            except (TypeError, ValueError):
                on = None
            rows.append({
                "gesture": gesture, "on_scale": on,
                "t_start_ms": start_ms, "t_end_ms": end_ms,
                "source_sheet": fname, "source_row": r,
            })
    return pl.DataFrame(rows).sort(["gesture", "t_start_ms"])


def merge_intervals(events: pl.DataFrame, gesture: str | None = None) -> list[tuple[int, int]]:
    """Sort + merge overlapping/touching intervals (optionally for one gesture).

    Returns a list of (t_start_ms, t_end_ms) on the scale clock.
    """
    sub = events if gesture is None else events.filter(pl.col("gesture") == gesture)
    iv = sub.sort("t_start_ms").select(["t_start_ms", "t_end_ms"]).to_numpy()
    if len(iv) == 0:
        return []
    merged: list[list[int]] = [list(iv[0])]
    for s, e in iv[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], int(e))
        else:
            merged.append([int(s), int(e)])
    return [(int(s), int(e)) for s, e in merged]


# ----------------------------------------------------------------------------
# Rasterize sleep / active onto the uniform grid
# ----------------------------------------------------------------------------
def labeled_span(events: pl.DataFrame, load_step_scale_ms: int) -> tuple[int, int]:
    """Annotated span on the scale clock: [mouse-in load step, last annotation end].

    Outside this span, absence of a sleep label does NOT mean active (the video
    wasn't being scored there), so those frames become background.
    """
    end_ms = int(events["t_end_ms"].max())
    return int(load_step_scale_ms), end_ms


def rasterize_sleep_active(t_ms: np.ndarray, sleeping_intervals: list[tuple[int, int]],
                           is_loaded: np.ndarray, span: tuple[int, int]) -> np.ndarray:
    """Per-frame class: ACTIVE(1) / SLEEP(2) / BG(0).

    BG = off-scale OR outside the annotated span. Inside span & loaded defaults
    to ACTIVE; sleeping intervals override to SLEEP.
    """
    t = t_ms.astype(np.int64)
    cls = np.zeros(len(t), dtype=np.int8)  # BG everywhere
    in_span = (t >= span[0]) & (t <= span[1])
    scored = in_span & is_loaded.astype(bool)
    cls[scored] = CLASS_ACTIVE
    for s, e in sleeping_intervals:
        lo = np.searchsorted(t, s, side="left")
        hi = np.searchsorted(t, e, side="right")
        seg = slice(lo, hi)
        # only flip frames that are scored (loaded & in span)
        sub = cls[seg]
        sub[scored[seg]] = CLASS_SLEEP
        cls[seg] = sub
    return cls


# ----------------------------------------------------------------------------
# Movement index (the headline discriminator)
# ----------------------------------------------------------------------------
def movement_index(signal: np.ndarray) -> float:
    """Median absolute first difference of a window of m_total (grams/sample).

    High-frequency micro-movement: ~0.1 g when still (asleep), ~1-2 g when active.
    This is the actigraphy statistic; window *std* does NOT work because slow
    postural drift inflates it during long sleep bouts.
    """
    d = np.abs(np.diff(np.asarray(signal, dtype=np.float64)))
    return float(np.median(d)) if len(d) else 0.0


def movement_index_batch(signals: np.ndarray) -> np.ndarray:
    """Vectorised movement index over rows of a (B, N) array."""
    d = np.abs(np.diff(signals.astype(np.float64), axis=1))
    return np.median(d, axis=1)


# ----------------------------------------------------------------------------
# Windowing (Mouse3 variant)
# ----------------------------------------------------------------------------
def build_windows_m3(frames: pl.DataFrame, classes: tuple[int, ...] = (CLASS_ACTIVE, CLASS_SLEEP),
                     fs: int = TARGET_HZ_M3, window_len_s: float = 4.0, stride_s: float = 1.0,
                     margin_s: float = 1.0, block_s: float = 30.0) -> tuple[pl.DataFrame, dict]:
    """Slice frames into windows of m_total, robust to Mouse3's structure.

    Unlike windows.build_windows (which drops any class run crossing a segment
    break — fine for dataset-1's second-long gestures, fatal for Mouse3's
    hour-long "active" run that spans the hourly buffer breaks), this:
      - finds runs of constant (class, segment_id) so runs never cross a gap,
      - trims `margin_s` from each end (sync slack + transition smear),
      - emits overlapping windows, and
      - assigns `source_interval_id` per `block_s` block within each run, so
        adjacent overlapping windows share a group => interval-aware CV without
        collapsing the long active run into a single un-splittable group.

    Input columns: t_ms, m_total, class, is_labeled, segment_id.
    """
    win_n = int(round(window_len_s * fs))
    stride_n = int(round(stride_s * fs))
    margin_n = int(round(margin_s * fs))
    block_ms = block_s * 1000.0

    df = frames.filter(pl.col("is_labeled")).sort("t_ms")
    t_ms = df["t_ms"].to_numpy().astype(np.int64)
    m_total = df["m_total"].to_numpy().astype(np.float32)
    cls = df["class"].to_numpy().astype(np.int64)
    seg = df["segment_id"].to_numpy().astype(np.int64)
    n = len(t_ms)

    # run boundaries: class OR segment changes
    if n == 0:
        raise ValueError("no labeled frames")
    chg = (np.diff(cls) != 0) | (np.diff(seg) != 0)
    starts = np.concatenate(([0], np.where(chg)[0] + 1))
    ends = np.concatenate((starts[1:], [n]))

    rows = []
    stats = {c: {"n_intervals": 0, "n_core_intervals": 0, "n_windows": 0} for c in classes}
    gid = 0
    for s, e in zip(starts, ends):
        c = int(cls[s])
        if c not in classes:
            continue
        stats[c]["n_intervals"] += 1
        cs, ce = s + margin_n, e - margin_n
        if ce - cs < win_n:
            continue
        stats[c]["n_core_intervals"] += 1
        run_t0 = t_ms[cs]
        block_gids: dict[int, int] = {}
        for ws in range(cs, ce - win_n + 1, stride_n):
            blk = int((t_ms[ws] - run_t0) // block_ms)
            if blk not in block_gids:
                block_gids[blk] = gid
                gid += 1
            rows.append({
                "t_start_ms": int(t_ms[ws]),
                "t_end_ms": int(t_ms[ws + win_n - 1]),
                "label": c,
                "source_interval_id": block_gids[blk],
                "signal": m_total[ws:ws + win_n].tolist(),
            })
            stats[c]["n_windows"] += 1

    win_df = pl.DataFrame(rows, schema={
        "t_start_ms": pl.Int64, "t_end_ms": pl.Int64, "label": pl.Int8,
        "source_interval_id": pl.Int32, "signal": pl.List(pl.Float32),
    })
    return win_df, stats
