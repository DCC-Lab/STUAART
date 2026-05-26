"""Phase 10c — Same sweep as 10b but on 3 classes only (drop class 0 = none)."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

from mousepipe.labels import CLASS_TO_GESTURE

RNG_SEED  = 42
TEST_FRAC = 0.20
CLASSES   = (1, 3, 4)  # grooming, nesting, play_isopad — DROP none(0) and eating(2)


def split_by_interval(windows, rng):
    train_ids, test_ids = set(), set()
    for c in CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        n_test = max(1, int(round(len(ids) * TEST_FRAC)))
        test_ids  |= set(ids[:n_test]); train_ids |= set(ids[n_test:])
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
    interim = ROOT / "data" / "interim"; figures = ROOT / "figures"
    rng = np.random.default_rng(RNG_SEED)

    windows = pl.read_parquet(ROOT / "data" / "processed" / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"3-class windows: {windows.height:,}  chance = {1/len(CLASSES):.3f}")

    train_ids, test_ids = split_by_interval(windows, rng)
    tr = balance(windows.filter(pl.col("source_interval_id").is_in(list(train_ids))), rng)
    te = balance(windows.filter(pl.col("source_interval_id").is_in(list(test_ids))), rng)
    Xtr, ytr = to_xy(tr); Xte, yte = to_xy(te)
    print(f"balanced: train {len(ytr)}  test {len(yte)}   per-class train {len(ytr)//len(CLASSES)}  test {len(yte)//len(CLASSES)}")

    rows = []
    configs = []
    for md in [3, 5, 8, 12, 20, None]:
        for ml in [1, 5, 10, 20]:
            configs.append(("RF", md, ml,
                            RandomForestClassifier(n_estimators=400, max_depth=md, min_samples_leaf=ml,
                                                   random_state=RNG_SEED, n_jobs=-1)))
    for md in [5, 12, None]:
        configs.append(("ExtraTrees", md, 2,
                        ExtraTreesClassifier(n_estimators=400, max_depth=md, min_samples_leaf=2,
                                             random_state=RNG_SEED, n_jobs=-1)))
    for md in [2, 3, 5]:
        configs.append(("GB", md, None,
                        GradientBoostingClassifier(n_estimators=300, max_depth=md, learning_rate=0.05,
                                                   random_state=RNG_SEED)))

    best = None
    for name, md, ml, clf in configs:
        clf.fit(Xtr, ytr)
        tr_a = accuracy_score(ytr, clf.predict(Xtr))
        te_a = accuracy_score(yte, clf.predict(Xte))
        rows.append({"model": name, "max_depth": str(md), "min_leaf": ml,
                     "train_acc": tr_a, "test_acc": te_a, "gap": tr_a - te_a})
        if best is None or te_a > best["test_acc"]:
            best = {"name": name, "max_depth": md, "min_leaf": ml,
                    "train_acc": tr_a, "test_acc": te_a, "clf": clf}

    res = pl.DataFrame(rows).sort("test_acc", descending=True)
    print("\nTop 10:")
    with pl.Config(tbl_rows=10):
        print(res.head(10))
    res.drop("model" if False else None) if False else None
    res.write_csv(interim / "phase10c_3class_sweep.csv")

    print(f"\nBEST: {best['name']} max_depth={best['max_depth']} min_leaf={best['min_leaf']}  "
          f"train {best['train_acc']:.3f}  test {best['test_acc']:.3f}")
    pred = best["clf"].predict(Xte)
    print(classification_report(yte, pred, labels=list(CLASSES),
                                target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3))

    # Confusion of best
    cm = confusion_matrix(yte, pred, labels=list(CLASSES))
    cm_n = cm / cm.sum(axis=1, keepdims=True).clip(min=1)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
    ax = axes[0]
    colors = {"RF": "C0", "ExtraTrees": "C1", "GB": "C2"}
    for mdl, sub in res.group_by("model"):
        ax.scatter(sub["train_acc"], sub["test_acc"], s=60, alpha=0.75, c=colors[mdl[0]], label=mdl[0])
    ax.plot([0.33, 1.0], [0.33, 1.0], "k--", lw=0.5, alpha=0.4, label="train = test")
    ax.axhline(1/len(CLASSES), color="r", ls=":", lw=0.7, alpha=0.6, label=f"chance ({1/len(CLASSES):.2f})")
    ax.set_xlabel("train accuracy"); ax.set_ylabel("test accuracy")
    ax.set_title("Phase 10c — 3-class sweep (none/eating dropped)")
    ax.legend(); ax.grid(alpha=0.3)
    ax.set_xlim(0.3, 1.02); ax.set_ylim(0.25, 0.75)

    ax = axes[1]
    im = ax.imshow(cm_n, cmap="Blues", vmin=0, vmax=1)
    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    ax.set_xticks(range(len(CLASSES)), names, rotation=20)
    ax.set_yticks(range(len(CLASSES)), names)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Best: {best['name']} d={best['max_depth']} leaf={best['min_leaf']}\n"
                 f"train {best['train_acc']:.3f}  test {best['test_acc']:.3f}")
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            ax.text(j, i, f"{cm_n[i,j]:.2f}\n({cm[i,j]})", ha="center", va="center",
                    color="white" if cm_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig_path = figures / "phase10c_3class.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
