"""Mouse3 phase 1 — raw -> cleaned, tared, gated, uniform 25 Hz frames.

Reuses the dataset-1 library functions, retuned for the ~33 Hz native rate:
  L1 io_raw.load_raw           (no sentinels in this file; handled gracefully)
  L2 clock.assign_segments     (gaps > 500 ms -> segment breaks)
  L3 channel_clean             (hampel + savgol, windows scaled for ~33 Hz)
  L4 tare                      (empty-cage median over [0, mouse-in])
  L5 presence.apply_off_scale_gate
  L6 resample.resample_all     (uniform 40 ms grid, per segment)

Output: data/interim/m3_frames.parquet  (t_ms, m_total, is_loaded, segment_id)
        figures/m3_phase1_overview.png
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import polars as pl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mousepipe.io_raw import load_raw
from mousepipe.clock import assign_segments, segment_summary
from mousepipe.channel_clean import hampel, lowpass_savgol
from mousepipe.tare_fuse import empty_cage_tare
from mousepipe.presence import apply_off_scale_gate
from mousepipe.resample import resample_all
from mousepipe import mouse3 as m3

INTERIM = ROOT / "data" / "interim"
FIGS = ROOT / "figures"
INTERIM.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

# ~33 Hz native -> scale filter windows to roughly match dataset-1 durations.
HAMPEL_WIN = 9    # ~270 ms at 33 Hz
SAVGOL_WIN = 7    # ~210 ms; odd, > polyorder
SAVGOL_POLY = 3


def clean_channels(df: pl.DataFrame) -> pl.DataFrame:
    """Hampel + Savitzky-Golay per channel, per segment (native sample rate)."""
    seg = df["segment_id"].to_numpy()
    out = {"t_ms": df["t_ms"].to_numpy(), "segment_id": seg}
    spike_frac = {}
    for ch in ("r1", "r2", "r3"):
        x = df[ch].to_numpy().astype(np.float64)
        cleaned = np.empty_like(x)
        n_spike = 0
        for sid in np.unique(seg):
            m = seg == sid
            de_spiked, sp = hampel(x[m], window=HAMPEL_WIN, k=3.0)
            cleaned[m] = lowpass_savgol(de_spiked, window=SAVGOL_WIN, poly=SAVGOL_POLY)
            n_spike += int(sp.sum())
        out[ch] = cleaned.astype(np.float32)
        spike_frac[ch] = n_spike / len(x)
    print(f"  spike fractions: " + ", ".join(f"{k} {v:.3%}" for k, v in spike_frac.items()))
    return pl.DataFrame(out)


def main() -> None:
    raw_path = ROOT / m3.M3_DIR / m3.RAW_CSV
    print(f"[L1] loading {raw_path.name}")
    df = load_raw(raw_path)
    print(f"  rows kept: {df.height:,}  (sentinels dropped: {df.attrs.get('n_sentinel_dropped', 0)})")
    t = df["t_ms"].to_numpy()
    print(f"  scale_t: {t.min()/1000:.1f}-{t.max()/1000:.1f} s  ({(t.max()-t.min())/1000/60:.1f} min)")

    print("[L2] segmenting (gaps > 500 ms)")
    df = assign_segments(df)
    ss = segment_summary(df)
    print(f"  segments: {ss.height}")
    print(ss)

    print("[L3] per-channel clean (hampel+savgol, 33 Hz-scaled windows)")
    cleaned = clean_channels(df)

    print(f"[L4] empty-cage tare over [0, {m3.MOUSE_IN_VIDEO_S}] s")
    # Empty cage = before the mouse goes in. Use a conservative window up to mouse-in.
    tare = empty_cage_tare(cleaned, channels=("r1", "r2", "r3"), end_s=float(m3.MOUSE_IN_VIDEO_S))
    print(f"  tare (g): " + ", ".join(f"{k} {v:+.3f}" for k, v in tare.items()))
    cleaned = cleaned.with_columns([
        (pl.col(ch) - tare[ch]).alias(f"{ch}_tared") for ch in ("r1", "r2", "r3")
    ]).with_columns(
        (pl.col("r1_tared") + pl.col("r2_tared") + pl.col("r3_tared")).alias("m_total")
    )

    print("[L5] off-scale gate (Schmitt 5/2 g)")
    m_total = cleaned["m_total"].to_numpy()
    t_ms = cleaned["t_ms"].to_numpy()
    _, is_loaded = apply_off_scale_gate(m_total, t_ms)
    cleaned = cleaned.with_columns(pl.Series("is_loaded", is_loaded))
    print(f"  loaded fraction: {is_loaded.mean():.3%}")

    print(f"[L6] resample to {m3.TARGET_HZ_M3} Hz ({m3.PERIOD_MS_M3:.1f} ms grid)")
    frames = resample_all(cleaned, numeric_cols=("m_total",), bool_cols=("is_loaded",),
                          period_ms=m3.PERIOD_MS_M3)
    print(f"  frames: {frames.height:,}")

    out_path = INTERIM / "m3_frames.parquet"
    frames.write_parquet(out_path)
    print(f"  wrote {out_path}")

    # ---- figure -------------------------------------------------------------
    ft = frames["t_ms"].to_numpy() / 1000.0
    fm = frames["m_total"].to_numpy()
    fl = frames["is_loaded"].to_numpy()
    fig, ax = plt.subplots(3, 1, figsize=(13, 8))
    ax[0].plot(ft / 60, fm, lw=0.3)
    ax[0].set(title=f"Mouse3 m_total (tared, {m3.TARGET_HZ_M3} Hz) — full {ft.max()/60:.0f} min",
              xlabel="min", ylabel="g")
    ax[0].axhline(0, color="k", lw=0.4)

    # empty -> loaded step zoom
    z = ft < 300
    ax[1].plot(ft[z], fm[z], lw=0.5)
    ax[1].set(title="empty -> loaded step (mouse-in)", xlabel="s", ylabel="g")
    step_i = np.argmax(fl)
    ax[1].axvline(ft[step_i], color="r", ls="--", label=f"first loaded @ {ft[step_i]:.1f}s")
    ax[1].legend()

    ax[2].plot(ft / 60, fl.astype(int), lw=0.4)
    ax[2].set(title=f"is_loaded (loaded fraction {fl.mean():.1%})", xlabel="min", ylabel="loaded")
    fig.tight_layout()
    fig.savefig(FIGS / "m3_phase1_overview.png", dpi=110)
    print(f"  wrote {FIGS / 'm3_phase1_overview.png'}")


if __name__ == "__main__":
    main()
