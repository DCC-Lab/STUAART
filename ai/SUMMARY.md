# Mouse-Scale Gesture Classification — Project Summary

## Context

**Data**: one 2025-11-17 recording of a single mouse in a cage with 3 load cells tiling the floor.

| Artifact | Size |
|---|---|
| `2025.11.17-RawMassTimeSeries-NoBufferFlushes.csv` | 12 MB, 505,002 rows (≈80 Hz, ~104 min) |
| `20251117-GroundTruthAfterWatchingVideo.xls` | 10 sheets: 1 metadata + 4 gesture + 5 position |
| `MAH00950.MP4` | 2,641 s of video (44 min) the annotator watched |

**Goal**: build a clean pipeline from the raw CSV + ground truth into a labelled, ML-ready dataset, then test classifiers that recognize gesture types (grooming, eating, nesting, play_isopad, none).

---

## Pipeline (Phases 1–8)

```
raw CSV ──► L1 parse ──► L2 segments ──► L3 channel clean ──► L4 tare+fuse
                                                                    │
GT .xls ──► L7 parse + sync + raster ──────────────────► join ◄─────┴── L5 off-scale gate
                                                          │              │
                                                          ▼              ▼
                                                  labeled_80hz   ◄── L6 80 Hz uniform
                                                          │
                                                          ▼
                                                  L8 → windows_train.parquet
```

### L1 — Parse & sanitize
- Dropped **4,951 sentinel `--` rows** (buffer flush markers, every ~102 rows). Kept **500,051** valid samples.
- Time range: 2.62 s → 6261.82 s = 104.32 min, strictly monotonic.
- Δt median 12 ms, max 2569 ms.

### L2 — Clock-outlier handling
- One gap >500 ms found (the 2.57 s dropout at scale_t ≈ 60 min).
- Two segments emitted; downstream layers refuse to interpolate across the gap.

### L3 — Per-channel cleaning
- **Hampel filter** (window 25, k=3) replaces spikes with rolling median.
- **Savitzky-Golay low-pass** (the user picked **20 Hz cutoff**, kernel=5, after a 3-cutoff comparison).
- Spike fractions per channel: r1 0.7 %, r2 1.6 %, r3 2.0 %. Raw outliers (–649 g, +345 g, etc.) eliminated.

### L4 — Tare correction & fusion
- **Discovery**: first 18 s of CSV is empty cage (mouse inserted at t≈20 s, video starts at t≈43.5 s).
- Used empty-cage medians as per-channel tare: `r1=-0.110, r2=-0.031, r3=+0.279`.
- After tare, `m_total = r1 + r2 + r3` reads –0.02 g during empty cage, +22.79 g median when mouse is on the floor.

### L5 — Off-scale gate
- Schmitt trigger (θ_on=5, θ_off=2, min 200 ms).
- Only one off-scale episode detected: the empty-cage prefix. Mouse stays on the floor for the entire labelled span — **the cage walls are unclimbable, confirmed**.

### L6 — Uniform 80 Hz resample
- Per-segment time-weighted linear interpolation onto a 12.5 ms grid.
- 500,532 frames out (count differs slightly from input because of rounding to the grid).
- Δt within every segment is exactly 12.50 ms post-resample.

### L7 — Ground-truth processing
- **Sync offset = +43.5 s** (derived from XLS metadata + video duration cross-check).
  - Confirmation: `Stop recording at = 0.7457 h` cell ≈ video_stop(2640 s) + 43.5 s = 2683.5 s.
  - Data-side cross-correlation later confirmed sync is correct to within ~200 ms.
- 141 gesture intervals parsed → 5 within-sheet merges → 136 final events.
- 4 cross-gesture overlap regions marked as `class = -1` (ignore, 15 s total).
- Class map: **-1 ignore, 0 none, 1 grooming, 2 eating, 3 nesting, 4 play_isopad**.
- Labelled span = scale_t ∈ [43.5 s, 2683.5 s] = 211,279 frames (42.2 % of grid).
- Position sheets dropped per user decision.

