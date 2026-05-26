"""Phase 17 — TSFresh massive feature engineering + ExtraTrees + 5-fold CV.

Computes the TSFresh 'efficient' feature set (~80 features per window) on the
2-s 3-class window pool, then trains ExtraTrees with the same interval-aware
5-fold CV protocol as Phase 12 / 14. Then runs a fast feature-importance pass.

Hypothesis: if hundreds of automatically-derived features still plateau near
0.63, it definitively closes the question of whether feature engineering can
break this dataset's ceiling.
"""
from __future__ import annotations
import sys, warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from tsfresh import extract_features
from tsfresh.feature_extraction import EfficientFCParameters

warnings.filterwarnings("ignore")

from mousepipe.labels import CLASS_TO_GESTURE

CLASSES   = (1, 3, 4)
N_CLASSES = len(CLASSES)
K_FOLDS   = 5
DATA_SPLIT_SEED = 42
N_TREES   = 500


def make_folds(windows, rng):
    folds = [set() for _ in range(K_FOLDS)]
    for c in CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        for i, iv in enumerate(ids):
            folds[i % K_FOLDS].add(iv)
    return folds


def balance(windows, rng):
    counts = {c: int((windows["label"] == c).sum()) for c in CLASSES}
    n_min = min(counts.values()) if counts.values() else 0
    if n_min == 0:
        return windows.clear()
    pieces = []
    for c in CLASSES:
        sub = windows.filter(pl.col("label") == c)
        idx = np.arange(sub.height); rng.shuffle(idx)
        pieces.append(sub[idx[:n_min].tolist()])
    return pl.concat(pieces).sample(fraction=1.0, shuffle=True, seed=int(rng.integers(0, 1 << 30)))


def cv_acc(feat_df: pl.DataFrame, feat_names: list[str], folds):
    rng = np.random.default_rng(DATA_SPLIT_SEED + 1000)
    per_fold = []; y_true_all = []; y_pred_all = []
    for k in range(K_FOLDS):
        test_iv = folds[k]
        train_iv = set().union(*[folds[j] for j in range(K_FOLDS) if j != k])
        tr = balance(feat_df.filter(pl.col("source_interval_id").is_in(list(train_iv))), rng)
        te = balance(feat_df.filter(pl.col("source_interval_id").is_in(list(test_iv))), rng)
        Xtr = tr.select(feat_names).to_numpy().astype(np.float32)
        Xte = te.select(feat_names).to_numpy().astype(np.float32)
        ytr = tr["label"].to_numpy().astype(int)
        yte = te["label"].to_numpy().astype(int)
        # map to 0..K-1
        lmap = {c: i for i, c in enumerate(CLASSES)}
        ytr = np.array([lmap[v] for v in ytr])
        yte = np.array([lmap[v] for v in yte])
        clf = ExtraTreesClassifier(n_estimators=N_TREES, max_depth=None, min_samples_leaf=2,
                                   random_state=DATA_SPLIT_SEED, n_jobs=-1)
        clf.fit(Xtr, ytr)
        pred = clf.predict(Xte)
        per_fold.append(accuracy_score(yte, pred))
        y_true_all.append(yte); y_pred_all.append(pred)
    accs = np.array(per_fold)
    se = accs.std(ddof=1) / np.sqrt(K_FOLDS)
    ci = (accs.mean() - 1.96*se, accs.mean() + 1.96*se)
    y_true_all = np.concatenate(y_true_all); y_pred_all = np.concatenate(y_pred_all)
    cm = confusion_matrix(y_true_all, y_pred_all, labels=list(range(N_CLASSES)))
    return accs, ci, cm, y_true_all, y_pred_all


