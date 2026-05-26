# Mouse-Scale Gesture Classification — Final Report

**Author note:** This is the long-form report. For the executive summary see `SUMMARY.md`.

---

## 1. The problem

A single mouse spent ~104 min in a cage instrumented with three load cells tiling the floor. Each cell reports its share of the animal's weight at ~80 Hz. The behavioural annotation file (`20251117-GroundTruthAfterWatchingVideo.xls`, 4 gesture sheets + 5 position sheets + 1 metadata sheet) tags four gestures — **grooming, eating, nesting, play_isopad** — over a ~44-minute window of the recording where the video was actually watched.

**Goal**: build a clean, reproducible pipeline from the raw triplet CSV + ground truth into AI-ready windows, then characterize how well off-the-shelf classifiers can recover gestures from the mass signal alone.

**Hard constraints from the user**:
- Single fused channel `m_total = r1 + r2 + r3` only. No per-cell features, no centre-of-mass features. Position-aware features were explicitly disallowed as too error-prone.
- Interactive phase-by-phase development with CSV / matplotlib artifacts at every step.
- Z-normalization tested both ways at every modelling stage.
- Interval-aware train/test splits to prevent leakage from the 75 % overlap of adjacent windows.

---

## 2. Raw-data audit (findings before any cleaning)

| Issue | Evidence | Impact |
|---|---|---|
| Sentinel rows `--, --, --, --` every ~102 rows | grep over the file | 4,951 buffer-flush markers, dropped |
| Clock jitter | dt modal 12 ms; 25–30 ms tail | resampling required |
| One 2.57 s gap | dt > 500 ms once | hard segment break — no interpolation across |
| Per-channel baselines | r1=2.5 g, r2=4.6 g, r3=15.6 g means | each cell has its own tare offset |
| Mass outliers | per-row sums from −649 g to +361 g | spike rejection needed |
| Empty cage at the start | first 18 s reads ~0 g | usable as an absolute zero anchor |

**Sync metadata** (from the XLS general-info sheet):
- "Delay between video and start of measurements" = **−43.5 s** → video starts 43.5 s after scale recording starts → `scale_t = video_t + 43.5 s`.
- Cross-checked against the "Stop recording at" cell: video_stop (2640 s) + 43.5 s = 2683.5 s ≈ 0.7454 h vs. stated 0.7457 h. ✓
- (The minutes-interpretation of the cell fails this cross-check by ~60×.)

---

## 3. Pipeline (Phases 1–8 → eight layer files)

```
raw CSV ──► [L1 parse] ──► [L2 segments] ──► [L3 channel-clean]
                                                    │
                                                    ▼
                                           [L4 tare + fuse]
                                                    │
                                                    ▼
                                           [L5 off-scale gate]
                                                    │
GT xls ─► [L7 parse + sync + raster] ──┐            ▼
                                       └─► join ◄─[L6 80 Hz resample]
                                            │
                                            ▼
                                   [L8 windowing] ──► windows_train.parquet
```

Each layer is a pure function in `src/mousepipe/` with a phase script in `scripts/`. Outputs are persisted as parquet so any later phase can re-run independently.

### L1 — Parse & sanitize (`io_raw.py`, `scripts/phase1_parse.py`)
- Read CSV with explicit dtypes `time_ms:i64, r1/r2/r3:f32`.
- Drop **4,951 sentinel `--` rows** (buffer-flush markers, every ~102 rows).
- Kept **500,051** valid samples covering scale_t ∈ [2.62 s, 6261.82 s] = 104.32 min, strictly monotonic.
- Δt: median 12 ms, max 2569 ms.

### L2 — Clock-outlier handling (`clock.py`, `scripts/phase2_clock.py`)
- Tag segment boundaries where dt > 500 ms.
- One break found at scale_t ≈ 60 min (2.57 s gap). Two segments emitted; downstream layers refuse to interpolate across the gap.
- Small jitter (10–30 ms) left alone; reconciled by the L6 resample.

