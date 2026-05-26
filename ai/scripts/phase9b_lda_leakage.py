"""Phase 9b — Same LDA as Phase 9 but with NAIVE WINDOW-LEVEL split (leaky).

Purpose: quantify how much the 75 % window-overlap inflates accuracy when train
and test windows are allowed to share source intervals.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

from mousepipe.labels import CLASS_TO_GESTURE

RNG_SEED  = 42
TEST_FRAC = 0.20
CLASSES   = (0, 1, 3, 4)


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


def train_and_eval(name, X_tr, y_tr, X_te, y_te):
    lda = LinearDiscriminantAnalysis()
    lda.fit(X_tr, y_tr)
    pred = lda.predict(X_te)
    acc = accuracy_score(y_te, pred)
    cm  = confusion_matrix(y_te, pred, labels=list(CLASSES))
    cm_n = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    print(f"\n=== {name} ===  accuracy = {acc:.4f}")
    print(classification_report(y_te, pred, labels=list(CLASSES),
                                target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3))
    return {"name": name, "accuracy": acc, "cm": cm, "cm_norm": cm_n}


def main():
    figures = ROOT / "figures"
    rng = np.random.default_rng(RNG_SEED)

    windows = pl.read_parquet(ROOT / "data" / "processed" / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"4-class windows: {windows.height:,}")

    # Balance the FULL pool first, then split at window level
    balanced = balance(windows, rng)
    print(f"balanced pool: {balanced.height}")

    # Naive window-level shuffle split
    idx = np.arange(balanced.height)
    rng.shuffle(idx)
    n_test = int(round(balanced.height * TEST_FRAC))
    test_idx, train_idx = idx[:n_test], idx[n_test:]
    train = balanced[train_idx.tolist()]
    test  = balanced[test_idx.tolist()]

    print(f"split: train={train.height}  test={test.height}")
    for c in CLASSES:
        print(f"  class {c} ({CLASS_TO_GESTURE[c]:>11}): train {int((train['label']==c).sum())}  test {int((test['label']==c).sum())}")

    # Same as phase 9
    Xt_r,  yt = to_xy(train, normalize=False)
    Xe_r,  ye = to_xy(test,  normalize=False)
    Xt_n,  _  = to_xy(train, normalize=True)
    Xe_n,  _  = to_xy(test,  normalize=True)

    r_raw  = train_and_eval("LDA on RAW (window-level split = LEAKY)",        Xt_r, yt, Xe_r, ye)
    r_norm = train_and_eval("LDA on Z-NORMALIZED (window-level split = LEAKY)", Xt_n, yt, Xe_n, ye)

    # Figure
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    for ax, r in zip(axes, (r_raw, r_norm)):
        cm = r["cm_norm"]
        im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(len(CLASSES)), names, rotation=20)
        ax.set_yticks(range(len(CLASSES)), names)
        ax.set_xlabel("predicted"); ax.set_ylabel("true")
        ax.set_title(f"{r['name']}\naccuracy = {r['accuracy']:.3f}  (chance = {1/len(CLASSES):.3f})")
        for i in range(len(CLASSES)):
            for j in range(len(CLASSES)):
                txt = f"{cm[i,j]:.2f}\n({r['cm'][i,j]})"
                ax.text(j, i, txt, ha="center", va="center",
                        color="white" if cm[i,j] > 0.5 else "black", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Phase 9b — Naive WINDOW-LEVEL split (allows train↔test leakage)", fontsize=13)
    p = figures / "phase9b_lda_leakage_confusions.png"
    fig.savefig(p, dpi=130); plt.close(fig)
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