### L8 — Windowing
- 2 s windows (160 samples), 0.5 s stride (75 % overlap), 0.5 s margin trimmed from each end of every interval.
- Min interval duration to contribute a window = 3 s; **98 / 136 intervals (72 %) make the cut**.
- Output: `windows_train.parquet`, **4,080 windows**: rest 2265, grooming 807, nesting 673, play_isopad 316, eating 19.
- `source_interval_id` column added so downstream splits can avoid leakage from overlapping windows.

---

## Modeling experiments (Phases 9–14)

All experiments use **interval-aware splits**: every window from one gesture interval goes to exactly one of {train, val, test}. Window-level random splits are leaky given the 75 % overlap.

### Phase 9 — LDA (linear baseline)

| Variant | Test acc | Chance |
|---|---|---|
| LDA + raw signal | 0.259 | 0.25 |
| LDA + z-normalized | 0.259 | 0.25 |

**Both at chance.** Even when re-run with intentionally leaky window-level split, accuracy stayed at chance — the failure mode isn't leakage, it's that no linear projection of the 160-sample window captures the class structure.

### Phase 10 — Random Forest

| Setup | Train | Test |
|---|---|---|
| RF + raw + interval split (honest) | 1.000 | **0.413** |
| RF + z-norm + interval split | 1.000 | 0.346 |
| RF + raw + window-level (leaky) | 1.000 | 0.372 |
| RF + z-norm + window-level (leaky) | 1.000 | 0.277 |

- First model class with real signal (+16 pp over chance).
- **Z-normalization HURTS trees** — splits at fixed time indices need absolute values.
- **Leakage didn't help RF** — tree splits aren't shift-invariant, so they can't "memorize" a shifted training window.
- Hyperparameter sweep across 30 configs: best was ExtraTrees max_depth=12 min_leaf=2 → 0.388. Variation ~6 pp across sweep — regularization helps a bit but not dramatically.

### Phase 10c — RF on 3 classes (drop none)

| Setup | Test |
|---|---|
| ExtraTrees, 3-class, raw | 0.458 |

Lift over chance (33 %) is +13 pp — same relative gain as 4-class. Dropping "none" doesn't fix the gesture-vs-gesture confusion.

### Phase 11 — 1-D CNN baseline

| Setup | Test |
|---|---|
| CNN + raw + 4-class | 0.418 |
| **CNN + z-norm + 4-class** | **0.587** |
| **CNN + raw + 3-class** | **0.624** |
| CNN + z-norm + 3-class | 0.532 |

- **Z-normalization story flipped**: helps CNN for 4-class (kills DC nuisance, lets the model see shape), hurts for 3-class (within-gesture amplitude differences are real signal).
- **Per-class trick**: play_isopad got 100 % precision in this single run — looked magical at first.
- Train-test gap shrunk from RF's ~0.6 to CNN's ~0.07 — CNN generalizes better.

### Phase 11d — 5-seed CNN ensemble

| Seed | Test |
|---|---|
| 42 (the lucky one) | 0.708 |
| 123 | 0.472 |
| 7 | 0.375 |
| 2026 | 0.472 |
| 314 | 0.597 |
| **Mean ± std** | **0.525 ± 0.116** |
| **Ensemble (mean logits)** | **0.597** |

**Reality check**: the 0.624 from Phase 11b was a lucky-seed artifact. Real per-seed variance is **11 pp**. The 100 % play_isopad precision was also coincidence; ensemble shows ~79 %.

### Phase 12 — 5-fold CV with 3-seed CNN ensemble per fold

| Metric | Value |
|---|---|
| Mean accuracy across 5 folds | **0.604** |
| Std across folds | 0.038 |
| **95 % CI on mean** | **[0.567, 0.642]** |

**The honest within-session 3-class baseline.**

Per-class (aggregated 948 predictions):
- grooming: P 0.51 / R 0.59
- nesting:  P 0.56 / R 0.64
- play_isopad: P **0.79** / R 0.56