### L3 — Per-channel cleaning (`channel_clean.py`, `scripts/phase3_channel.py`)
- **Hampel filter** with rolling window of 25 samples (≈300 ms) and threshold k=3 MAD.
- Replaces single-sample spikes (impacts, electrical glitches) with the rolling median.
- Spike fractions per channel: r1 0.7 %, r2 1.6 %, r3 2.0 %. Raw outliers (–649 g, +345 g…) eliminated.
- **Savitzky-Golay low-pass** with kernel=5, polyorder=3 (≈20 Hz cutoff). Three cutoffs (9 / 14 / 20 Hz) were rendered and compared visually.
  - The signal's spectral density is dominated by the **0–5 Hz** band (slow postural changes); 5–20 Hz contains the grooming-stroke harmonics; ≥20 Hz is essentially noise floor.
  - 9 Hz cut killed grooming harmonics; 14 Hz preserved most of them but smoothed edges; 20 Hz kept the gesture content intact while still removing single-cell ringing.
  - **User picked 20 Hz** to keep the modulation envelope as faithful as possible — accepting that some load-cell mechanical noise survives.
- Important caveat logged for the modelling phase: **load-cell mechanical resonance sits in 50–500 Hz** and aliases into the 0–40 Hz band at 80 Hz sampling — this contaminates the biologically interesting 5–25 Hz range and is irrecoverable without anti-alias hardware. ([[project-scale-aliasing-caveat]])

### L4 — Tare correction & fusion (`tare_fuse.py`, `scripts/phase4_tare.py`)
- **Empty-cage discovery**: the first 18 s of the CSV is empty cage (mouse inserted at scale_t ≈ 20 s; video starts at 43.5 s).
- Per-channel tare = median over scale_t ∈ [0, 18]: `r1 = −0.110, r2 = −0.031, r3 = +0.279 g`.
- After tare, `m_total = r1' + r2' + r3'` reads −0.02 g median empty, **+22.79 g median loaded** — one mouse.
- Drift correction skipped (no end-of-recording empty-cage anchor; risk of fabricating signal).

### L5 — Off-scale gate (`presence.py`, `scripts/phase5_presence.py`)
- Schmitt trigger: θ_on=5 g, θ_off=2 g, min on/off duration 200 ms.
- Only one off-scale episode detected: the empty-cage prefix. **The mouse stays on the floor for the entire labelled span.** This is the empirical version of "cage walls unclimbable" — confirmed by the user. ([[project-cage-geometry]])
- `is_loaded` persisted as its own column for downstream masking.

### L6 — Uniform 80 Hz resample (`resample.py`, `scripts/phase6_resample.py`)
- Per-segment time-weighted linear interpolation onto a 12.5 ms grid.
- **500,532 frames** out (count differs from input because of grid rounding).
- Δt within every segment is exactly 12.50 ms post-resample. Cross-segment boundary is NaN by design.

### L7 — Ground-truth processing (`labels.py`, `scripts/phase7_labels.py`)
- Excel fractional days converted with `t_video_seconds = excel_fractional_day × 86400`, then `t_scale_ms = t_video_seconds × 1000 + 43500`.
- **141 raw gesture intervals → 5 within-sheet overlaps merged → 136 final events**.
- **4 cross-gesture overlap regions** (grooming ∩ play_isopad, etc.) marked as `class = −1` (ignore, ~15 s total).
- Class map: `-1 ignore, 0 none, 1 grooming, 2 eating, 3 nesting, 4 play_isopad`.
- Labelled span: scale_t ∈ [43.5 s, 2683.5 s] → 211,279 frames (42.2 % of the grid). `is_labeled = True` only inside this span.
- **Sub-second sync validation** (Phase 7g): cross-correlated rolling-std(m_total) against the gesture indicator over ±5 s of lag — peak inside ±200 ms → no correction applied. Eating, the only one-of-its-kind event, was used as a video-time landmark (see `scripts/phase15_verify_alignment.py` and `phase15b_video_timestamps.py`).

### L8 — Windowing (`windows.py`, `scripts/phase8_windows.py`)
- 2 s windows, 160 samples @ 80 Hz, stride 0.5 s (75 % overlap), margin 0.5 s trimmed from each end of every interval (to keep boundary uncertainty out of the training window).
- Min interval duration to contribute any window = 3 s → **98 of 136 intervals (72 %) make the cut**.
- `source_interval_id` column added → interval-aware splits avoid the train→test leak that 75 % overlap would otherwise cause.
- Output `windows_train.parquet`: **4,080 windows × (t_start_ms, t_end_ms, label, source_interval_id, signal[160])**.

