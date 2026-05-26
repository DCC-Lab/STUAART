"""L4 — Per-channel tare correction using the empty-cage window + fusion."""
from __future__ import annotations
import numpy as np
import polars as pl

from . import EMPTY_CAGE_END_S


def empty_cage_tare(df: pl.DataFrame, channels=("r1", "r2", "r3"),
                    end_s: float = EMPTY_CAGE_END_S) -> dict[str, float]:
    """Per-channel median over scale_t ∈ [0, end_s]. Returns {channel: tare_g}."""
    end_ms = int(end_s * 1000)
    pre = df.filter(pl.col("t_ms") <= end_ms)
    if pre.height < 100:
        raise ValueError(f"Empty-cage window too small: only {pre.height} samples")
    return {ch: float(pre[ch].median()) for ch in channels}


def fuse(df: pl.DataFrame, source_suffix: str = "_20hz", channels=("r1", "r2", "r3")) -> tuple[pl.DataFrame, dict[str, float]]:
    """Apply tare per channel then sum to m_total. Reads `r{i}{source_suffix}` columns."""
    src = {ch: f"{ch}{source_suffix}" for ch in channels}
    tare = empty_cage_tare(df.rename({src[ch]: ch for ch in channels}).select(["t_ms", *channels]),
                           channels=channels)
    out = df.with_columns([
        (pl.col(src[ch]) - tare[ch]).alias(f"{ch}_tared") for ch in channels
    ]).with_columns(
        (pl.col("r1_tared") + pl.col("r2_tared") + pl.col("r3_tared")).alias("m_total")
    )
    return out, tare