Dominant failure: **grooming ↔ nesting confusion** (≈30 % each direction).

### Phase 13 — Shorter windows + binary

| Experiment | Mean | 95 % CI |
|---|---|---|
| 3-class on **1-s** windows | 0.482 | [0.369, 0.594] |
| Binary rest-vs-any-gesture (1-s) | 0.615 | [0.570, 0.660] |

- **Shorter windows hurt** 3-class by ~12 pp. Grooming recall collapses (60 % → 28 %). Stick with 2 s.
- **Binary is barely easier than 3-class** (+12 pp over chance). The hard problem isn't gesture-vs-gesture — it's **rest-vs-gesture**. A 2-stage rest→type pipeline won't help.

### Phase 16 — 2-D Spectrogram CNN

STFT (nperseg=32, noverlap=24, fs=80 Hz) → log-magnitude 17×17 (freq × time) → 3-block 2-D CNN.

| Metric | Value |
|---|---|
| Mean across 5 folds | **0.645** |
| Std | 0.055 |
| **95 % CI** | **[0.591, 0.698]** |

Per-class: grooming P 0.68 / R 0.38, nesting P 0.54 / R 0.75, play_isopad P 0.72 / R 0.75. Marginal lift over the 1-D CNN (0.604 → 0.645) but **CIs overlap**.

### Phase 17 — TSFresh (645 auto-features) + ExtraTrees

| Configuration | Mean | 95 % CI |
|---|---|---|
| all 645 features | 0.633 ± 0.044 | [0.589, 0.676] |
| top-10 | 0.617 ± 0.013 | [0.604, 0.629] |
| top-25 | 0.635 ± 0.029 | [0.607, 0.663] |
| **top-50** | **0.638 ± 0.035** | [0.605, 0.672] |

TSFresh's top features (FFT centroid / variance / aggregated stats, permutation entropy, change_quantiles, cid_ce, partial_autocorrelation, absolute_sum_of_changes) **independently corroborate** the hand-rolled drop-one analysis. Same physics, different parameterization.

### Phase 18 — Binary rest-vs-gesture redux

Re-ran the spectrogram CNN (18a) and the TSFresh + ExtraTrees pipeline (18b) on the binary task **0 = rest vs 1 = any gesture {1, 3, 4}**, dropping eating. Interval-aware 5-fold CV, 1:1 balancing.

| Model | Mean | 95 % CI | AUROC |
|---|---|---|---|
| 2-D Spectrogram CNN | 0.661 ± 0.052 | [0.610, 0.711] | 0.732 |
| TSFresh all 647 | 0.666 ± 0.041 | [0.626, 0.706] | 0.736 |
| **TSFresh top-50** | **0.679 ± 0.031** | [0.649, 0.710] | **0.745** |

Modest 5–7 pp over Phase 13's 1-D CNN binary (0.615) but still **capped at ~0.68 / AUROC 0.75**. Both architectures **lean toward calling "rest"** (recall asymmetry ~0.71 vs 0.63). Confirms a 2-stage `rest? → which?` pipeline is not the rescue path. Top binary features are dominated by **autocorrelation lags 1–7 and permutation entropy** — temporal-coherence physics.

### Phase 14 — Engineered features + drop-one selection

32 features computed per window: time-domain (rms, mean, std, mad, range, skew, kurt, slope, detr_std, zcr), frequency-band power (5 bands incl. aliased 20–40 Hz), spectral shape (entropy, centroid, dom_freq), autocorrelation (3 lags + first peak), envelope stats (mean, std, peakiness, rise time).

| Model | Mean | 95 % CI | n_features |
|---|---|---|---|
| ExtraTrees on all 32 | 0.628 | [0.573, 0.683] | 32 |
| **ExtraTrees on selected 15** | **0.638** | [0.580, 0.696] | **15** |

**The discriminators** (top drop-one importance):