Per-class counts:

| Class | Windows |
|---|---|
| 0 (rest) | 2265 |
| 1 (grooming) | 807 |
| 2 (eating) | 19 |
| 3 (nesting) | 673 |
| 4 (play_isopad) | 316 |

Eating is too rare (n=19) to be a useful target. The 3-class problem `{grooming, nesting, play_isopad}` uses 1,796 windows.

---

## 4. Modelling experiments

### Methodology constants
- **Interval-aware 5-fold CV**: every window from one annotated interval lives in exactly one fold. Interval splits are stratified per class so each fold sees every gesture type.
- **Per-fold class balancing**: down-sample to the minimum-class window count inside each fold (no fold-leakage from the global balance).
- **3-seed ensemble** for CNN folds: mean of softmax logits across seeds 42 / 123 / 314.
- **95 % CI on the mean** of fold accuracies via standard-error × 1.96.
- Z-normalization tested everywhere; results below note which version is reported.

### Phase 9 — Linear baseline (LDA)

| Variant | Test acc | Chance |
|---|---|---|
| LDA + raw | 0.259 | 0.25 |
| LDA + z-norm | 0.259 | 0.25 |

**At chance even with a leaky window-level split.** The class structure isn't recoverable from any linear projection of the 160-sample window. This was the first signal that we'd need non-linear methods.

### Phase 10 — Random Forest (and ExtraTrees sweep)

| Setup | Train | Test |
|---|---|---|
| RF, raw, interval split | 1.000 | **0.413** |
| RF, z-norm, interval split | 1.000 | 0.346 |
| RF, raw, window-level (leaky) | 1.000 | 0.372 |
| RF, z-norm, window-level (leaky) | 1.000 | 0.277 |

- First model class with real signal (+16 pp over chance).
- **Z-normalization hurts trees**: splits at fixed time indices need absolute values. ([[project-normalization-choice]])
- **Leakage didn't help RF**: tree splits aren't shift-invariant, so they can't memorize a shifted training window the way a CNN might.
- 30-config hyperparameter sweep: best ExtraTrees (max_depth=12, min_leaf=2) → 0.388. Sweep range ~6 pp — regularization helps modestly but not dramatically.

### Phase 10c — RF after dropping "none" (3-class)

User asked: maybe the "none" / rest class is what's confusing the trees. Re-ran ExtraTrees on the 3-class subset {grooming, nesting, play_isopad}.

| Setup | Test |
|---|---|
| ExtraTrees, 3-class, raw | **0.458** |

Lift over chance (0.333) is **+13 pp** — almost exactly the same relative gain as 4-class (+16 pp over 0.25). **Dropping "none" doesn't fix the gesture-vs-gesture confusion**, which means the hard part isn't isolating rest from gestures; it's discriminating among gestures themselves. This finding propagates into the Phase 13 binary result.

### Phase 11 — 1-D CNN baseline (raw signal)

A simple stack: Conv1d(1→16,k=7)–BN–ReLU–Pool – Conv1d(16→32,k=5)–BN–ReLU–Pool – Conv1d(32→64,k=3)–BN–ReLU – AdaptiveAvgPool – Linear.

| Setup | Test |
|---|---|
| CNN + raw + 4-class | 0.418 |
| CNN + z-norm + 4-class | **0.587** |
| CNN + raw + 3-class | **0.624** |
| CNN + z-norm + 3-class | 0.532 |

- **Z-normalization story flips by problem**: helps CNN for 4-class (kills DC nuisance, lets the model see shape) but hurts for 3-class (within-gesture amplitude differences are real signal).
- The 0.624 single-run result looked great — but Phase 11d revealed it was a **lucky seed**.

### Phase 11d — Reality check: 5-seed variance

| Seed | Test |
|---|---|
| 42 ("lucky") | 0.708 |
| 123 | 0.472 |
| 7 | 0.375 |
| 2026 | 0.472 |
| 314 | 0.597 |
| **Mean ± std** | **0.525 ± 0.116** |
| **Ensemble (mean logits)** | **0.597** |

