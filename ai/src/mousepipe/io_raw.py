"""L1 — Parse & sanitize the raw mass time-series CSV.

Input : 2025.11.17-RawMassTimeSeries-NoBufferFlushes.csv (~505k rows)
        Columns: 'time (ms), reading 1, reading 2, reading 3'
        Plus 4,951 sentinel rows '--, --, --, --' (every ~102 rows; buffer flush markers).

Output: a tidy DataFrame with columns t_ms (i64), r1/r2/r3 (f32), sum (f32).
"""
from __future__ import annotations
from pathlib import Path
import polars as pl

SENTINEL = "--"

def load_raw(csv_path: str | Path) -> pl.DataFrame:
    """Parse the raw mass CSV. Returns rows with non-sentinel, monotone time."""
    csv_path = Path(csv_path)

    # Read everything as strings first so the sentinel rows don't crash type inference.
    df = pl.read_csv(
        csv_path,
        has_header=True,
        new_columns=["t_ms", "r1", "r2", "r3"],
        schema_overrides={"t_ms": pl.Utf8, "r1": pl.Utf8, "r2": pl.Utf8, "r3": pl.Utf8},
    )

    n_raw = df.height

    # Drop sentinel rows: any cell starting with '--' (with optional surrounding spaces).
    sentinel_mask = (
        df["t_ms"].str.strip_chars().str.starts_with(SENTINEL)
        | df["r1"].str.strip_chars().str.starts_with(SENTINEL)
        | df["r2"].str.strip_chars().str.starts_with(SENTINEL)
        | df["r3"].str.strip_chars().str.starts_with(SENTINEL)
    )
    n_sentinel = int(sentinel_mask.sum())
    df = df.filter(~sentinel_mask)

    # Cast and sum.
    df = df.with_columns(
        pl.col("t_ms").cast(pl.Int64),
        pl.col("r1").cast(pl.Float32),
        pl.col("r2").cast(pl.Float32),
        pl.col("r3").cast(pl.Float32),
    ).with_columns(
        (pl.col("r1") + pl.col("r2") + pl.col("r3")).alias("sum")
    )

    # Monotone check.
    t = df["t_ms"]
    if (t.diff().drop_nulls() < 0).any():
        raise ValueError("time_ms is not monotonically non-decreasing")

    df.attrs = {
        "n_raw_rows": n_raw,
        "n_sentinel_dropped": n_sentinel,
        "n_kept": df.height,
    }
    return df
