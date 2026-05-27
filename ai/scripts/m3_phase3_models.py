"""Mouse3 phase 3 — active-vs-sleep models with interval-aware CV.

Task: binary window classification, sleep (positive) vs active.
Methodology mirrors the dataset-1 report:
  - Interval-aware 5-fold CV: every window from one block lives in one fold
    (StratifiedGroupKFold on source_interval_id, stratified by class).
  - Per-fold class balancing: down-sample the majority (active) in TRAIN only.
  - Report balanced accuracy + AUROC (imbalance-robust) with 95% CI.

Models, simplest first:
  A) Movement-index threshold     — ONE feature, threshold by Youden's J.
  B) Logistic regression          — engineered features (linear).
  C) ExtraTrees                   — engineered features (non-linear ceiling).
  D) 1-D CNN on the raw window     — does a deep model beat the threshold?

Output: data/processed/m3_leaderboard.csv
        figures/m3_phase3_models.png
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import balanced_accuracy_score, roc_auc_score, confusion_matrix, roc_curve
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mousepipe import mouse3 as m3
from mousepipe.features import extract_features_batch, feature_names

PROCESSED = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
FS = m3.TARGET_HZ_M3
N_SPLITS = 5
SEED = 42
RUN_CNN = True


def load_windows():
    df = pl.read_parquet(PROCESSED / "m3_windows.parquet")
    X = np.array(df["signal"].to_list(), dtype=np.float32)          # (B, N)
    y = (df["label"].to_numpy() == m3.CLASS_SLEEP).astype(int)      # 1 = sleep
    groups = df["source_interval_id"].to_numpy()
    return X, y, groups


def balance_idx(y, idx, rng):
    """Down-sample the majority class within `idx` to the minority count."""
    idx = np.asarray(idx)
    pos = idx[y[idx] == 1]
    neg = idx[y[idx] == 0]
    k = min(len(pos), len(neg))
    return np.concatenate([rng.choice(pos, k, replace=False),
                           rng.choice(neg, k, replace=False)])


def ci95(vals):
    vals = np.asarray(vals, float)
    se = vals.std(ddof=1) / np.sqrt(len(vals))
    return 1.96 * se


# ----------------------------------------------------------------------------
# Optional CNN
# ----------------------------------------------------------------------------
def run_cnn_fold(Xtr, ytr, Xte, seed):
    import torch, torch.nn as nn
    torch.manual_seed(seed)
    dev = "cpu"

    def norm(a):
        mu, sd = a.mean(1, keepdims=True), a.std(1, keepdims=True) + 1e-6
        return (a - mu) / sd
    Xtr_t = torch.tensor(norm(Xtr)[:, None, :], dtype=torch.float32)
    Xte_t = torch.tensor(norm(Xte)[:, None, :], dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.long)

    model = nn.Sequential(
        nn.Conv1d(1, 16, 7, padding=3), nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(2),
        nn.Conv1d(16, 32, 5, padding=2), nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(2),
        nn.Conv1d(32, 64, 3, padding=1), nn.BatchNorm1d(64), nn.ReLU(),
        nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(64, 2),
    ).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    lossf = nn.CrossEntropyLoss()
    model.train()
    bs = 128
    for _ in range(15):
        perm = torch.randperm(len(Xtr_t))
        for i in range(0, len(perm), bs):
            b = perm[i:i + bs]
            opt.zero_grad()
            loss = lossf(model(Xtr_t[b]), ytr_t[b])
            loss.backward(); opt.step()
    model.eval()
    with torch.no_grad():
        prob = torch.softmax(model(Xte_t), 1)[:, 1].numpy()
    return prob


# ----------------------------------------------------------------------------
def main() -> None:
    X, y, groups = load_windows()
    print(f"windows: {len(y)}  (sleep {y.sum()}, active {(y==0).sum()})  "
          f"natural sleep prevalence {y.mean():.3f}")

    print("extracting engineered features (fs=25) + movement index ...")
    F = extract_features_batch(X, fs=FS)
    F = np.nan_to_num(F, nan=0.0, posinf=0.0, neginf=0.0)
    mi = m3.movement_index_batch(X)
    Feat = np.column_stack([F, mi])           # engineered + MI
    feat_names = feature_names() + ["movement_index"]

    sgkf = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    results = {k: {"bacc": [], "auroc": []} for k in ["A_threshold", "B_logreg", "C_extratrees"]}
    if RUN_CNN:
        results["D_cnn"] = {"bacc": [], "auroc": []}
    # aggregate test predictions for the threshold model (for confusion + ROC)
    agg_y, agg_score_A = [], []
    thresholds_A = []

    for fold, (tr, te) in enumerate(sgkf.split(X, y, groups)):
        rng = np.random.default_rng(SEED + fold)
        tr_b = balance_idx(y, tr, rng)

        # --- A: movement-index threshold (Youden's J on balanced train) ------
        mtr, ytr = mi[tr_b], y[tr_b]
        fpr, tpr, thr = roc_curve(ytr, -mtr)            # score = -MI (low MI => sleep)
        j = np.argmax(tpr - fpr)
        cut_score = thr[j]
        cut_mi = -cut_score                              # predict sleep if MI < cut_mi
        predA = (mi[te] < cut_mi).astype(int)
        results["A_threshold"]["bacc"].append(balanced_accuracy_score(y[te], predA))
        results["A_threshold"]["auroc"].append(roc_auc_score(y[te], -mi[te]))
        thresholds_A.append(cut_mi)
        agg_y.append(y[te]); agg_score_A.append(-mi[te])

        # --- B: logistic regression on standardized engineered features ------
        sc = StandardScaler().fit(Feat[tr_b])
        lr = LogisticRegression(max_iter=2000, C=1.0)
        lr.fit(sc.transform(Feat[tr_b]), y[tr_b])
        pB = lr.predict_proba(sc.transform(Feat[te]))[:, 1]
        results["B_logreg"]["bacc"].append(balanced_accuracy_score(y[te], (pB > 0.5).astype(int)))
        results["B_logreg"]["auroc"].append(roc_auc_score(y[te], pB))

        # --- C: ExtraTrees ---------------------------------------------------
        et = ExtraTreesClassifier(n_estimators=300, max_depth=12, min_samples_leaf=2,
                                  random_state=SEED, n_jobs=-1)
        et.fit(Feat[tr_b], y[tr_b])
        pC = et.predict_proba(Feat[te])[:, 1]
        results["C_extratrees"]["bacc"].append(balanced_accuracy_score(y[te], (pC > 0.5).astype(int)))
        results["C_extratrees"]["auroc"].append(roc_auc_score(y[te], pC))

        # --- D: CNN ----------------------------------------------------------
        if RUN_CNN:
            pD = run_cnn_fold(X[tr_b], y[tr_b], X[te], SEED + fold)
            results["D_cnn"]["bacc"].append(balanced_accuracy_score(y[te], (pD > 0.5).astype(int)))
            results["D_cnn"]["auroc"].append(roc_auc_score(y[te], pD))

        print(f"  fold {fold}: |tr_bal|={len(tr_b)} |te|={len(te)}  "
              f"A bacc {results['A_threshold']['bacc'][-1]:.3f} / auroc {results['A_threshold']['auroc'][-1]:.3f}")

    # --- leaderboard ---------------------------------------------------------
    print("\n=== Leaderboard (5-fold interval-aware CV) ===")
    rows = []
    for name, r in results.items():
        b = np.array(r["bacc"]); a = np.array(r["auroc"])
        rows.append({"model": name,
                     "bacc_mean": round(b.mean(), 4), "bacc_ci95": round(ci95(b), 4),
                     "auroc_mean": round(a.mean(), 4), "auroc_ci95": round(ci95(a), 4)})
        print(f"  {name:14s}  bacc {b.mean():.3f} ± {ci95(b):.3f}   "
              f"auroc {a.mean():.3f} ± {ci95(a):.3f}")
    lb = pl.DataFrame(rows)
    lb.write_parquet(PROCESSED / "m3_leaderboard.parquet")
    lb.write_csv(PROCESSED / "m3_leaderboard.csv")

    # threshold detector: aggregate operating point
    agg_y = np.concatenate(agg_y); agg_score_A = np.concatenate(agg_score_A)
    cut = -np.mean(thresholds_A)
    predA = (agg_score_A > cut).astype(int)  # score=-MI; sleep if score>cut i.e. MI<mean_thr
    cm = confusion_matrix(agg_y, predA)
    mean_thr = float(np.mean(thresholds_A))
    print(f"\n[A] mean Youden threshold: MI < {mean_thr:.3f} g/sample => sleep")
    print(f"[A] aggregate confusion (rows true active/sleep):\n{cm}")

    # --- figure --------------------------------------------------------------
    fig, ax = plt.subplots(1, 3, figsize=(16, 5))
    names = list(results.keys())
    bmeans = [np.mean(results[n]["bacc"]) for n in names]
    bcis = [ci95(np.array(results[n]["bacc"])) for n in names]
    ameans = [np.mean(results[n]["auroc"]) for n in names]
    acis = [ci95(np.array(results[n]["auroc"])) for n in names]
    xp = np.arange(len(names))
    ax[0].bar(xp - 0.2, bmeans, 0.4, yerr=bcis, capsize=3, label="balanced acc")
    ax[0].bar(xp + 0.2, ameans, 0.4, yerr=acis, capsize=3, label="AUROC")
    ax[0].axhline(0.5, color="k", ls="--", lw=0.8, label="chance")
    ax[0].set_xticks(xp); ax[0].set_xticklabels(names, rotation=20, ha="right")
    ax[0].set(title="Active-vs-sleep: 5-fold CV", ylim=(0.4, 1.02)); ax[0].legend()

    fpr, tpr, _ = roc_curve(agg_y, agg_score_A)
    ax[1].plot(fpr, tpr, label=f"AUROC {roc_auc_score(agg_y, agg_score_A):.3f}")
    ax[1].plot([0, 1], [0, 1], "k--", lw=0.7)
    ax[1].set(title="Threshold detector (A) — aggregate ROC", xlabel="FPR", ylabel="TPR")
    ax[1].legend()

    ax[2].hist(mi[y == 0], bins=60, alpha=0.6, label="active", color="tab:blue", log=True)
    ax[2].hist(mi[y == 1], bins=60, alpha=0.6, label="sleep", color="tab:purple", log=True)
    ax[2].axvline(mean_thr, color="r", ls="--", label=f"cut {mean_thr:.2f}")
    ax[2].set(title="Movement index by class", xlabel="median |Δm| (g/sample)", ylabel="count")
    ax[2].legend()
    fig.tight_layout(); fig.savefig(FIGS / "m3_phase3_models.png", dpi=110)
    print(f"\nwrote {PROCESSED/'m3_leaderboard.csv'}, {FIGS/'m3_phase3_models.png'}")


if __name__ == "__main__":
    main()
