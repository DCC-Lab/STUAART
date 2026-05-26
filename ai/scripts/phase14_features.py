"""Phase 14 — Hand-engineered features + Random Forest + drop-one feature selection.

Steps:
  1) Compute ~25 engineered features per 2-s window for the 3 gesture classes.
  2) Run 5-fold CV (interval-aware, balanced) with ExtraTrees on ALL features → baseline.
  3) Drop-one: for each feature, re-run the same 5-fold CV with that feature removed.
     Importance = baseline_acc - drop_one_acc.
  4) Train a "selected" model on only the positive-importance features and re-evaluate.

Outputs:
  data/processed/windows_features.parquet
  data/interim/phase14_drop_one_importance.csv
  data/interim/phase14_selected_features.csv
  data/interim/phase14_cv_summary.csv
  figures/phase14_importance.png
  figures/phase14_confusions.png
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, confusion_matrix

from mousepipe.labels import CLASS_TO_GESTURE
from mousepipe.features import extract_features, feature_names

CLASSES   = (1, 3, 4)
N_CLASSES = len(CLASSES)
K_FOLDS   = 5
DATA_SPLIT_SEED = 42
N_TREES   = 500


def make_folds(windows, k, rng):
    folds = [set() for _ in range(k)]
    for c in CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        for i, iv in enumerate(ids):
            folds[i % k].add(iv)
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


def to_arrays(windows, feat_names):
    Xf = np.stack([np.array([row[n] for n in feat_names], dtype=np.float32)
                   for row in windows.select(feat_names).to_dicts()])
    y_raw = windows["label"].to_numpy().astype(int)
    label_idx = {c: i for i, c in enumerate(CLASSES)}
    y = np.array([label_idx[v] for v in y_raw], dtype=np.int64)
    return Xf, y


def cv_acc(windows: pl.DataFrame, feat_names: list[str], folds):
    """5-fold CV ensemble accuracy with ExtraTrees on the given features."""
    rng = np.random.default_rng(DATA_SPLIT_SEED + 1000)
    per_fold = []
    y_true_all = []
    y_pred_all = []
    for k in range(K_FOLDS):
        test_iv = folds[k]
        train_iv = set().union(*[folds[j] for j in range(K_FOLDS) if j != k])
        tr = balance(windows.filter(pl.col("source_interval_id").is_in(list(train_iv))), rng)
        te = balance(windows.filter(pl.col("source_interval_id").is_in(list(test_iv))), rng)
        Xtr, ytr = to_arrays(tr, feat_names)
        Xte, yte = to_arrays(te, feat_names)
        clf = ExtraTreesClassifier(
            n_estimators=N_TREES, max_depth=None, min_samples_leaf=2,
            random_state=DATA_SPLIT_SEED, n_jobs=-1,
        )
        clf.fit(Xtr, ytr)
        pred = clf.predict(Xte)
        acc = accuracy_score(yte, pred)
        per_fold.append(acc)
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

    # --- 1) Compute features ---
    print("Loading 2-s windows…")
    windows = pl.read_parquet(processed / "windows_train.parquet")
    windows_3c = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"3-class window pool: {windows_3c.height} windows")

    feat_names = feature_names()
    print(f"Feature names ({len(feat_names)}): {feat_names}")

    print("Extracting features…")
    feat_rows = []
    for row in windows_3c.iter_rows(named=True):
        sig = np.asarray(row["signal"], dtype=np.float32)
        f = extract_features(sig)
        feat_rows.append({
            "t_start_ms": row["t_start_ms"],
            "t_end_ms":   row["t_end_ms"],
            "label":      row["label"],
            "source_interval_id": row["source_interval_id"],
            **f,
        })
    feat_df = pl.DataFrame(feat_rows)
    feat_df.write_parquet(processed / "windows_features.parquet")
    print(f"wrote {processed / 'windows_features.parquet'}  ({feat_df.height:,} rows × {feat_df.width} cols)")

    # --- 2) Baseline CV on all features ---
    rng = np.random.default_rng(DATA_SPLIT_SEED)
    folds = make_folds(feat_df, K_FOLDS, rng)

    print("\nBaseline (all features) 5-fold CV…")
    base_accs, base_ci, base_cm, _, _ = cv_acc(feat_df, feat_names, folds)
    print(f"  mean {base_accs.mean():.3f} ± {base_accs.std():.3f}   95% CI [{base_ci[0]:.3f}, {base_ci[1]:.3f}]")

    # --- 3) Drop-one importance ---
    print("\nDrop-one importance scan…")
    importance_rows = []
    for f in feat_names:
        keep = [n for n in feat_names if n != f]
        accs, ci, _, _, _ = cv_acc(feat_df, keep, folds)
        imp = base_accs.mean() - accs.mean()
        print(f"  drop {f:>22}: drop-one acc = {accs.mean():.4f}  →  importance = {imp:+.4f}")
        importance_rows.append({
            "feature": f, "drop_one_acc": accs.mean(),
            "importance": imp,
        })
    imp_df = pl.DataFrame(importance_rows).sort("importance", descending=True)
    imp_df.write_csv(interim / "phase14_drop_one_importance.csv")
    print(imp_df)

    # --- 4) Selected: keep features with positive importance ---
    selected = imp_df.filter(pl.col("importance") > 0)["feature"].to_list()
    if not selected:
        selected = imp_df.head(8)["feature"].to_list()  # safety fallback
    print(f"\nSelected {len(selected)} features (positive importance):")
    print("  " + ", ".join(selected))
    pl.DataFrame({"feature": selected}).write_csv(interim / "phase14_selected_features.csv")

    sel_accs, sel_ci, sel_cm, _, _ = cv_acc(feat_df, selected, folds)
    print(f"\nSelected-features CV: mean {sel_accs.mean():.3f} ± {sel_accs.std():.3f}   95% CI [{sel_ci[0]:.3f}, {sel_ci[1]:.3f}]")

    pl.DataFrame([
        {"model": "all-features",        "mean": float(base_accs.mean()), "std": float(base_accs.std()),
         "ci_lo": float(base_ci[0]), "ci_hi": float(base_ci[1]), "n_features": len(feat_names)},
        {"model": "selected-features",   "mean": float(sel_accs.mean()),  "std": float(sel_accs.std()),
         "ci_lo": float(sel_ci[0]),  "ci_hi": float(sel_ci[1]),  "n_features": len(selected)},
    ]).write_csv(interim / "phase14_cv_summary.csv")

    # --- Figures ---
    # Importance bar
    fig, ax = plt.subplots(1, 1, figsize=(11, max(4, 0.3 * len(feat_names))), constrained_layout=True)
    imp_df_sorted = imp_df.sort("importance")
    names = imp_df_sorted["feature"].to_list()
    vals  = imp_df_sorted["importance"].to_list()
    colors = ["C2" if v > 0 else "C3" for v in vals]
    ax.barh(names, vals, color=colors)
    ax.axvline(0, color="k", lw=0.5)
    ax.set_xlabel("importance (baseline_acc − drop_one_acc)")
    ax.set_title(f"Phase 14 — Drop-one feature importance\nbaseline {base_accs.mean():.3f} (CI [{base_ci[0]:.3f}, {base_ci[1]:.3f}])")
    ax.grid(alpha=0.3, axis="x")
    fig.savefig(figures / "phase14_importance.png", dpi=130)
    plt.close(fig)

    # Confusion matrices
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
    names_c = [CLASS_TO_GESTURE[c] for c in CLASSES]
    for ax, cm, title in zip(axes, (base_cm, sel_cm),
                             (f"All features (n={len(feat_names)})  acc={base_accs.mean():.3f}",
                              f"Selected features (n={len(selected)})  acc={sel_accs.mean():.3f}")):
        cm_n = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
        im = ax.imshow(cm_n, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(N_CLASSES), names_c, rotation=20)
        ax.set_yticks(range(N_CLASSES), names_c)
        ax.set_xlabel("predicted"); ax.set_ylabel("true")
        ax.set_title(title)
        for i in range(N_CLASSES):
            for j in range(N_CLASSES):
                ax.text(j, i, f"{cm_n[i,j]:.2f}\n({cm[i,j]})", ha="center", va="center",
                        color="white" if cm_n[i,j] > 0.5 else "black", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.savefig(figures / "phase14_confusions.png", dpi=130)
    plt.close(fig)

    print(f"\nwrote {figures / 'phase14_importance.png'}")
    print(f"wrote {figures / 'phase14_confusions.png'}")
    print(f"\n=== Final comparison vs CNN baseline (0.604) ===")
    print(f"  All-features ExtraTrees:       {base_accs.mean():.3f}  CI [{base_ci[0]:.3f}, {base_ci[1]:.3f}]")
    print(f"  Selected-features ExtraTrees:  {sel_accs.mean():.3f}  CI [{sel_ci[0]:.3f}, {sel_ci[1]:.3f}]")
    print(f"  CNN baseline (Phase 12):       0.604         CI [0.567, 0.642]")


if __name__ == "__main__":
    main()