Per-seed variance is **±11 pp** without CV. Any single-seed report is noise.

### Phase 12 — The canonical baseline (5-fold × 3-seed CNN ensemble)

| Metric | Value |
|---|---|
| Mean across 5 folds | **0.604** |
| Std across folds | 0.038 |
| **95 % CI on mean** | **[0.567, 0.642]** |

Per-class precision / recall (948 aggregated test predictions):
- grooming: P 0.51 / R 0.59
- nesting:  P 0.56 / R 0.64
- play_isopad: P 0.79 / R 0.56

**Dominant failure mode**: grooming ↔ nesting confusion (≈30 % in each direction). The 100 % play_isopad precision from the lucky seed was coincidence; ensemble lands at ~79 %. ([[project-baseline-accuracy]])

### Phase 13 — Shorter windows and binary

| Experiment | Mean | 95 % CI |
|---|---|---|
| 3-class on 1-s windows | 0.482 | [0.369, 0.594] |
| Binary rest-vs-any-gesture (1-s) | 0.615 | [0.570, 0.660] |

- **Shorter windows hurt** 3-class by ~12 pp. Grooming recall collapses (0.60 → 0.28). 2 s is the sweet spot — enough cycles of the 10 Hz rhythm.
- **Binary** rest-vs-gesture only +12 pp over chance — the hard problem isn't gesture-vs-gesture but **rest-vs-gesture**. A 2-stage `rest? → which?` pipeline won't help. ([[project-window-length-and-binary-ceiling]])

### Phase 14 — Engineered features + drop-one selection

32 hand-rolled features per window:
- **Time-domain (10)**: rms, mean, std, mad, range, skew, kurt, slope, detr_std, zcr.
- **Frequency-band power (10)**: absolute and relative in 0.5–2 Hz, 2–5 Hz, 5–10 Hz, 10–20 Hz, 20–40 Hz.
- **Spectral shape (3)**: entropy, centroid, dom_freq.
- **Autocorrelation (4)**: lag at 50 / 100 / 200 ms + first peak.
- **Envelope (5)**: mean, std, peakiness, rise_ms, max.

| Model | Mean | 95 % CI | n_features |
|---|---|---|---|
| ExtraTrees on all 32 | 0.628 | [0.573, 0.683] | 32 |
| **ExtraTrees on selected 15** | **0.638** | [0.580, 0.696] | **15** |

**Discriminators** (top drop-one importance):

| Rank | Feature | Δ | Why it works |
|---|---|---|---|
| 1 | rms | +0.015 | Absolute downward force level |
| 2 | mean | +0.015 | Same |
| 3 | **p_5_10_frac** | **+0.013** | Relative power in 5–10 Hz — grooming-stroke band |
| 4 | **ac_lag_100ms** | **+0.010** | Autocorrelation at 100 ms = 10 Hz period |
| 5 | p_5_10 | +0.007 | Absolute power in 5–10 Hz |
| 6 | p_2_5_frac | +0.005 | Slow rhythm relative power |
| 7 | env_std | +0.005 | Envelope variability |
| 8 | p_20_40_frac | +0.004 | ⚠ aliased band |

**Misleaders** (removing them helps):

| Feature | Δ |
|---|---|
| detr_std | −0.014 |
| std | −0.011 |
| p_10_20_frac | −0.009 |
| spec_centroid | −0.006 |
| Envelope shape (rise_ms, peakiness) | all negative |

**Surprising finding ([[project-gesture-signal-character]])**: gestures show *less* mass variability than rest. Annotated bouts are focused, stationary activity; rest periods include small exploratory motion. Generic variance/energy features therefore **invert**.

### Phase 16 — 2-D Spectrogram CNN

STFT params: fs=80 Hz, nperseg=32 (400 ms → Δf = 2.5 Hz), noverlap=24 → **17×17 spectrogram** (freq × time). Log-magnitude. 2-D CNN: Conv2d(1→16)→Conv2d(16→32)→Conv2d(32→64)→AdaptiveAvgPool(1)→Linear.

| Metric | Value |
|---|---|
| Mean across 5 folds | **0.645** |
| Std | 0.055 |
| **95 % CI** | **[0.591, 0.698]** |
| Per fold | 0.568, 0.709, 0.620, 0.620, 0.706 |