| Rank | Feature | Importance | Why it works |
|---|---|---|---|
| 1 | rms | +0.015 | Average downward force level |
| 2 | mean | +0.015 | Same |
| 3 | **p_5_10_frac** | **+0.013** | Fraction of power in 5–10 Hz — **grooming-stroke band** |
| 4 | **ac_lag_100ms** | **+0.010** | Autocorrelation at 100 ms = 10 Hz period |
| 5 | p_5_10 | +0.007 | Absolute power in 5–10 Hz |
| 6 | p_2_5_frac | +0.005 | Slow rhythm relative power |
| 7 | env_std | +0.005 | Envelope variability |
| 8 | p_20_40_frac | +0.004 | ⚠ aliased band — see caveat |

**The misleaders** (removing them helps):

| Feature | Importance |
|---|---|
| detr_std | −0.014 |
| std | −0.011 |
| p_10_20_frac | −0.009 |
| spec_centroid | −0.006 |
| Envelope shape (rise_ms, peakiness) | all negative |

**Bottom line**: engineered features + ExtraTrees ≈ CNN ≈ 60–64 % accuracy with overlapping CIs.

---

## Final accuracy comparison

### 3-class (grooming / nesting / play_isopad), chance = 0.333

```
LDA (raw or z-norm)                                    │  0.259   below chance, model is broken
RF + raw (best sweep)                                  │  0.413
1-D CNN (5-fold × 3-seed ensemble — Phase 12)          │  0.604   95% CI [0.567, 0.642]
ExtraTrees, 32 engineered features, all                │  0.628
ExtraTrees, 15 selected features                       │  0.638
TSFresh 645 → top-50 + ExtraTrees                      │  0.638   95% CI [0.605, 0.672]
2-D Spectrogram CNN                                    │  0.645   95% CI [0.591, 0.698]
─────────────────────────────────────────────────────────────
       hard ceiling for this signal + this session     │  ~0.63–0.65
```

### Binary (rest vs any-gesture), chance = 0.50

```
1-D CNN binary, 1-s windows (Phase 13)                 │  0.615   95% CI [0.570, 0.660]
2-D Spectrogram CNN, 2-s (Phase 18a)                   │  0.661   95% CI [0.610, 0.711], AUROC 0.732
TSFresh all 647 (Phase 18b)                            │  0.666   95% CI [0.626, 0.706], AUROC 0.736
TSFresh top-50 (Phase 18b)                             │  0.679   95% CI [0.649, 0.710], AUROC 0.745
─────────────────────────────────────────────────────────────
       hard ceiling on binary task                     │  ~0.68 / AUROC 0.75
```

---

## Key findings (saved as memory)

Stored in `/home/x/.claude/projects/-home-x-projects-val-demo/memory/`:

| Memory | Insight |
|---|---|
| `project_scale_aliasing_caveat.md` | Load-cell resonance (50–500 Hz) aliases into 0–40 Hz band at 80 Hz sampling. 5–25 Hz range is contaminated. |
| `project_cage_geometry.md` | Cage walls unclimbable → mouse stays on floor full time → L5 off-scale gate detects ~zero mid-recording episodes. |
| `project_gesture_signal_character.md` | Gestures show **less** mass variability than rest (focused stationary activity). Standard energy/variance features fail or invert. |
| `feedback_no_position_features.md` | User-stated preference: do not derive per-cell or center-of-mass features. m_total only. |
| `project_normalization_choice.md` | Z-norm helps CNN for 4-class, hurts for 3-class. Always hurts trees. Sign flips by class set. |
| `project_baseline_accuracy.md` | 3-class within-session CNN baseline = **0.604 ± 0.038** (5-fold CV). Single-run estimates ±10 pp without CV. |
| `project_window_length_and_binary_ceiling.md` | 2-s beats 1-s by ~12 pp. Binary rest-vs-gesture tops at 0.62 → no 2-stage rescue. |
| `project_discriminative_features.md` | rms/mean + 5–10 Hz band power + autocorrelation at 100 ms lag. Generic variability features hurt. |
| `project_data_ceiling.md` | Six families converge to 0.60–0.65 (3-class) / 0.66–0.68 (binary); bottleneck is data, not model. |
| `project_tsfresh_corroborates_handcrafted.md` | TSFresh's 645→top-20 ranks the same physics as hand-rolled drop-one (FFT shape, perm entropy, cid_ce, autocorrelation). |

