# Action Recognition in Mice from Floor Load Cells

End-to-end pipeline + modelling studies for recovering mouse behaviour from a
triplet of floor-mounted load cells (single fused channel `m_total = r1 + r2 + r3`).
Two studies live here, with opposite conclusions:

1. **Gestures** (dataset 1, `REPORT.md`) — grooming / eating / nesting / play.
2. **Active vs sleeping** (`Mouse3`, `MOUSE3_REPORT.md`) — sleep/wake scoring.

## What's here

| File | Purpose |
|---|---|
| `REPORT.md` / `SUMMARY.md` | Dataset-1 gesture study — long-form / executive. |
| `MOUSE3_REPORT.md` | **Mouse3 active-vs-sleeping study** — methods, leaderboard, simplest-method recommendation, metric primer (§5.1). |
| `src/mousepipe/` | Pipeline library (L1–L8: parse → clock → channel-clean → tare/fuse → off-scale gate → resample → labels → windowing) + engineered features. `mouse3.py` adapts it to the Mouse3 recording. |
| `scripts/phase{1..18}_*.py` | Dataset-1 phase + modelling scripts. |
| `scripts/m3_phase{1..4}_*.py` | Mouse3 active-vs-sleep: prepare → sync+labels → models → hypnogram. |
| `figures/` | All diagnostic plots (`phase*_*`, `m3_phase*_*`). |
| `2025.11.17-RawMassTimeSeries-NoBufferFlushes.csv` + `20251117-…xls` | Dataset-1 raw mass (~80 Hz, ~104 min) + gesture annotations. |
| `Mouse3-3heures-10Hz/` | Mouse3 raw CSV (~33 Hz, ~261 min) + 4 label sheets (incl. **Sleeping**) + info. |

The MP4s the annotator watched and the per-phase derived parquet files are **not**
in the repo — re-running the phase scripts in order regenerates everything under
`data/` from the raw CSV + labels.

## Headline results

**Gestures (dataset 1):** six independent model families (LDA, RF, 1-D CNN,
hand-engineered + ExtraTrees, TSFresh 645-feature + ExtraTrees, 2-D spectrogram CNN)
all converge to **0.60–0.65 accuracy** on the within-session 3-class problem with
overlapping CIs; binary rest-vs-gesture caps at **AUROC ≈ 0.75**. This is a
**data-information ceiling**, not a model ceiling — the signal separating grooming
from nesting lives in posture/paw motion, which doesn't project onto vertical floor
force at 80 Hz. (`REPORT.md` §6.)

**Active vs sleeping (Mouse3):** the opposite regime. A **single feature** — the
*movement index*, `median(|Δm_total|)` over a few-second window — thresholded at
**≈0.11 g/sample** gives **AUROC 0.996 ± 0.003 / balanced accuracy 0.975 ± 0.012**
(interval-aware 5-fold CV). A 33-feature logistic/ExtraTrees model ties it within CI;
a 1-D CNN does *worse* (per-window normalization discards the amplitude that is the
signal). **No ML is needed** — movement-vs-stillness genuinely lives in vertical
force. The end-to-end detector recovers all 8 sleep bouts and the 142-min sleep onset.
(`MOUSE3_REPORT.md`.)

## Reproducing

```bash
# 1. Install (Python 3.12 + uv)
uv sync

# 2a. Mouse3 active-vs-sleep (run in order)
uv run python scripts/m3_phase1_prepare.py      # raw -> 25 Hz frames
uv run python scripts/m3_phase2_sync_labels.py  # derive+validate sync, labels, windows
uv run python scripts/m3_phase3_models.py       # threshold + logreg + ExtraTrees + CNN, 5-fold CV
uv run python scripts/m3_phase4_hypnogram.py    # whole-recording sleep/wake detector + bout stats

# 2b. Dataset-1 cleaning pipeline (L1–L8)
for i in 1 2 3 4 5 6 7 8; do uv run python scripts/phase${i}_*.py; done

# 2c. Dataset-1 modelling experiments
uv run python scripts/phase9_lda.py
uv run python scripts/phase12_cnn_kfold.py
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