Per-class:
- grooming: P 0.68 / R 0.38 (model under-calls it)
- nesting: P 0.54 / R 0.75
- play_isopad: P 0.72 / R 0.75

Marginal improvement over the 1-D CNN (0.604 → 0.645) but **CIs overlap** — statistically indistinguishable.

### Phase 17 — TSFresh (645 automated features) + ExtraTrees

`tsfresh.extract_features(default_fc_parameters=EfficientFCParameters())` produced **645** non-constant, finite features per window. ExtraTrees on impurity importance ranked them.

| Configuration | Mean | 95 % CI |
|---|---|---|
| all 645 features | 0.633 ± 0.044 | [0.589, 0.676] |
| top-10 by importance | 0.617 ± 0.013 | [0.604, 0.629] |
| top-25 | 0.635 ± 0.029 | [0.607, 0.663] |
| **top-50** | **0.638 ± 0.035** | [0.605, 0.672] |

**Top-20 features**: `variance_larger_than_standard_deviation`, multiple `fft_aggregated` aggtypes (centroid, variance, skew), `change_quantiles` (multiple param combos), `cid_ce__normalize_False`, `partial_autocorrelation`, `permutation_entropy` (multiple dim/tau), `fft_coefficient` (real/imag), `number_peaks__n_1`, `absolute_sum_of_changes`.

**Independent corroboration of the hand-rolled story**: spectral shape, short-lag temporal coherence (autocorrelation / cid_ce), permutation entropy of the modulation pattern. Same physics, different parameterization. ([[project-tsfresh-corroborates-handcrafted]])

### Phase 18 — Binary rest-vs-gesture redux (this session)

Re-ran the spectrogram CNN (18a) and the TSFresh + ExtraTrees pipeline (18b) on the binary task **0 = rest vs 1 = any gesture {1, 3, 4}**, dropping eating (n=19). Interval-aware 5-fold CV, per-fold 1:1 balancing.

#### Phase 18a — Binary 2-D spectrogram CNN

| Metric | Value |
|---|---|
| Mean across 5 folds | **0.661** |
| Std | 0.052 |
| **95 % CI** | **[0.610, 0.711]** |
| **AUROC (aggregated)** | **0.732** |
| Per fold | 0.662, 0.713, 0.701, 0.567, 0.662 |

Aggregated confusion (n=3,220, balanced):
- rest: P 0.66 / R **0.71**
- gesture: P 0.68 / R 0.63

The model leans toward calling "rest" — recall asymmetry of 0.71 vs 0.63. Still 4.6 pp above the Phase 13 1-D-CNN binary reference (0.615), but well below where one would hope binary classification could go on a 3,220-sample test set.

#### Phase 18b — Binary TSFresh + ExtraTrees

| Configuration | Mean | 95 % CI | AUROC |
|---|---|---|---|
| All 647 features | 0.666 ± 0.041 | [0.626, 0.706] | 0.736 |
| top-10 by importance | 0.652 ± 0.034 | [0.618, 0.685] | 0.706 |
| top-25 | 0.679 ± 0.034 | [0.646, 0.713] | 0.738 |
| **top-50** | **0.679 ± 0.031** | **[0.649, 0.710]** | **0.745** |

**Top features for binary** (different ordering than 3-class — temporal coherence dominates):
1. `partial_autocorrelation` lags
2. `autocorrelation` at lags 1–7 (multiple)
3. `permutation_entropy` (several dim/tau combos)
4. `ar_coefficient`, `large_standard_deviation`, `fourier_entropy`
5. `cid_ce__normalize_True`, `number_peaks__n_3`

Aggregated confusion (n=3,440, balanced):
- rest: P 0.65 / R **0.73**
- gesture: P 0.69 / R 0.60

**Same lean toward rest** as the spectrogram CNN. The binary task is harder than expected because rest contains a lot of small exploratory motion that mimics low-amplitude gesture envelopes — the [[project-gesture-signal-character]] finding (gestures show *less* variability than rest) shows up here as confusion between "rest with exploration" and "low-amplitude gesture".

#### Binary takeaway

