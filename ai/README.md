# Action Recognition in Mice from Floor Load Cells

End-to-end pipeline + modelling study for recovering mouse behaviours
(grooming / eating / nesting / play-with-isopad) from a triplet of
floor-mounted load cells sampled at ~80 Hz.

## What's here

| File | Purpose |
|---|---|
| `REPORT.md` | Long-form report — pipeline, every modelling experiment, ceiling diagnosis, recommendations. |
| `SUMMARY.md` | Executive summary version of the same. |
| `src/mousepipe/` | Pipeline library (L1–L8: parse → clock → channel-clean → tare/fuse → off-scale gate → resample → labels → windowing) + engineered features. |
| `scripts/phase{1..18}_*.py` | One-shot scripts that exercise each phase and produce parquet / CSV / figure outputs. |
| `figures/` | All diagnostic plots referenced from the report. |
| `2025.11.17-RawMassTimeSeries-NoBufferFlushes.csv` | Raw mass CSV (3 load cells, ~80 Hz, ~104 min). |
| `20251117-GroundTruthAfterWatchingVideo.xls` | Video-derived gesture annotations (10 sheets). |

The MP4 the annotator watched and the per-phase derived parquet files
are **not** in the repo — re-running the phase scripts in order
regenerates everything under `data/` from the raw CSV + xls.

## Headline result

Six independent model families (LDA, RF, 1-D CNN, hand-engineered features
+ ExtraTrees, TSFresh 645-feature + ExtraTrees, 2-D spectrogram CNN) all
converge to **0.60–0.65 accuracy** on the within-session 3-class problem,
with overlapping confidence intervals. The binary rest-vs-gesture task
caps at **AUROC ≈ 0.75**. This is a **data-information ceiling**, not a
model ceiling: the discriminating signal that separates grooming from
nesting lives in body posture / paw motion, which the human annotator
saw on video but which doesn't project usefully onto vertical floor force
at 80 Hz. See `REPORT.md` §6 for the full diagnosis.

## Reproducing

```bash
# 1. Install (Python 3.12 + uv)
uv sync

# 2. Run the cleaning pipeline (L1–L8)
for i in 1 2 3 4 5 6 7 8; do uv run python scripts/phase${i}_*.py; done

# 3. Run the modelling experiments
uv run python scripts/phase9_lda.py
uv run python scripts/phase12_kfold_cnn.py
uv run python scripts/phase14_features.py
uv run python scripts/phase16_spectrogram_cnn.py
uv run python scripts/phase17_tsfresh.py
uv run python scripts/phase18a_binary_spectrogram_cnn.py
uv run python scripts/phase18b_binary_tsfresh.py
```

Outputs land in `data/interim/`, `data/processed/`, and `figures/`.

## Constraints driving the design

- Single fused channel `m_total = r1 + r2 + r3`. No per-cell or
  centre-of-mass features.
- Interval-aware train/test splits (every window from one annotation
  interval goes to exactly one fold) — needed because adjacent windows
  share 75 % of their samples.
- Every modelling result is reported as a **5-fold CV mean ± std with
  95 % CI**, and CNN folds use a **3-seed ensemble** to suppress the
  ±11 pp per-seed variance found in Phase 11d.