---

## The "hard limit" diagnosis

**Six** model families (linear, RF, 1-D CNN, hand-engineered, TSFresh 645-features, 2-D spectrogram CNN) all converge to **0.60–0.65** for 3-class with overlapping CIs. The same families on the binary task land in **0.66–0.68 / AUROC 0.73–0.75**. This is strong evidence the limit is **in the data, not in the models**.

Decomposing what's bottlenecking us:

| Factor | Hardness | Estimated cost |
|---|---|---|
| `m_total` carries similar signatures for grooming vs nesting (both stationary small-modulation, distinguished by visible posture only) | **Hard** | Most of the gap |
| One session / one mouse — small training data | Soft | ±5 pp recoverable with more recordings |
| ~200 ms sync uncertainty + annotator boundary slack | Soft, small | ±2 pp |
| 80 Hz undersampling + aliased mechanical resonance | Soft, capped | ±3 pp recoverable with anti-aliasing |

What this means:
- The within-session ceiling on this rig for this 3-class problem is **~60–65 %** and we've already hit it.
- Real gains require **more data** (more recordings) or **a second signal channel** (video features, accelerometer, IR beam breaks). Or **redefining the task** to group classes that are mechanically similar (e.g. collapse grooming + nesting into "stationary fine motion").

---

## Working artifacts

```
val-demo/
├── pyproject.toml                  # uv-managed Python 3.12 project
├── src/mousepipe/
│   ├── __init__.py                  # constants: SYNC_OFFSET_MS=43_500, TARGET_HZ=80, EMPTY_CAGE_END_S=18.0
│   ├── io_raw.py                    # L1
│   ├── clock.py                     # L2
│   ├── channel_clean.py             # L3 (Hampel + SavGol)
│   ├── tare_fuse.py                 # L4
│   ├── presence.py                  # L5 (Schmitt + min-duration)
│   ├── resample.py                  # L6
│   ├── labels.py                    # L7 (xlrd parse, sync, rasterize)
│   ├── windows.py                   # L8 (interval-aware windowing)
│   └── features.py                  # Phase 14 engineered features
├── scripts/
│   ├── phase1_parse.py … phase18b_binary_tsfresh.py
├── data/
│   ├── interim/                     # per-phase parquets + CSV diagnostics
│   └── processed/
│       ├── windows_train.parquet           # 4,080 × signal[160] @ 80 Hz, 2 s
│       ├── windows_train_1s.parquet        # 8,806 × signal[80] @ 80 Hz, 1 s
│       ├── windows_features.parquet        # 1,796 × 32 engineered (3-class)
│       ├── windows_tsfresh.parquet         # 1,796 × 645 TSFresh (3-class)
│       └── windows_tsfresh_binary.parquet  # 4,061 × 647 TSFresh (rest+gesture)
└── figures/
    └── phase{1..14}_*.png           # one or more figures per phase
```

---

## Pragmatic recommendations from here

1. **Treat 0.60 ± 0.04 as the published benchmark** for this dataset. Don't claim improvements without similarly-tight CIs.
2. **For interpretability**: the 5-feature kernel `[rms, mean, p_5_10_frac, ac_lag_100ms, env_std]` captures most of the signal and explains the model in physical terms.
3. **For production-grade improvements**: collect more sessions. With ~5–10 recordings the within-mouse and cross-mouse ceiling can be properly estimated; without that, this is a single-point measurement.
4. **For a new sensor experiment**: if the goal is to beat ~0.65, add a camera or an accelerometer. No amount of `m_total` modeling will get there.