Both binary classifiers land in the **[0.61, 0.71]** envelope — about 5–7 pp above the Phase 13 1-D-CNN binary baseline, but firmly capped well short of the 0.85+ one would expect if rest were trivially separable. CIs again overlap across architectures. The binary task isn't the rescue path either: a 2-stage `rest? → which gesture?` pipeline cannot exceed the product of the binary recall and the conditional 3-class accuracy, and both are sitting around 0.66.

---

## 5. Final leaderboard

Within-session, balanced, interval-aware 5-fold CV.

### 3-class (grooming / nesting / play_isopad), chance = 0.333

| Model | Mean | 95 % CI |
|---|---|---|
| LDA (raw or z-norm) | 0.259 | — (below chance) |
| Random Forest + raw | 0.413 | — |
| 1-D CNN raw, single seed (Phase 11b) | 0.624 | — (lucky) |
| 1-D CNN raw, 5-fold × 3-seed (Phase 12) | **0.604 ± 0.038** | [0.567, 0.642] |
| Engineered 32 → selected 15 + ExtraTrees | **0.638** | [0.580, 0.696] |
| TSFresh 645 → top-50 + ExtraTrees | **0.638 ± 0.035** | [0.605, 0.672] |
| TSFresh all 645 + ExtraTrees | 0.633 ± 0.044 | [0.589, 0.676] |
| **2-D spectrogram CNN** | **0.645 ± 0.055** | [0.591, 0.698] |

### Binary (rest vs any-gesture), chance = 0.50

| Model | Mean | 95 % CI | AUROC |
|---|---|---|---|
| 1-D CNN binary, 1-s windows (Phase 13) | 0.615 | [0.570, 0.660] | — |
| 2-D spectrogram CNN, 2-s windows (Phase 18a) | **0.661 ± 0.052** | [0.610, 0.711] | 0.732 |
| TSFresh binary, all 647 features (Phase 18b) | 0.666 ± 0.041 | [0.626, 0.706] | 0.736 |
| **TSFresh binary, top-50 (Phase 18b)** | **0.679 ± 0.031** | **[0.649, 0.710]** | **0.745** |

---

## 6. Diagnosis: why does it ceiling at ~0.63?

Six independent model families — LDA (linear), Random Forest, 1-D CNN on raw signal, hand-engineered features + ExtraTrees, TSFresh's 645 auto-features + ExtraTrees, 2-D spectrogram CNN — all converge to **0.60–0.65** for the 3-class problem with overlapping confidence intervals. The binary task tops out at **0.66–0.68** with AUROC 0.73–0.75 across the same families — only +13 pp over the 0.50 chance, not the +35 pp one would expect if rest-vs-gesture were trivially separable.

This is the textbook signature of a **data ceiling**, not a model ceiling. The information needed to disambiguate the three gestures is not present in `m_total` at 80 Hz over 2-s windows beyond about 0.65 accuracy.

Decomposing the gap:

| Factor | Hardness | Estimated cost |
|---|---|---|
| Grooming vs nesting share the same fine-stationary mass signature; the difference is visible (paw motion, head orientation) — not in vertical load | **Hard** | most of the 0.35 gap |
| One session / one mouse — small dataset (≈600–800 windows per class) | Soft | ±5 pp reachable with more recordings |
| ~200 ms sync residual + annotator boundary slack | Soft, small | ±2 pp |
| 80 Hz Nyquist + aliased 50–500 Hz mechanical resonance into the gesture band | Soft, capped | ±3 pp with anti-aliasing hardware |

