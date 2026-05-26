"""L6 — Uniform 80 Hz resample on a 12.5 ms grid, per segment."""
from __future__ import annotations
import numpy as np
import polars as pl

from . import TARGET_HZ

PERIOD_MS = 1000.0 / TARGET_HZ  # 12.5 ms at 80 Hz


def make_grid(seg_start_ms: int, seg_end_ms: int, period_ms: float = PERIOD_MS) -> np.ndarray:
    """Uniform time grid (float ms) covering [seg_start, seg_end] inclusive."""
    n = int((seg_end_ms - seg_start_ms) / period_ms) + 1
    return seg_start_ms + np.arange(n, dtype=np.float64) * period_ms


def resample_segment(t_in: np.ndarray, cols: dict[str, np.ndarray], period_ms: float = PERIOD_MS,
                     bool_cols: tuple[str, ...] = ()) -> dict[str, np.ndarray]:
    """Linearly interpolate every column in `cols` onto a uniform grid.

    Boolean columns named in `bool_cols` are converted to float for interpolation
    then thresholded back to bool at 0.5.
    """
    grid = make_grid(int(t_in.min()), int(t_in.max()), period_ms=period_ms)
    out: dict[str, np.ndarray] = {"t_ms": grid}
    for name, x in cols.items():
        x_f = x.astype(np.float64)
        y = np.interp(grid, t_in.astype(np.float64), x_f)
        if name in bool_cols:
            out[name] = (y > 0.5)
        else:
            out[name] = y.astype(np.float32)
    return out


def resample_all(df: pl.DataFrame,
                 numeric_cols: tuple[str, ...] = ("m_total", "r1_tared", "r2_tared", "r3_tared"),
                 bool_cols: tuple[str, ...] = ("is_loaded",),
                 period_ms: float = PERIOD_MS) -> pl.DataFrame:
    """Uniform resample every segment independently. Concatenates the results."""
    t = df["t_ms"].to_numpy()
    seg = df["segment_id"].to_numpy()
    pieces = []
    for sid in sorted(np.unique(seg)):
        m = seg == sid
        cols = {n: df[n].to_numpy()[m] for n in (*numeric_cols, *bool_cols)}
        out  = resample_segment(t[m], cols, period_ms=period_ms, bool_cols=bool_cols)
        out["segment_id"] = np.full_like(out["t_ms"], sid, dtype=np.uint32)
        pieces.append(pl.DataFrame(out))
    return pl.concat(pieces)
