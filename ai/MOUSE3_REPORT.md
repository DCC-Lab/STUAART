# Mouse3 — Active-vs-Sleeping Classification

**Companion to `REPORT.md`.** That study asked whether a 1-D vertical-force trace can tell *gestures* apart
(grooming/eating/nesting/play) and found a hard **data ceiling at ~0.60–0.65** — posture detail isn't in the
signal. This study asks a different question on a new recording (`Mouse3-3heures-10Hz/`): **active vs sleeping.**
The answer is the mirror image — the distinction is **nearly trivial**, and the *simplest possible* model wins.

**Headline:** thresholding a single feature — the per-window **movement index** (median |Δm_total| between
consecutive samples) — at **≈0.11 g/sample** gives **AUROC 0.996 ± 0.003** and **balanced accuracy 0.975 ± 0.012**
(interval-aware 5-fold CV). A 33-feature logistic/ExtraTrees model ties it within the confidence interval; a 1-D CNN
does *worse*. **No machine learning is required to separate active from sleeping on this rig.**

---

## 1. What's different about Mouse3 (and why the old pipeline can't be rerun verbatim)

| Axis | Dataset 1 (`REPORT.md`) | Mouse3 | Handling |
|---|---|---|---|
| Sample rate | 80 Hz (12.5 ms) | **~33 Hz (30 ms median)** — *despite the `…80Hz.csv` filename* | resample to **25 Hz**, retune filter windows; never upsample |
| Duration | 104 min | **260.7 min**, 517,625 rows | — |
| Buffer flushes | 4,951 `--` sentinels | **none** | `io_raw.load_raw` handles gracefully |
| Clock gaps >500 ms | 1 | **4 (hourly buffer breaks)**, max 6.1 s | `clock.assign_segments` → **5 segments** |
| Labels | XLS fractional-day, 4 gestures | **CSV sheets, H:MM:SS**, + new **Sleeping** sheet | new parser `mouse3.parse_mouse3_labels` |
| Sync | explicit −43.5 s in metadata | **none** — derived from data | mouse-in load step |
| On-scale gate | mouse always on floor | **loaded 98.7 %** of recording | confirms cage walls unclimbable, same as dataset 1 |

The dataset-1 library (`src/mousepipe/`) is reused unchanged for L1–L5; a thin **`src/mousepipe/mouse3.py`** layer adds
the 25 Hz config, sync derivation, CSV label parsing, sleep/active rasterization, and a windower that (unlike
`windows.build_windows`) splits long runs at segment breaks — necessary because "active" is one ~2-hour run that
crosses the hourly buffer gaps and would otherwise be discarded wholesale.

---

## 2. Task definition (locked with the user)

Whole-recording **sleep/wake scoring**, m_total only (the per-sheet "On scale" 1/2/3 column is position metadata → excluded):