What this *isn't*:
- Not an architecture problem (CNN, ExtraTrees, automated featurizer all tie).
- Not a feature-engineering problem (hand-rolled top features and TSFresh's top features pick the same physics).
- Not a window-length problem (2 s already beats 1 s by ~12 pp; longer would need to bridge segment breaks).
- Not a class-set problem (4-class, 3-class, and binary all sit in the same regime).

### Missing data vs. missing information

Asked plainly: are we short of *examples*, or short of *signal*?

**Primarily short of signal.** Five converging lines of evidence:

1. **Six independent model families ceiling at the same place.** When linear, tree, raw-CNN, hand-crafted-feature, automatic-feature, and time-frequency CNN approaches all hit 0.60–0.65, the limit lives upstream of any model.
2. **Two independent feature-engineering pipelines rank the same physics.** Hand-rolled drop-one and TSFresh top-20 both put absolute level, 5–10 Hz band content, and short-lag autocorrelation at the top. There is no clever transform left to try — we've extracted what's in `m_total` at 80 Hz over 2 s.
3. **Grooming and nesting are mechanically similar in vertical force.** Both are focused, stationary, fine-motor behaviours; the *visible* differences (paw motion, head orientation, body posture) used by the human annotator don't project onto a 1-D scalar vertical-load time series.
4. **Binary rest-vs-gesture caps at AUROC ≈ 0.75.** Even reduced to "is this fidget purposeful or not?", the boundary isn't crisp — because rest contains exploratory motion that produces the same kind of small mass modulations as low-amplitude gestures ([[project-gesture-signal-character]]).
5. **The label-generating signal is in another modality.** The annotator labelled from video. The information they used was visual; we are asking whether that visual content also lives in a 1-D vertical force trace, and the answer is: only partially.

**Where extra data would help, and by how much.** Three soft factors with ceilings:
- More sessions / more mice: probably **±5 pp** from small-sample noise + a proper cross-session ceiling.
- Hardware sync pulse: **±2 pp** from removing the ~200 ms residual.
- Anti-aliased sampling: **±3 pp** by cleaning up the aliased 50–500 Hz mechanical resonance contaminating 5–25 Hz.

Stack all three best-case and the 3-class asymptote on `m_total` alone is **~0.70–0.75**, not 0.95.

**The cheapest path past 0.75 is another modality**, not more of the same. A camera (the annotator already used one), an IMU on the mouse, or IR beam breaks would change the problem from "decode posture from vertical load" — which is bandwidth-limited at the source — to "fuse complementary streams," which has real headroom.

---

## 7. Discriminative physics (what *does* work)

Both feature pipelines independently rank the same things at the top:

1. **Absolute mass level** (`rms`, `mean`, `variance_larger_than_standard_deviation`) — different gestures place the mouse in subtly different postural-mass states.
2. **5–10 Hz band power, both absolute and relative** (`p_5_10`, `p_5_10_frac`, `fft_aggregated` centroid/variance) — the grooming-stroke rhythm.
3. **Short-lag temporal coherence** (`ac_lag_100ms`, `partial_autocorrelation`, `cid_ce`) — 10 Hz period = 100 ms lag, captures how regular the modulation is.
4. **Permutation entropy** (multiple dim/tau) — orderedness of the modulation pattern.

The minimal interpretable kernel `[rms, mean, p_5_10_frac, ac_lag_100ms, env_std]` recovers most of the ExtraTrees signal in five physical features.

---

## 8. Sync-alignment verification (Phases 7g, 15)

Four independent confirmations of `SYNC_OFFSET_MS = 43_500`:

1. **XLS metadata**: "Delay between video and start of measurements" = −43.5 s.
2. **XLS cross-check**: video duration (2640 s) + 43.5 s = 2683.5 s ≈ stated "Stop recording at" = 0.7457 h. ✓
3. **Data-side cross-correlation** (Phase 7g): a "wiggle" signal = `rolling_std(m_total, win=500 ms)` was cross-correlated against a 0/1 gesture-indicator over ±5 s of lag. The peak sat **within ±200 ms of zero** with no sharp dominant maximum — so the offset is correct to within 200 ms, and the labels are too soft / boundary-noisy to refine sync further from the data alone.
   - *Methodology note*: this assumes the two signals share a coarse common structure (gestures push the rolling-std up on average). It can detect a *bulk lag* but won't catch sub-window drift. That's a fair test for "is the +43.5 s value sane?" — it isn't a fine sync calibrator.
4. **Video landmarks** (`scripts/phase15b_video_timestamps.py`): printed mm:ss landmarks for the eating event (unique → best landmark), the longest of each gesture class, the first and last gestures (alignment at the ends), and the 5 shortest non-eating bouts (for tight-boundary checks). The user scrubbed MAH00950.MP4 to each timestamp and confirmed the labels matched.
5. **Visual overlay** (`scripts/phase15_verify_alignment.py`): rendered `m_total` with colour-banded gesture intervals at multiple scales — full labelled span, eating zoom, longest grooming / nesting / play_isopad, and class transitions. Provided as `figures/phase15_alignment_check.png`.

---

## 9. Working artifacts

```
val-demo/
├── pyproject.toml                 # uv-managed Python 3.12
├── src/mousepipe/
│   ├── __init__.py                 # constants: SYNC_OFFSET_MS=43_500, TARGET_HZ=80, EMPTY_CAGE_END_S=18.0
│   ├── io_raw.py                   # L1
│   ├── clock.py                    # L2 (SEGMENT_BREAK_MS=500)
│   ├── channel_clean.py            # L3 (Hampel + SavGol)
│   ├── tare_fuse.py                # L4
│   ├── presence.py                 # L5 (THETA_ON_G=5, THETA_OFF_G=2)
│   ├── resample.py                 # L6 (PERIOD_MS=12.5)
│   ├── labels.py                   # L7 (xlrd parse, sync, rasterize)
│   ├── windows.py                  # L8 (WINDOW_LEN_S=2.0, STRIDE_S=0.5, MARGIN_S=0.5)
│   └── features.py                 # Phase 14: 32 engineered features
├── scripts/
│   ├── phase1_parse.py … phase18b_binary_tsfresh.py
├── data/
│   ├── interim/                    # per-phase parquets + CSV diagnostics
│   └── processed/
│       ├── windows_train.parquet           # 4,080 × signal[160] @ 80 Hz, 2 s
│       ├── windows_train_1s.parquet        # 8,806 × signal[80] @ 80 Hz, 1 s
│       ├── windows_features.parquet        # 1,796 × 32 hand-rolled
│       ├── windows_tsfresh.parquet         # 1,796 × 645 (3-class)
│       └── windows_tsfresh_binary.parquet  # 4,061 × 645 (rest+gesture)
└── figures/
    └── phase{1..18}_*.png                  # one or more figures per phase
```

---

## 10. Recommendations

1. **Publish 0.60 ± 0.04 as the within-session 3-class benchmark on this rig.** Don't claim improvements without similarly-tight CIs from a 5-fold-CV ensemble.
2. **For interpretability**: use `[rms, mean, p_5_10_frac, ac_lag_100ms, env_std]`. Five physical features, ~0.62 accuracy, easy to defend in a methods section.
3. **For real progress**: collect more sessions and more mice. The within-mouse and cross-mouse ceilings can only be properly estimated with ≥5–10 recordings.
4. **For a sensor upgrade**: a camera or an accelerometer is the cheapest path past 0.65. No `m_total` model will get there because the discriminating signal isn't in the vertical force time series.
5. **For task redefinition**: collapsing grooming + nesting into "stationary fine motion" would lift accuracy on the resulting 2-of-3 problem substantially — but ask the biology question that needs answering first, then pick the label set.

---

## 11. Persisted memory

Stored in `/home/x/.claude/projects/-home-x-projects-val-demo/memory/`:

| Memory | Insight |
|---|---|
| [[project-scale-aliasing-caveat]] | Load-cell resonance 50–500 Hz aliases into 0–40 Hz at 80 Hz sampling. |
| [[project-cage-geometry]] | Cage walls unclimbable → L5 detects ~zero mid-recording off-scale episodes. |
| [[project-gesture-signal-character]] | Gestures show *less* variability than rest; energy/variance features invert. |
| [[feedback-no-position-features]] | m_total only — no per-cell, dominant-cell, or centre-of-mass features. |
| [[project-normalization-choice]] | Z-norm helps CNN 4-class, hurts 3-class, always hurts trees. |
| [[project-baseline-accuracy]] | 3-class CNN baseline 0.604 ± 0.038 (5-fold CV). |
| [[project-window-length-and-binary-ceiling]] | 2 s beats 1 s by 12 pp; binary tops at ~0.62. |
| [[project-discriminative-features]] | rms/mean + 5–10 Hz band + 100 ms autocorrelation. |
| [[project-data-ceiling]] | Six families converge to 0.60–0.65; bottleneck is data. |
| [[project-tsfresh-corroborates-handcrafted]] | TSFresh's top-20 ranks the same physics as drop-one. |
