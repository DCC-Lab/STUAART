"""Phase 9 — Simple LDA baseline.

Classes used: 0 (rest), 1 (grooming), 3 (nesting), 4 (play_isopad). Class 2 (eating) excluded.

Split: by INTERVAL (not by window) — all windows from the same gesture interval go
to the same fold. Avoids data leakage from the 75 % window overlap.

Balancing: undersample each class to the minimum count, separately within train and test.

Two LDA models: raw signal vs per-window z-normalized signal.

Outputs:
  data/interim/phase9_lda_results.csv   — summary
  figures/phase9_lda_confusions.png     — two confusion matrices side-by-side
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

RNG_SEED   = 42
TEST_FRAC  = 0.20
CLASSES    = (0, 1, 3, 4)  # eating (2) dropped


def split_intervals_per_class(windows: pl.DataFrame, rng: np.random.Generator) -> tuple[set[int], set[int]]:
    """Return (train_intervals, test_intervals) — split intervals 80/20 within each class."""
    train: set[int] = set()
    test:  set[int] = set()
    for c in CLASSES:
        ids = (
            windows.filter(pl.col("label") == c)
                   .select("source_interval_id")
                   .unique()
                   .to_series()
                   .to_list()
        )
        rng.shuffle(ids)
        n_test = max(1, int(round(len(ids) * TEST_FRAC)))
        test_ids  = set(ids[:n_test])
        train_ids = set(ids[n_test:])
        test  |= test_ids
        train |= train_ids
    return train, test


def balance(windows: pl.DataFrame, rng: np.random.Generator) -> pl.DataFrame:
    """Undersample each class to the min count, sampling whole windows (within a split)."""
    counts = {c: int((windows["label"] == c).sum()) for c in CLASSES}
    n_min = min(counts.values())
    pieces = []
    for c in CLASSES:
        sub = windows.filter(pl.col("label") == c)
        idx = np.arange(sub.height)
        rng.shuffle(idx)
        pieces.append(sub[idx[:n_min].tolist()])
    return pl.concat(pieces).sample(fraction=1.0, shuffle=True, seed=rng.integers(0, 1 << 30))


def to_xy(windows: pl.DataFrame, normalize: bool) -> tuple[np.ndarray, np.ndarray]:
    X = np.array(windows["signal"].to_list(), dtype=np.float32)
    y = windows["label"].to_numpy().astype(int)
    if normalize:
        m = X.mean(axis=1, keepdims=True)
        s = X.std(axis=1, keepdims=True)
        s = np.where(s < 1e-6, 1.0, s)
        X = (X - m) / s
    return X, y


def train_and_eval(name: str, X_tr, y_tr, X_te, y_te) -> dict:
    lda = LinearDiscriminantAnalysis()
    lda.fit(X_tr, y_tr)
    pred = lda.predict(X_te)
    acc  = accuracy_score(y_te, pred)
    cm   = confusion_matrix(y_te, pred, labels=list(CLASSES))
    cm_norm = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    print(f"\n=== {name} ===")
    print(f"accuracy: {acc:.4f}")
    print(classification_report(y_te, pred, labels=list(CLASSES),
                                target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3))
    return {"name": name, "accuracy": acc, "cm": cm, "cm_norm": cm_norm,
            "y_te": y_te, "pred": pred}


def main() -> None:
    interim   = ROOT / "data" / "interim"
    processed = ROOT / "data" / "processed"
    figures   = ROOT / "figures"

    rng = np.random.default_rng(RNG_SEED)

    windows = pl.read_parquet(processed / "windows_train.parquet")
    print(f"total windows: {windows.height:,}")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"after dropping class 2: {windows.height:,}")

    train_ids, test_ids = split_intervals_per_class(windows, rng)
    train_raw = windows.filter(pl.col("source_interval_id").is_in(list(train_ids)))
    test_raw  = windows.filter(pl.col("source_interval_id").is_in(list(test_ids)))

    print()
    print(f"intervals: train={len(train_ids)}  test={len(test_ids)}")
    print("pre-balance window counts:")
    for c in CLASSES:
        n_tr = int((train_raw["label"] == c).sum())
        n_te = int((test_raw["label"]  == c).sum())
        print(f"  class {c} ({CLASS_TO_GESTURE[c]:>11}): train {n_tr:>5}  test {n_te:>5}")

    train = balance(train_raw, rng)
    test  = balance(test_raw,  rng)

    print()
    print(f"balanced: train={train.height}  test={test.height}")
    print(f"  per-class: train {train.height // len(CLASSES)}/class   test {test.height // len(CLASSES)}/class")

    # Train two models
    X_tr_raw,  y_tr = to_xy(train, normalize=False)
    X_te_raw,  y_te = to_xy(test,  normalize=False)
    X_tr_norm, _    = to_xy(train, normalize=True)
    X_te_norm, _    = to_xy(test,  normalize=True)

    r_raw  = train_and_eval("LDA on RAW windows",        X_tr_raw,  y_tr, X_te_raw,  y_te)
    r_norm = train_and_eval("LDA on Z-NORMALIZED windows", X_tr_norm, y_tr, X_te_norm, y_te)

    # Save summary
    pl.DataFrame([
        {"variant": "raw",        "accuracy": r_raw["accuracy"]},
        {"variant": "z-normalized", "accuracy": r_norm["accuracy"]},
    ]).write_csv(interim / "phase9_lda_results.csv")

    # ----- Figure: confusion matrices -----
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

    fig.suptitle("Phase 9 — LDA confusion matrices (row-normalized)", fontsize=13)
    fig_path = figures / "phase9_lda_confusions.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
