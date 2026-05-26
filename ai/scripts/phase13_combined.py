"""Phase 13 — 1-s windows + 3-class CNN + binary (rest-vs-all-gestures) CNN.

Generates a fresh 1-s window set, then runs 5-fold × 3-seed CV for both:
  (a) 3-class on 1-s windows: grooming / nesting / play_isopad (compare to Phase 12, 2-s)
  (b) binary on 1-s windows:  rest vs ANY gesture (1/2/3/4)

Outputs:
  data/processed/windows_train_1s.parquet
  data/interim/phase13_window_stats_1s.csv
  data/interim/phase13_cv_3class_1s.csv
  data/interim/phase13_cv_binary_1s.csv
  figures/phase13_summary.png
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import polars as pl
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

from mousepipe.labels import CLASS_TO_GESTURE
from mousepipe.windows import build_windows

# --- 1-s window config ---
WINDOW_LEN_S = 1.0
STRIDE_S     = 0.25
MARGIN_S     = 0.5
WIN_N        = int(WINDOW_LEN_S * 80)  # 80 samples

# --- CV / training ---
K_FOLDS  = 5
SEEDS    = [42, 123, 314]
DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"
EPOCHS    = 60
BATCH     = 32
LR        = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE  = 20
AUG_SHIFT_SAMPLES = 1   # smaller because window is shorter
AUG_NOISE_STD     = 0.15
VAL_FRAC          = 0.15
DATA_SPLIT_SEED   = 42


def make_folds(windows, classes, k, rng):
    folds = [set() for _ in range(k)]
    for c in classes:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        for i, iv in enumerate(ids):
            folds[i % k].add(iv)
    return folds


def balance(windows, classes, rng):
    counts = {c: int((windows["label"] == c).sum()) for c in classes}
    n_min = min(counts.values()) if counts.values() else 0
    if n_min == 0:
        return windows.clear()
    pieces = []
    for c in classes:
        sub = windows.filter(pl.col("label") == c)
        idx = np.arange(sub.height); rng.shuffle(idx)
        pieces.append(sub[idx[:n_min].tolist()])
    return pl.concat(pieces).sample(fraction=1.0, shuffle=True, seed=int(rng.integers(0, 1 << 30)))


def to_arrays(windows, classes):
    X = np.array(windows["signal"].to_list(), dtype=np.float32)
    y_raw = windows["label"].to_numpy().astype(int)
    label_idx = {c: i for i, c in enumerate(classes)}
    y = np.array([label_idx[v] for v in y_raw], dtype=np.int64)
    return X, y


def augment(X):
    B, N = X.shape
    shifts = torch.randint(-AUG_SHIFT_SAMPLES, AUG_SHIFT_SAMPLES + 1, (B,), device=X.device)
    out = torch.empty_like(X)
    for i in range(B):
        s = int(shifts[i].item())
        if s == 0:   out[i] = X[i]
        elif s > 0:  out[i, :-s] = X[i, s:];   out[i, -s:] = X[i, -1]
        else:        k = -s; out[i, k:] = X[i, :-k]; out[i, :k] = X[i, 0]
    if AUG_NOISE_STD > 0:
        out = out + torch.randn_like(out) * AUG_NOISE_STD
    return out


class CNN1D(nn.Module):
    """Same as Phase 11/12; downstream pooling adapts to the smaller input length."""
    def __init__(self, n_classes, p_drop=0.3):
        super().__init__()
        self.feat = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=11, padding=5),
            nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(16, 32, kernel_size=7, padding=3),
            nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64), nn.ReLU(), nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(p_drop), nn.Linear(64, n_classes))

    def forward(self, x):
        if x.ndim == 2:
            x = x.unsqueeze(1)
        return self.head(self.feat(x))


def train_one_seed(seed, n_classes, Xtr, ytr, Xvl, yvl, Xte):
    torch.manual_seed(seed); np.random.seed(seed)
    model = CNN1D(n_classes).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    loss_fn = nn.CrossEntropyLoss()
    T = lambda a, d=torch.float32: torch.from_numpy(a).to(DEVICE).to(d)
    Xtr_t = T(Xtr); ytr_t = T(ytr, torch.long)
    Xvl_t = T(Xvl); yvl_t = T(yvl, torch.long)
    Xte_t = T(Xte)
    best_val = -1.0; best_state = None; bad = 0
    n = Xtr_t.shape[0]
    for epoch in range(EPOCHS):
        model.train()
        perm = torch.randperm(n, device=DEVICE)
        for i in range(0, n, BATCH):
            j = perm[i:i+BATCH]
            xb = augment(Xtr_t[j])
            opt.zero_grad()
            loss = loss_fn(model(xb), ytr_t[j])
            loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            vl_acc = (model(Xvl_t).argmax(1) == yvl_t).float().mean().item()
        if vl_acc > best_val:
            best_val = vl_acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
            if bad >= PATIENCE:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        te_logits = model(Xte_t).cpu().numpy()
    return te_logits


def run_cv(windows_all: pl.DataFrame, classes: tuple[int, ...], label_name: str):
    """5-fold CV with 3-seed CNN ensemble per fold."""
    n_classes = len(classes)
    rng = np.random.default_rng(DATA_SPLIT_SEED)
    print(f"\n========== {label_name}: classes={classes}  chance={1/n_classes:.3f} ==========")
    folds = make_folds(windows_all, classes, K_FOLDS, rng)
    rows = []; cms = []; y_true_all=[]; y_pred_all=[]
    for k in range(K_FOLDS):
        test_iv = folds[k]
        trainval_iv = set().union(*[folds[j] for j in range(K_FOLDS) if j != k])
        te_pool = windows_all.filter(pl.col("source_interval_id").is_in(list(test_iv)))
        tv_pool = windows_all.filter(pl.col("source_interval_id").is_in(list(trainval_iv)))
        val_iv = set(); train_iv = set()
        for c in classes:
            ids = (tv_pool.filter(pl.col("label") == c)
                          .select("source_interval_id").unique().to_series().to_list())
            rng.shuffle(ids)
            n_val = max(1, int(round(len(ids) * VAL_FRAC)))
            val_iv  |= set(ids[:n_val])
            train_iv |= set(ids[n_val:])
        tr_pool = tv_pool.filter(pl.col("source_interval_id").is_in(list(train_iv)))
        vl_pool = tv_pool.filter(pl.col("source_interval_id").is_in(list(val_iv)))
        bal_rng = np.random.default_rng(DATA_SPLIT_SEED + k)
        tr = balance(tr_pool, classes, bal_rng)
        vl = balance(vl_pool, classes, bal_rng)
        te = balance(te_pool, classes, bal_rng)
        Xtr, ytr = to_arrays(tr, classes); Xvl, yvl = to_arrays(vl, classes); Xte, yte = to_arrays(te, classes)

        seed_logits = []; per_seed_acc = []
        for s in SEEDS:
            tl = train_one_seed(s, n_classes, Xtr, ytr, Xvl, yvl, Xte)
            seed_logits.append(tl)
            per_seed_acc.append(accuracy_score(yte, tl.argmax(1)))
        ens_logits = np.mean(seed_logits, axis=0)
        ens_pred = ens_logits.argmax(1)
        fold_acc = accuracy_score(yte, ens_pred)
        cm = confusion_matrix(yte, ens_pred, labels=list(range(n_classes)))
        cms.append(cm)
        y_true_all.append(yte); y_pred_all.append(ens_pred)
        rows.append({
            "fold": k, "n_train": tr.height, "n_val": vl.height, "n_test": te.height,
            "per_seed_acc_mean": float(np.mean(per_seed_acc)),
            "per_seed_acc_std":  float(np.std(per_seed_acc)),
            "ensemble_acc":      float(fold_acc),
        })
        print(f"  fold {k}: train {tr.height} test {te.height}   per-seed {np.mean(per_seed_acc):.3f}±{np.std(per_seed_acc):.3f}   ensemble {fold_acc:.3f}")

    res = pl.DataFrame(rows)
    accs = res["ensemble_acc"].to_numpy()
    se = accs.std(ddof=1) / np.sqrt(K_FOLDS)
    ci = (accs.mean() - 1.96*se, accs.mean() + 1.96*se)
    print(f"\n  {label_name}: mean {accs.mean():.3f} ± {accs.std():.3f}   95% CI [{ci[0]:.3f}, {ci[1]:.3f}]")
    y_true_all = np.concatenate(y_true_all); y_pred_all = np.concatenate(y_pred_all)
    cm_total = confusion_matrix(y_true_all, y_pred_all, labels=list(range(n_classes)))
    print(classification_report(
        y_true_all, y_pred_all,
        target_names=[CLASS_TO_GESTURE.get(c, str(c)) for c in classes],
        digits=3, zero_division=0))
    return res, cm_total, accs, ci


def main():
    interim   = ROOT / "data" / "interim"
    processed = ROOT / "data" / "processed"
    figures   = ROOT / "figures"

    # --- Build 1-s windows ---
    print(f"Building windows: len={WINDOW_LEN_S}s ({WIN_N} samples) stride={STRIDE_S}s margin={MARGIN_S}s")
    df_grid = pl.read_parquet(interim / "phase7_labeled.parquet")
    windows_1s, stats = build_windows(df_grid,
                                      window_len_s=WINDOW_LEN_S,
                                      stride_s=STRIDE_S,
                                      margin_s=MARGIN_S)
    print(f"built {windows_1s.height:,} windows")
    print(f"  per-class: {[(c, stats[c]['n_windows']) for c in stats]}")
    windows_1s.write_parquet(processed / "windows_train_1s.parquet")
    pl.DataFrame([{"class": c, **s} for c, s in stats.items()]).sort("class").write_csv(
        interim / "phase13_window_stats_1s.csv")

    # --- 3-class (no rest, no eating) ---
    THREE = (1, 3, 4)
    win_three = windows_1s.filter(pl.col("label").is_in(list(THREE)))
    print(f"\n3-class subset: {win_three.height} windows")
    res3, cm3, accs3, ci3 = run_cv(win_three, THREE, "3-class on 1s windows")
    res3.write_csv(interim / "phase13_cv_3class_1s.csv")

    # --- Binary: rest (0) vs any gesture (collapse 1/2/3/4 into a single positive class) ---
    # We re-label all non-zero classes to "1" and class 0 stays 0.
    win_bin = (
        windows_1s
        .filter(pl.col("label").is_in([0, 1, 2, 3, 4]))
        .with_columns(pl.when(pl.col("label") == 0).then(0).otherwise(1).cast(pl.Int8).alias("label"))
    )
    print(f"\nbinary pool: {win_bin.height} windows  "
          f"(rest={int((win_bin['label']==0).sum())}  gestures={int((win_bin['label']==1).sum())})")
    BIN = (0, 1)
    res_b, cm_b, accs_b, ci_b = run_cv(win_bin, BIN, "rest vs any-gesture on 1s windows")
    res_b.write_csv(interim / "phase13_cv_binary_1s.csv")

    # --- Summary figure ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 11), constrained_layout=True)

    # Top-left: 3-class accuracy comparison (2s baseline vs 1s)
    ax = axes[0, 0]
    baseline_2s = 0.604  # from Phase 12
    baseline_2s_ci = (0.567, 0.642)
    labels = ["2-s windows\n(Phase 12)", "1-s windows\n(Phase 13)"]
    means = [baseline_2s, accs3.mean()]
    cis_lo = [baseline_2s_ci[0], ci3[0]]
    cis_hi = [baseline_2s_ci[1], ci3[1]]
    yerr_lo = [m - lo for m, lo in zip(means, cis_lo)]
    yerr_hi = [hi - m for m, hi in zip(means, cis_hi)]
    ax.bar(labels, means, color=["C7", "C0"], yerr=[yerr_lo, yerr_hi], capsize=10, alpha=0.85)
    for i, (m, lo, hi) in enumerate(zip(means, cis_lo, cis_hi)):
        ax.text(i, m + 0.005, f"{m:.3f}\n[{lo:.3f}, {hi:.3f}]", ha="center", va="bottom", fontsize=9)
    ax.axhline(1/3, color="r", ls=":", lw=0.7, alpha=0.6, label="chance (0.33)")
    ax.set_ylabel("test accuracy")
    ax.set_title("3-class — does shorter window help?")
    ax.set_ylim(0.25, 0.85)
    ax.legend(loc="upper right"); ax.grid(alpha=0.3, axis="y")

    # Top-right: Binary accuracy + CI
    ax = axes[0, 1]
    ax.bar(["rest vs any-gesture\n(1s windows)"], [accs_b.mean()],
           color="C2", yerr=[[accs_b.mean()-ci_b[0]], [ci_b[1]-accs_b.mean()]], capsize=10, alpha=0.85)
    ax.text(0, accs_b.mean() + 0.005, f"{accs_b.mean():.3f}\n[{ci_b[0]:.3f}, {ci_b[1]:.3f}]",
            ha="center", va="bottom", fontsize=9)
    ax.axhline(0.5, color="r", ls=":", lw=0.7, alpha=0.6, label="chance (0.50)")
    ax.set_ylabel("test accuracy"); ax.set_title("Binary: rest vs any-gesture")
    ax.set_ylim(0.4, 1.0); ax.legend(loc="upper right"); ax.grid(alpha=0.3, axis="y")

    # Bottom-left: 3-class 1s confusion (aggregated)
    cm3_n = cm3 / cm3.sum(axis=1, keepdims=True).clip(min=1)
    ax = axes[1, 0]
    im = ax.imshow(cm3_n, cmap="Blues", vmin=0, vmax=1)
    names3 = [CLASS_TO_GESTURE[c] for c in THREE]
    ax.set_xticks(range(len(THREE)), names3, rotation=20)
    ax.set_yticks(range(len(THREE)), names3)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"3-class 1-s aggregated confusion (n={cm3.sum()})")
    for i in range(len(THREE)):
        for j in range(len(THREE)):
            ax.text(j, i, f"{cm3_n[i,j]:.2f}\n({cm3[i,j]})", ha="center", va="center",
                    color="white" if cm3_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # Bottom-right: Binary confusion (aggregated)
    cm_b_n = cm_b / cm_b.sum(axis=1, keepdims=True).clip(min=1)
    ax = axes[1, 1]
    im = ax.imshow(cm_b_n, cmap="Blues", vmin=0, vmax=1)
    names_b = ["rest", "any-gesture"]
    ax.set_xticks(range(2), names_b, rotation=20)
    ax.set_yticks(range(2), names_b)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Binary 1-s aggregated confusion (n={cm_b.sum()})")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm_b_n[i,j]:.2f}\n({cm_b[i,j]})", ha="center", va="center",
                    color="white" if cm_b_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig.suptitle(f"Phase 13 — 1-s windows: 3-class CNN vs binary rest/gesture CNN", fontsize=12)
    fig_path = figures / "phase13_summary.png"
    fig.savefig(fig_path, dpi=130); plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