def main():
    interim   = ROOT / "data" / "interim"
    processed = ROOT / "data" / "processed"
    figures   = ROOT / "figures"

    print("Loading 2-s windows…")
    windows = pl.read_parquet(processed / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"3-class window pool: {windows.height} windows")

    # ---- Build TSFresh-compatible long-form input ----
    print("Building TSFresh long-form input…")
    rows = []
    for i, row in enumerate(windows.iter_rows(named=True)):
        sig = list(row["signal"])
        for t, v in enumerate(sig):
            rows.append({"id": i, "time": t, "value": float(v)})
    long_df = pd.DataFrame(rows)
    print(f"long-form: {len(long_df):,} rows")

    print("Running tsfresh.extract_features (this is the slow step)…")
    feats = extract_features(
        long_df, column_id="id", column_sort="time", column_value="value",
        default_fc_parameters=EfficientFCParameters(),
        disable_progressbar=True, n_jobs=4,
    )
    # Drop columns with NaN / inf / constant
    feats = feats.replace([np.inf, -np.inf], np.nan)
    feats = feats.dropna(axis=1)
    nunique = feats.nunique()
    feats = feats.loc[:, nunique > 1]
    print(f"feature matrix: {feats.shape}")

    feat_names = list(feats.columns)
    feats_pl = pl.from_pandas(feats.reset_index().rename(columns={"index": "id"}))
    # attach the window metadata (label, source_interval_id)
    meta = windows.with_columns(pl.arange(0, windows.height).alias("id")).select(
        ["id", "label", "source_interval_id"]
    )
    feat_df = meta.join(feats_pl, on="id", how="inner")
    feat_df.write_parquet(processed / "windows_tsfresh.parquet")
    print(f"wrote {processed / 'windows_tsfresh.parquet'} ({feat_df.height} × {feat_df.width})")

    # ---- 5-fold CV with all features ----
    rng = np.random.default_rng(DATA_SPLIT_SEED)
    folds = make_folds(feat_df, rng)
    print(f"\nBaseline (all {len(feat_names)} TSFresh features) 5-fold CV…")
    accs_all, ci_all, cm_all, _, _ = cv_acc(feat_df, feat_names, folds)
    print(f"  mean {accs_all.mean():.3f} ± {accs_all.std():.3f}   95 % CI [{ci_all[0]:.3f}, {ci_all[1]:.3f}]")

    # ---- Fast importance via a single ExtraTrees on the full pool ----
    print("\nRanking features via ExtraTrees impurity importance (single fit on all balanced data)…")
    bal_rng = np.random.default_rng(DATA_SPLIT_SEED + 9999)
    bal = balance(feat_df, bal_rng)
    Xall = bal.select(feat_names).to_numpy().astype(np.float32)
    yall = bal["label"].to_numpy().astype(int)
    lmap = {c: i for i, c in enumerate(CLASSES)}
    yall = np.array([lmap[v] for v in yall])
    clf = ExtraTreesClassifier(n_estimators=N_TREES, max_depth=None, min_samples_leaf=2,
                               random_state=DATA_SPLIT_SEED, n_jobs=-1)
    clf.fit(Xall, yall)
    imp = clf.feature_importances_
    imp_df = (
        pl.DataFrame({"feature": feat_names, "importance": imp.tolist()})
        .sort("importance", descending=True)
    )
    imp_df.write_csv(interim / "phase17_tsfresh_importance.csv")
    print("Top 20 features by impurity importance:")
    with pl.Config(tbl_rows=20):
        print(imp_df.head(20))

    # ---- Take top-K features and re-evaluate ----
    for K in [10, 25, 50]:
        top = imp_df["feature"].to_list()[:K]
        accs, ci, cm, _, _ = cv_acc(feat_df, top, folds)
        print(f"top-{K:>3} features → CV mean {accs.mean():.3f} ± {accs.std():.3f}   95 % CI [{ci[0]:.3f}, {ci[1]:.3f}]")

    pl.DataFrame([
        {"model": "all-features", "mean": float(accs_all.mean()), "std": float(accs_all.std()),
         "ci_lo": float(ci_all[0]), "ci_hi": float(ci_all[1]), "n_features": len(feat_names)},
    ]).write_csv(interim / "phase17_cv_summary.csv")

    # ---- Figure ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    ax = axes[0]
    top20 = imp_df.head(20).to_dicts()[::-1]
    ax.barh([t["feature"][:48] for t in top20], [t["importance"] for t in top20], color="C0")
    ax.set_xlabel("ExtraTrees impurity importance")
    ax.set_title(f"Phase 17 — Top-20 TSFresh features (of {len(feat_names)} total)\n"
                 f"all-features CV mean {accs_all.mean():.3f} CI [{ci_all[0]:.3f}, {ci_all[1]:.3f}]")
    ax.grid(alpha=0.3, axis="x")

    cm_n = cm_all / cm_all.sum(axis=1, keepdims=True).clip(min=1)
    ax = axes[1]
    im = ax.imshow(cm_n, cmap="Blues", vmin=0, vmax=1)
    names_c = [CLASS_TO_GESTURE[c] for c in CLASSES]
    ax.set_xticks(range(N_CLASSES), names_c, rotation=20)
    ax.set_yticks(range(N_CLASSES), names_c)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Aggregated confusion (n={cm_all.sum()})")
    for i in range(N_CLASSES):
        for j in range(N_CLASSES):
            ax.text(j, i, f"{cm_n[i,j]:.2f}\n({cm_all[i,j]})", ha="center", va="center",
                    color="white" if cm_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.savefig(figures / "phase17_tsfresh.png", dpi=130)
    plt.close(fig)
    print(f"wrote {figures / 'phase17_tsfresh.png'}")


if __name__ == "__main__":
    main()