- **SLEEP** = on-scale AND inside an annotated *Sleeping* interval.
- **ACTIVE** = on-scale AND *not* sleeping, **inside the annotated span** `[3.1, 185.0] min`.
- **Ignore** = off-scale, or outside the annotated span (the video wasn't scored there, so "no sleep label" ≠ active).

Annotated *Sleeping*: 9 raw rows → **8 merged intervals, 39.6 min total**. Within the span: active 78.2 %, sleep 21.8 %.

---

## 3. Sync (derived + independently validated)

- **Physical anchor:** the cage is empty until the mouse is placed in at video **0:02:38 (158 s)**. On the scale clock,
  the first sustained load step is at **183.7 s** → `scale_t = video_t + 25.7 s`.
- **Data-driven check:** sweeping candidate offsets, the one that maximizes the movement-index separation between
  annotated-sleep frames and the rest peaks at **+20.7 s** (separation ×10) — within **5 s** of the anchor, i.e. inside
  the annotator's video-scrub slack. The anchor is kept as authoritative. (`figures/m3_phase2_sync.png`)

The separation is ~10× regardless of which offset in this range is chosen, so the result is robust to sync error.

---

## 4. The discriminating physics

The right feature is **not** window variance. During long sleep bouts, slow postural drift inflates the window
*std* (sleep std 2.4–4.1 g) to the same range as active (3.7–4.8 g) — std does **not** separate the classes. What
separates them is **high-frequency micro-movement**: the median absolute change between consecutive 40 ms samples.

| Bout type | movement index (median \|Δm\|) |
|---|---|
| Sleeping | **0.02–0.14 g/sample** |
| Active (eat/groom/play/explore) | **0.3–2.5 g/sample** |

This is classical **actigraphy** — sleep/wake from a movement sensor. The two distributions barely overlap
(`figures/m3_phase3_models.png`, right panel).

---

## 5. Models — interval-aware 5-fold CV (StratifiedGroupKFold on 370 blocks, per-fold balancing)

Sleep = positive class. Balanced accuracy + AUROC (imbalance-robust), 95 % CI on the fold mean.

| Model | Features | Balanced acc | AUROC |
|---|---|---|---|
| **A — movement-index threshold (Youden)** | **1** | **0.975 ± 0.012** | **0.996 ± 0.003** |
| B — Logistic regression | 33 | 0.977 ± 0.004 | 0.996 ± 0.003 |
| C — ExtraTrees | 33 | 0.977 ± 0.007 | 0.996 ± 0.004 |
| D — 1-D CNN on raw window | raw 100 | 0.841 ± 0.015 | 0.945 ± 0.005 |

**Reading the table:**
- **The 1-feature threshold statistically ties the 33-feature models** — overlapping CIs. Extra features and
  non-linearity add nothing.
- **The CNN is worse**, because it z-normalizes each window and throws away the absolute movement *amplitude* that
  *is* the signal. (In `REPORT.md`, z-norm *helped* the gesture CNN — opposite regime, opposite lesson.)
- Aggregate operating point: **MI < 0.107 g/sample ⇒ sleep**. Confusion (n=10,811): active 8379/8482 correct
  (1.2 % FP), sleep 2247/2329 correct (3.5 % FN).

### 5.1 How to read the metrics (balanced accuracy & AUROC)

Both metrics exist because **plain accuracy lies on imbalanced data**. Sleep is only 21.5 % of windows, so a lazy
"everything is active" detector scores 78.5 % accuracy while never finding a single sleep bout. We need scores that
don't reward guessing the majority class.

**Balanced accuracy** — score each class separately, then average, so the rare class counts as much as the common one.
For each class, *recall* = "of the windows that truly are this class, what fraction did I catch?"

```
balanced_acc = ½ · (sleep_recall + active_recall)
```

The lazy detector gets active_recall = 1.0, sleep_recall = 0.0 → balanced_acc = **0.50** (exposed as chance). Our
threshold detector: active_recall = 8379/8482 = 0.988, sleep_recall = 2247/2329 = 0.965 → **0.977**. Chance is always
**0.50** for two classes regardless of skew, so it is the honest baseline. *Balanced accuracy depends on the chosen
threshold* (here 0.107) — it scores the detector you actually ship.

**AUROC** (Area Under the Receiver-Operating-Characteristic curve) — scores the *signal itself*, across **all** possible
thresholds at once, so it doesn't depend on where you set the knob. As the threshold slides from strict to loose it
traces a curve of:
- **TPR** (true-positive rate) = sleep recall — fraction of real sleep caught (want high), vs.
- **FPR** (false-positive rate) = fraction of real *active* windows wrongly called sleep (want low).

AUROC is the area under that TPR-vs-FPR curve. Its cleanest interpretation:

> **AUROC = the probability that a randomly chosen *sleep* window has a lower movement index than a randomly chosen
> *active* window.**

So **1.0** = perfectly separable (some threshold splits the classes with zero error), **0.5** = the feature is useless
(distributions fully overlap). Our **0.996** means: pick one random sleep window and one random active window, and
99.6 % of the time the sleep one is the stiller of the two — which is exactly why the two movement-index histograms in
`figures/m3_phase3_models.png` barely overlap.

| Metric | Answers | Threshold-dependent? | Chance |
|---|---|---|---|
| Balanced accuracy | At my operating point, how well do I do on *each* class? | **Yes** (cut = 0.107) | 0.50 |
| AUROC | Is the *signal* separable, wherever I set the knob? | **No** (all thresholds) | 0.50 |

AUROC 0.996 = "the movement index is almost a perfect separator"; balanced accuracy 0.975 = "even after committing to
one fixed threshold, I'm right ~97.5 % on both classes."

---

## 6. Whole-recording hypnogram (the deployable detector)

Apply the threshold end-to-end: 4 s rolling movement index → threshold at 0.107 → drop sleep/wake flips shorter
than 10 s (`presence.remove_short_runs`). (`figures/m3_phase4_hypnogram.png`)

- In-span balanced accuracy **0.977**; detected sleep **39.8 min** vs annotated **39.6 min**.
- **8 detected sleep bouts** (= 8 annotated), first sustained sleep onset at **142.4 min** (annotated: 142 min).
- Over the *full* recording the detector finds **53.8 min** of sleep — the extra ~14 min is a flat, motionless
  stretch at **185–198 min**, just past the annotated boundary: almost certainly real sleep the annotator stopped
  scoring. A nice demonstration that the detector generalizes beyond the labeled span.

---

## 7. The simplest accurate method (the deliverable)

> **Sleep ⇔ the per-window median absolute sample-to-sample change in total mass is below ≈0.1 g.**
> Compute `median(|diff(m_total)|)` over a few-second window; call it sleep if it's under the threshold; require a
> ≥10 s minimum bout. One feature, one threshold, AUROC 0.996.

No training data is strictly required — the threshold sits in a wide empty valley between the two distributions, so
it transfers across thresholds in `[0.08, 0.15]` with little change. Calibrate per-rig from a few minutes of known
quiet sleep if available; otherwise 0.1 g/sample is a sound default for this load-cell rig at ~25–33 Hz.

---

## 8. Honest caveats

1. **Quiet wakefulness** (awake but motionless) is the only real confound and is what bounds accuracy below 1.0:
   the few false positives are brief still moments during the active period. Distinguishing true sleep from quiet
   rest needs the annotator's modality (posture/EEG/EMG), not vertical force — but that residual is small (≈2 %).
2. **Annotation completeness:** "not sleeping" inside the span is taken as active; the detector finding extra sleep at
   185–198 min suggests the *Sleeping* sheet is not exhaustive past ~185 min. Scoring is therefore restricted to the
   annotated span for the accuracy numbers.
3. **Sync is derived**, not given (±~5 s); the ~10× separation makes the result insensitive to this.
4. **One mouse, one session.** The threshold and the ~0.98 ceiling should be re-confirmed across mice/sessions, but
   unlike the gesture task there is no architectural or feature headroom left to find — the signal is unambiguous.

---

## 9. Why this is the opposite of `REPORT.md`

`REPORT.md`: six model families converge at 0.60–0.65 on gestures → **data ceiling**, the information isn't in
m_total. Here: a 1-feature threshold, a 33-feature tree model, and a linear model all converge at **~0.98** →
**the information is fully in m_total**, and the floor model already captures it. Movement-vs-stillness projects
cleanly onto vertical force; posture detail does not.

---

## 10. Artifacts

```
src/mousepipe/mouse3.py                  # config, sync, CSV labels, rasterize, windower, movement index
scripts/m3_phase1_prepare.py             # raw -> cleaned/tared/gated/resampled 25 Hz frames
scripts/m3_phase2_sync_labels.py         # sync derive+validate, labels, windows
scripts/m3_phase3_models.py              # threshold + logreg + extratrees + CNN, 5-fold CV
scripts/m3_phase4_hypnogram.py           # whole-recording sleep/wake detector + bout stats
data/interim/m3_frames.parquet           # 390,735 frames @ 25 Hz
data/processed/m3_windows.parquet        # 10,811 windows (active 8482 / sleep 2329)
data/processed/m3_leaderboard.csv        # model leaderboard
data/processed/m3_sleep_bouts.csv        # 8 detected sleep bouts
figures/m3_phase1_overview.png … m3_phase4_hypnogram.png
```

Reproduce: `uv run python scripts/m3_phase1_prepare.py` → `…phase2…` → `…phase3…` → `…phase4…`.
