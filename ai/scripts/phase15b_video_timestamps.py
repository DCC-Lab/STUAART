"""Phase 15b — Print video-time landmarks for manual verification against MAH00950.MP4.

For each "key" gesture interval, produce both scale-clock time and video-clock time
(mm:ss). The user can scrub the video to each video timestamp and confirm the
labelled gesture is actually happening on screen.

Conversion:  video_t_seconds = scale_t_seconds - 43.5
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import polars as pl


SYNC_S = 43.5


def mmss(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60:02d}:{s % 60:02d}"


def main():
    interim = ROOT / "data" / "interim"
    iv = pl.read_csv(interim / "phase15_gesture_intervals.csv").sort("t_start_s")

    # Compute video times
    iv = iv.with_columns(
        (pl.col("t_start_s") - SYNC_S).alias("video_start_s"),
        (pl.col("t_end_s")   - SYNC_S).alias("video_end_s"),
    )

    def fmt(rows, title):
        print(f"\n=== {title} ===")
        print(f"{'class':<12} {'video start':>11} {'video end':>10} {'duration':>9}   {'scale_t':>22}")
        for r in rows:
            vs = r["video_start_s"]; ve = r["video_end_s"]
            print(f"{r['gesture']:<12} {mmss(vs):>11} {mmss(ve):>10} {r['duration_s']:>6.0f} s   "
                  f"({vs:>7.1f}..{ve:<7.1f} s video / scale {r['t_start_s']:.0f}..{r['t_end_s']:.0f})")

    # ------- LANDMARKS -------

    # 1) THE EATING EVENT — only one in the recording, best sync landmark
    eating = iv.filter(pl.col("class") == 2).to_dicts()
    fmt(eating, "THE EATING EVENT (unique — best sync landmark)")

    # 2) Top 5 longest of each gesture class
    for c, name in [(1, "GROOMING"), (3, "NESTING"), (4, "PLAY_ISOPAD")]:
        top = (iv.filter(pl.col("class") == c)
                 .sort("duration_s", descending=True)
                 .head(5)
                 .to_dicts())
        fmt(top, f"Top 5 longest {name} bouts")

    # 3) The very first gesture (anywhere) — checks alignment at the start of annotation
    first = iv.head(1).to_dicts()
    fmt(first, "FIRST gesture in the recording (alignment at start)")

    # 4) The very last gesture — checks alignment at the end
    last = iv.tail(1).to_dicts()
    fmt(last, "LAST gesture in the recording (alignment at end)")

    # 5) A few short ones for high-precision spot-checks (≤3 s)
    short = (iv.filter((pl.col("duration_s") <= 3) & (pl.col("class") != 2))
               .sort("duration_s")
               .head(5)
               .to_dicts())
    fmt(short, "5 shortest non-eating gestures (good for tight-boundary checks)")

    # Persist a CSV for the user to keep
    out = iv.select([
        "class", "gesture",
        pl.col("video_start_s").map_elements(mmss, return_dtype=pl.Utf8).alias("video_start_mmss"),
        pl.col("video_end_s").map_elements(mmss, return_dtype=pl.Utf8).alias("video_end_mmss"),
        "duration_s",
        "video_start_s", "video_end_s",
        "t_start_s", "t_end_s",
    ])
    out.write_csv(interim / "phase15_video_landmarks.csv")
    print(f"\nwrote {interim / 'phase15_video_landmarks.csv'} (full list)")


if __name__ == "__main__":
    main()
