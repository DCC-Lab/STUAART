"""Phase 10b — Random Forest hyperparameter sweep.

Test whether regularizing RF actually changes test accuracy, or just lowers train
without lifting test. Same interval-aware split + raw signal as Phase 10's best.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, confusion_matrix

from mousepipe.labels import CLASS_TO_GESTURE

RNG_SEED  = 42
TEST_FRAC = 0.20
CLASSES   = (0, 1, 3, 4)


def split_by_interval(windows, rng):
    train_ids, test_ids = set(), set()
    for c in CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        n_test = max(1, int(round(len(ids) * TEST_FRAC)))
        test_ids  |= set(ids[:n_test])
        train_ids |= set(ids[n_test:])
    return train_ids, test_ids


def balance(windows, rng):
    counts = {c: int((windows["label"] == c).sum()) for c in CLASSES}
    n_min = min(counts.values())
    pieces = []
    for c in CLASSES:
        sub = windows.filter(pl.col("label") == c)
        idx = np.arange(sub.height); rng.shuffle(idx)
        pieces.append(sub[idx[:n_min].tolist()])
    return pl.concat(pieces).sample(fraction=1.0, shuffle=True, seed=int(rng.integers(0, 1 << 30)))


def to_xy(windows):
    X = np.array(windows["signal"].to_list(), dtype=np.float32)
    y = windows["label"].to_numpy().astype(int)
    return X, y


def main():
    interim = ROOT / "data" / "interim"
    figures = ROOT / "figures"
    rng = np.random.default_rng(RNG_SEED)

    windows = pl.read_parquet(ROOT / "data" / "processed" / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))

    train_ids, test_ids = split_by_interval(windows, rng)
    tr = balance(windows.filter(pl.col("source_interval_id").is_in(list(train_ids))), rng)
    te = balance(windows.filter(pl.col("source_interval_id").is_in(list(test_ids))), rng)
    Xtr, ytr = to_xy(tr); Xte, yte = to_xy(te)
    print(f"train {len(ytr)}  test {len(yte)}  per-class train {len(ytr)//4}  test {len(yte)//4}")

    rows = []

    # Grid sweep of RF
    max_depths    = [3, 5, 8, 12, 20, None]
    min_leaves    = [1, 5, 10, 20]
    for md in max_depths:
        for ml in min_leaves:
            clf = RandomForestClassifier(
                n_estimators=400, max_depth=md, min_samples_leaf=ml,
                random_state=RNG_SEED, n_jobs=-1,
            )
            clf.fit(Xtr, ytr)
            tr_a = accuracy_score(ytr, clf.predict(Xtr))
            te_a = accuracy_score(yte, clf.predict(Xte))
            rows.append({"model": "RF", "max_depth": str(md), "min_leaf": ml,
                         "train_acc": tr_a, "test_acc": te_a, "gap": tr_a - te_a})

    # ExtraTrees with sensible defaults (often more robust to overfit)
    for md in [5, 12, None]:
        clf = ExtraTreesClassifier(n_estimators=400, max_depth=md, min_samples_leaf=2,
                                   random_state=RNG_SEED, n_jobs=-1)
        clf.fit(Xtr, ytr)
        tr_a = accuracy_score(ytr, clf.predict(Xtr))
        te_a = accuracy_score(yte, clf.predict(Xte))
        rows.append({"model": "ExtraTrees", "max_depth": str(md), "min_leaf": 2,
                     "train_acc": tr_a, "test_acc": te_a, "gap": tr_a - te_a})

    # Gradient Boosting (slower, often best on tabular small data)
    for md in [2, 3, 5]:
        clf = GradientBoostingClassifier(n_estimators=300, max_depth=md, learning_rate=0.05,
                                         random_state=RNG_SEED)
        clf.fit(Xtr, ytr)
        tr_a = accuracy_score(ytr, clf.predict(Xtr))
        te_a = accuracy_score(yte, clf.predict(Xte))
        rows.append({"model": "GB", "max_depth": str(md), "min_leaf": None,
                     "train_acc": tr_a, "test_acc": te_a, "gap": tr_a - te_a})

    res = pl.DataFrame(rows).sort("test_acc", descending=True)
    print("\nFull sweep, sorted by test accuracy:")
    with pl.Config(tbl_rows=50):
        print(res)

    res.write_csv(interim / "phase10b_rf_sweep.csv")

    # Plot: train vs test scatter (with gap colour) + best confusion
    best = res.row(0, named=True)
    print(f"\nBEST: {best}")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)

    ax = axes[0]
    colors = {"RF": "C0", "ExtraTrees": "C1", "GB": "C2"}
    for mdl, sub in res.group_by("model"):
        ax.scatter(sub["train_acc"], sub["test_acc"], s=60, alpha=0.75,
                   c=colors[mdl[0]], label=mdl[0])
    ax.plot([0.25, 1.0], [0.25, 1.0], "k--", lw=0.5, alpha=0.4, label="train = test")
    ax.axhline(0.25, color="r", ls=":", lw=0.7, alpha=0.6, label="chance (0.25)")
    ax.set_xlabel("train accuracy"); ax.set_ylabel("test accuracy")
    ax.set_title("Phase 10b — Sweep: train vs test")
    ax.legend(); ax.grid(alpha=0.3)
    ax.set_xlim(0.25, 1.02); ax.set_ylim(0.20, 0.55)

    # Best model confusion
    if best["model"] == "RF":
        clf = RandomForestClassifier(n_estimators=400,
                                     max_depth=None if best["max_depth"] == "None" else int(best["max_depth"]),
                                     min_samples_leaf=int(best["min_leaf"]),
                                     random_state=RNG_SEED, n_jobs=-1)
    elif best["model"] == "ExtraTrees":
        clf = ExtraTreesClassifier(n_estimators=400,
                                   max_depth=None if best["max_depth"] == "None" else int(best["max_depth"]),
                                   min_samples_leaf=2,
                                   random_state=RNG_SEED, n_jobs=-1)
    else:
        clf = GradientBoostingClassifier(n_estimators=300, max_depth=int(best["max_depth"]),
                                         learning_rate=0.05, random_state=RNG_SEED)
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    cm = confusion_matrix(yte, pred, labels=list(CLASSES))
    cm_n = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    ax = axes[1]
    im = ax.imshow(cm_n, cmap="Blues", vmin=0, vmax=1)
    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    ax.set_xticks(range(len(CLASSES)), names, rotation=20)
    ax.set_yticks(range(len(CLASSES)), names)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Best: {best['model']}, max_depth={best['max_depth']}, min_leaf={best['min_leaf']}\n"
                 f"train {best['train_acc']:.3f}  test {best['test_acc']:.3f}")
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            ax.text(j, i, f"{cm_n[i,j]:.2f}\n({cm[i,j]})", ha="center", va="center",
                    color="white" if cm_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig_path = figures / "phase10b_rf_sweep.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
