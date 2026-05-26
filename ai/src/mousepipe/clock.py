"""L2 — Clock-outlier handling.

Detects large inter-sample gaps and assigns a segment id so downstream layers
can refuse to interpolate across hardware dropouts.
"""
from __future__ import annotations
import polars as pl

SEGMENT_BREAK_MS = 500  # gaps strictly greater than this start a new segment


def assign_segments(df: pl.DataFrame, break_ms: int = SEGMENT_BREAK_MS) -> pl.DataFrame:
    """Add `dt_ms` (i64, null on first row) and `segment_id` (u32, 0-indexed).

    A new segment starts whenever dt_ms > break_ms.
    """
    return (
        df.with_columns(pl.col("t_ms").diff().alias("dt_ms"))
        .with_columns(
            (pl.col("dt_ms").fill_null(0) > break_ms).cum_sum().cast(pl.UInt32).alias("segment_id")
        )
    )


def segment_summary(df: pl.DataFrame) -> pl.DataFrame:
    """One row per segment with start/end and sample count."""
    return (
        df.group_by("segment_id")
        .agg(
            pl.col("t_ms").min().alias("t_start_ms"),
            pl.col("t_ms").max().alias("t_end_ms"),
            pl.col("t_ms").len().alias("n_samples"),
        )
        .sort("segment_id")
        .with_columns(
            (pl.col("t_end_ms") - pl.col("t_start_ms")).alias("duration_ms"),
        )
    )
