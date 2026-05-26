"""Phase 18b — Binary rest-vs-gesture, TSFresh + ExtraTrees.

Maps label 0 → 0 (rest), labels {1, 3, 4} → 1 (any gesture). Drops label 2.
Same 5-fold interval-aware CV as Phase 17.
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
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, roc_auc_score
from tsfresh import extract_features
from tsfresh.feature_extraction import EfficientFCParameters

warnings.filterwarnings("ignore")

REST = 0
GESTURE_CLASSES = (1, 3, 4)
KEEP_CLASSES = (0, 1, 3, 4)
N_CLASSES = 2
K_FOLDS   = 5
DATA_SPLIT_SEED = 42
N_TREES   = 500


def to_binary(labels: np.ndarray) -> np.ndarray:
    return (labels != REST).astype(np.int64)


def make_folds(windows, rng):
    folds = [set() for _ in range(K_FOLDS)]
    for c in KEEP_CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        for i, iv in enumerate(ids):
            folds[i % K_FOLDS].add(iv)
    return folds


def balance_binary(windows, rng):
    rest = windows.filter(pl.col("label") == REST)
    gest = windows.filter(pl.col("label").is_in(list(GESTURE_CLASSES)))
    n_min = min(rest.height, gest.height)
    if n_min == 0:
        return windows.clear()
    idx_r = np.arange(rest.height); rng.shuffle(idx_r)
    idx_g = np.arange(gest.height); rng.shuffle(idx_g)
    out = pl.concat([rest[idx_r[:n_min].tolist()], gest[idx_g[:n_min].tolist()]])
    return out.sample(fraction=1.0, shuffle=True, seed=int(rng.integers(0, 1 << 30)))


def cv_acc(feat_df: pl.DataFrame, feat_names: list[str], folds):
    rng = np.random.default_rng(DATA_SPLIT_SEED + 1000)
    per_fold = []; y_true_all = []; y_pred_all = []; y_prob_all = []
    for k in range(K_FOLDS):
        test_iv = folds[k]
        train_iv = set().union(*[folds[j] for j in range(K_FOLDS) if j != k])
        tr = balance_binary(feat_df.filter(pl.col("source_interval_id").is_in(list(train_iv))), rng)
        te = balance_binary(feat_df.filter(pl.col("source_interval_id").is_in(list(test_iv))), rng)
        Xtr = tr.select(feat_names).to_numpy().astype(np.float32)
        Xte = te.select(feat_names).to_numpy().astype(np.float32)
        ytr = to_binary(tr["label"].to_numpy().astype(int))
        yte = to_binary(te["label"].to_numpy().astype(int))
        clf = ExtraTreesClassifier(n_estimators=N_TREES, max_depth=None, min_samples_leaf=2,
                                   random_state=DATA_SPLIT_SEED, n_jobs=-1)
        clf.fit(Xtr, ytr)
        pred = clf.predict(Xte)
        prob = clf.predict_proba(Xte)[:, 1]
        per_fold.append(accuracy_score(yte, pred))
        y_true_all.append(yte); y_pred_all.append(pred); y_prob_all.append(prob)
    accs = np.array(per_fold)
    se = accs.std(ddof=1) / np.sqrt(K_FOLDS)
    ci = (accs.mean() - 1.96*se, accs.mean() + 1.96*se)
    y_true_all = np.concatenate(y_true_all); y_pred_all = np.concatenate(y_pred_all)
    y_prob_all = np.concatenate(y_prob_all)
    cm = confusion_matrix(y_true_all, y_pred_all, labels=[0, 1])
    try:
        auroc = roc_auc_score(y_true_all, y_prob_all)
    except ValueError:
        auroc = float("nan")
    return accs, ci, cm, y_true_all, y_pred_all, y_prob_all, auroc


def main():
    interim   = ROOT / "data" / "interim"
    processed = ROOT / "data" / "processed"
    figures   = ROOT / "figures"

    windows = pl.read_parquet(processed / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(KEEP_CLASSES)))
    print(f"Binary pool: {windows.height} windows")
    print(f"  rest      : {(windows['label'] == 0).sum()}")
    print(f"  gestures  : {sum((windows['label'] == c).sum() for c in GESTURE_CLASSES)}")

    cache = processed / "windows_tsfresh_binary.parquet"
    if cache.exists():
        print(f"Loading cached TSFresh features from {cache}")
        feat_df = pl.read_parquet(cache)
        feat_names = [c for c in feat_df.columns
                      if c not in {"id", "label", "source_interval_id"}]
    else:
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
        feats = feats.replace([np.inf, -np.inf], np.nan).dropna(axis=1)
        nunique = feats.nunique()
        feats = feats.loc[:, nunique > 1]
        print(f"feature matrix: {feats.shape}")
        feat_names = list(feats.columns)
        feats_pl = pl.from_pandas(feats.reset_index().rename(columns={"index": "id"}))
        meta = windows.with_columns(pl.arange(0, windows.height).alias("id")).select(
            ["id", "label", "source_interval_id"]
        )
        feat_df = meta.join(feats_pl, on="id", how="inner")
        feat_df.write_parquet(cache)
        print(f"wrote {cache} ({feat_df.height} × {feat_df.width})")

    rng = np.random.default_rng(DATA_SPLIT_SEED)
    folds = make_folds(feat_df, rng)

    print(f"\nBaseline (all {len(feat_names)} TSFresh features) 5-fold CV…")
    accs_all, ci_all, cm_all, ytrue, ypred, yprob, auroc_all = cv_acc(feat_df, feat_names, folds)
    print(f"  mean {accs_all.mean():.3f} ± {accs_all.std():.3f}   "
          f"95 % CI [{ci_all[0]:.3f}, {ci_all[1]:.3f}]   AUROC {auroc_all:.3f}")

    print("\nRanking features via ExtraTrees impurity importance…")
    bal_rng = np.random.default_rng(DATA_SPLIT_SEED + 9999)
    bal = balance_binary(feat_df, bal_rng)
    Xall = bal.select(feat_names).to_numpy().astype(np.float32)
    yall = to_binary(bal["label"].to_numpy().astype(int))
    clf = ExtraTreesClassifier(n_estimators=N_TREES, max_depth=None, min_samples_leaf=2,
                               random_state=DATA_SPLIT_SEED, n_jobs=-1)
    clf.fit(Xall, yall)
    imp = clf.feature_importances_
    imp_df = (
        pl.DataFrame({"feature": feat_names, "importance": imp.tolist()})
        .sort("importance", descending=True)
    )
    imp_df.write_csv(interim / "phase18b_tsfresh_binary_importance.csv")
    print("Top 20 features by impurity importance:")
    with pl.Config(tbl_rows=20):
        print(imp_df.head(20))

    for K in [10, 25, 50]:
        top = imp_df["feature"].to_list()[:K]
        accs, ci, cm, _, _, _, auroc = cv_acc(feat_df, top, folds)
        print(f"top-{K:>3} features → CV mean {accs.mean():.3f} ± {accs.std():.3f}   "
              f"95 % CI [{ci[0]:.3f}, {ci[1]:.3f}]   AUROC {auroc:.3f}")

    pl.DataFrame([
        {"model": "all-features", "mean": float(accs_all.mean()), "std": float(accs_all.std()),
         "ci_lo": float(ci_all[0]), "ci_hi": float(ci_all[1]),
         "auroc": float(auroc_all), "n_features": len(feat_names)},
    ]).write_csv(interim / "phase18b_cv_summary.csv")

    cm_n = cm_all / cm_all.sum(axis=1, keepdims=True).clip(min=1)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    ax = axes[0]
    top20 = imp_df.head(20).to_dicts()[::-1]
    ax.barh([t["feature"][:48] for t in top20], [t["importance"] for t in top20], color="C0")
    ax.set_xlabel("ExtraTrees impurity importance")
    ax.set_title(f"Phase 18b — Top-20 TSFresh features (binary, of {len(feat_names)} total)\n"
                 f"all-features CV mean {accs_all.mean():.3f} CI [{ci_all[0]:.3f}, {ci_all[1]:.3f}]   "
                 f"AUROC {auroc_all:.3f}")
    ax.grid(alpha=0.3, axis="x")

    ax = axes[1]
    im = ax.imshow(cm_n, cmap="Blues", vmin=0, vmax=1)
    names = ["rest", "gesture"]
    ax.set_xticks([0, 1], names); ax.set_yticks([0, 1], names)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Aggregated confusion (n={cm_all.sum()})")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm_n[i,j]:.2f}\n({cm_all[i,j]})", ha="center", va="center",
                    color="white" if cm_n[i,j] > 0.5 else "black", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig_path = figures / "phase18b_tsfresh_binary.png"
    fig.savefig(fig_path, dpi=130); plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
