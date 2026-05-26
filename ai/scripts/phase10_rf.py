"""Phase 10 — Random Forest baseline (non-linear).

Same setup as Phase 9 (interval-aware 80/20 split, classes 0/1/3/4, balanced)
but with a Random Forest classifier on the raw m_total waveform.

Also runs the leaky window-level split for comparison so we can see whether a
non-linear model crashes through accuracy when overlap leaks between train/test.

Outputs:
  data/interim/phase10_rf_results.csv
  figures/phase10_rf_confusions.png
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

from mousepipe.labels import CLASS_TO_GESTURE

RNG_SEED  = 42
TEST_FRAC = 0.20
CLASSES   = (0, 1, 3, 4)
N_TREES   = 300


def split_by_interval(windows: pl.DataFrame, rng):
    train_ids, test_ids = set(), set()
    for c in CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        n_test = max(1, int(round(len(ids) * TEST_FRAC)))
        test_ids  |= set(ids[:n_test])
        train_ids |= set(ids[n_test:])
    return train_ids, test_ids


def balance(windows: pl.DataFrame, rng) -> pl.DataFrame:
    counts = {c: int((windows["label"] == c).sum()) for c in CLASSES}
    n_min = min(counts.values())
    pieces = []
    for c in CLASSES:
        sub = windows.filter(pl.col("label") == c)
        idx = np.arange(sub.height)
        rng.shuffle(idx)
        pieces.append(sub[idx[:n_min].tolist()])
    return pl.concat(pieces).sample(fraction=1.0, shuffle=True, seed=int(rng.integers(0, 1 << 30)))


def to_xy(windows: pl.DataFrame, normalize: bool):
    X = np.array(windows["signal"].to_list(), dtype=np.float32)
    y = windows["label"].to_numpy().astype(int)
    if normalize:
        m = X.mean(axis=1, keepdims=True)
        s = X.std(axis=1, keepdims=True)
        s = np.where(s < 1e-6, 1.0, s)
        X = (X - m) / s
    return X, y


def fit_and_score(name, X_tr, y_tr, X_te, y_te):
    clf = RandomForestClassifier(n_estimators=N_TREES, random_state=RNG_SEED, n_jobs=-1)
    clf.fit(X_tr, y_tr)
    pred = clf.predict(X_te)
    tr_acc = accuracy_score(y_tr, clf.predict(X_tr))
    te_acc = accuracy_score(y_te, pred)
    cm = confusion_matrix(y_te, pred, labels=list(CLASSES))
    cm_n = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    print(f"\n=== {name} ===  train acc = {tr_acc:.3f}  test acc = {te_acc:.3f}")
    print(classification_report(y_te, pred, labels=list(CLASSES),
                                target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3))
    return {"name": name, "train_acc": tr_acc, "test_acc": te_acc, "cm": cm, "cm_norm": cm_n}


def main():
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"
    rng = np.random.default_rng(RNG_SEED)

    windows = pl.read_parquet(ROOT / "data" / "processed" / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"4-class windows: {windows.height:,}    n_trees: {N_TREES}")

    # -------- A) Interval-aware split (honest) --------
    rng_a = np.random.default_rng(RNG_SEED)
    train_ids, test_ids = split_by_interval(windows, rng_a)
    tr_raw = windows.filter(pl.col("source_interval_id").is_in(list(train_ids)))
    te_raw = windows.filter(pl.col("source_interval_id").is_in(list(test_ids)))
    tr_a = balance(tr_raw, rng_a)
    te_a = balance(te_raw, rng_a)
    print(f"\n[INTERVAL-AWARE]  train {tr_a.height}  test {te_a.height}  "
          f"(per class: {tr_a.height // len(CLASSES)} / {te_a.height // len(CLASSES)})")

    Xtr_r, ytr = to_xy(tr_a, normalize=False)
    Xte_r, yte = to_xy(te_a, normalize=False)
    Xtr_n, _   = to_xy(tr_a, normalize=True)
    Xte_n, _   = to_xy(te_a, normalize=True)

    r_clean_raw  = fit_and_score("RF + RAW + interval-aware split",        Xtr_r, ytr, Xte_r, yte)
    r_clean_norm = fit_and_score("RF + Z-NORM + interval-aware split",     Xtr_n, ytr, Xte_n, yte)

    # -------- B) Leaky window-level split (for comparison) --------
    rng_b = np.random.default_rng(RNG_SEED)
    balanced_full = balance(windows, rng_b)
    idx = np.arange(balanced_full.height); rng_b.shuffle(idx)
    n_test = int(round(balanced_full.height * TEST_FRAC))
    te_b = balanced_full[idx[:n_test].tolist()]
    tr_b = balanced_full[idx[n_test:].tolist()]
    print(f"\n[WINDOW-LEVEL / LEAKY]  train {tr_b.height}  test {te_b.height}")

    Xtr_rb, ytrb = to_xy(tr_b, normalize=False)
    Xte_rb, yteb = to_xy(te_b, normalize=False)
    Xtr_nb, _    = to_xy(tr_b, normalize=True)
    Xte_nb, _    = to_xy(te_b, normalize=True)

    r_leak_raw  = fit_and_score("RF + RAW + window-level split (LEAKY)",    Xtr_rb, ytrb, Xte_rb, yteb)
    r_leak_norm = fit_and_score("RF + Z-NORM + window-level split (LEAKY)", Xtr_nb, ytrb, Xte_nb, yteb)

    # Persist
    pl.DataFrame([
        {"split": "interval-aware", "norm": "raw",   "train_acc": r_clean_raw["train_acc"],  "test_acc": r_clean_raw["test_acc"]},
        {"split": "interval-aware", "norm": "z",     "train_acc": r_clean_norm["train_acc"], "test_acc": r_clean_norm["test_acc"]},
        {"split": "window-leaky",   "norm": "raw",   "train_acc": r_leak_raw["train_acc"],   "test_acc": r_leak_raw["test_acc"]},
        {"split": "window-leaky",   "norm": "z",     "train_acc": r_leak_norm["train_acc"],  "test_acc": r_leak_norm["test_acc"]},
    ]).write_csv(interim / "phase10_rf_results.csv")

    # -------- Figure: four confusion matrices in a 2x2 grid --------
    fig, axes = plt.subplots(2, 2, figsize=(13, 11), constrained_layout=True)
    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    panels = [
        (axes[0, 0], r_clean_raw),
        (axes[0, 1], r_clean_norm),
        (axes[1, 0], r_leak_raw),
        (axes[1, 1], r_leak_norm),
    ]
    for ax, r in panels:
        cm = r["cm_norm"]
        im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(len(CLASSES)), names, rotation=20)
        ax.set_yticks(range(len(CLASSES)), names)
        ax.set_xlabel("predicted"); ax.set_ylabel("true")
        ax.set_title(f"{r['name']}\ntrain={r['train_acc']:.3f}  test={r['test_acc']:.3f}  (chance={1/len(CLASSES):.2f})",
                     fontsize=10)
        for i in range(len(CLASSES)):
            for j in range(len(CLASSES)):
                ax.text(j, i, f"{cm[i,j]:.2f}\n({r['cm'][i,j]})", ha="center", va="center",
                        color="white" if cm[i,j] > 0.5 else "black", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(f"Phase 10 — Random Forest (n_estimators={N_TREES}). Top row: honest. Bottom row: leaky.", fontsize=12)
    fig_path = figures / "phase10_rf_confusions.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
