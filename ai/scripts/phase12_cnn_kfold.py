"""Phase 12 — 5-fold CV with 3-seed CNN ensemble per fold (interval-aware).

Goal: tight estimate of true test accuracy on this dataset, dampening both the
small-test-set noise (n=24 windows/class per fold isn't great) and the seed noise
(±11 pp from Phase 11d).

Each fold:
  - test  = windows from intervals assigned to fold k (per class, ~5-9 intervals/class)
  - trainval = windows from the other 4 folds' intervals
  - train/val carved from trainval at the interval level (85/15)
  - 3 seeds × CNN trained, logits averaged → predict on the fold's test set

Aggregate: per-fold accuracy + mean/std across folds + class-level confusion summed.
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

K_FOLDS  = 5
SEEDS    = [42, 123, 314]
CLASSES  = (1, 3, 4)
N_CLASSES = len(CLASSES)
WIN_N    = 160
DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"

EPOCHS    = 60
BATCH     = 32
LR        = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE  = 20
AUG_SHIFT_SAMPLES = 2
AUG_NOISE_STD     = 0.15
VAL_FRAC          = 0.15

DATA_SPLIT_SEED = 42


def make_folds(windows: pl.DataFrame, k: int, rng) -> list[set[int]]:
    """Return a list of k sets of interval ids, each set is one fold (per class balanced)."""
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


def to_arrays(windows):
    X = np.array(windows["signal"].to_list(), dtype=np.float32)
    y_raw = windows["label"].to_numpy().astype(int)
    label_idx = {c: i for i, c in enumerate(CLASSES)}
    y = np.array([label_idx[v] for v in y_raw], dtype=np.int64)
    return X, y


def augment(X, shift=AUG_SHIFT_SAMPLES, noise_std=AUG_NOISE_STD):
    B, N = X.shape
    shifts = torch.randint(-shift, shift + 1, (B,), device=X.device)
    out = torch.empty_like(X)
    for i in range(B):
        s = int(shifts[i].item())
        if s == 0:   out[i] = X[i]
        elif s > 0:  out[i, :-s] = X[i, s:];   out[i, -s:] = X[i, -1]
        else:        k = -s; out[i, k:] = X[i, :-k]; out[i, :k] = X[i, 0]
    if noise_std > 0:
        out = out + torch.randn_like(out) * noise_std
    return out


class CNN1D(nn.Module):
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


def train_one_seed(seed, Xtr, ytr, Xvl, yvl, Xte):
    torch.manual_seed(seed); np.random.seed(seed)
    model = CNN1D(N_CLASSES).to(DEVICE)
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


def main():
    interim = ROOT / "data" / "interim"; figures = ROOT / "figures"
    rng = np.random.default_rng(DATA_SPLIT_SEED)

    windows = pl.read_parquet(ROOT / "data" / "processed" / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"3-class windows: {windows.height:,}  chance = {1/N_CLASSES:.3f}  device={DEVICE}")
    print(f"per-class interval counts (with core): "
          f"{[int(windows.filter(pl.col('label')==c).select('source_interval_id').unique().height) for c in CLASSES]}")

    folds = make_folds(windows, K_FOLDS, rng)
    for i, f in enumerate(folds):
        print(f"  fold {i}: {len(f)} intervals "
              f"({[int(windows.filter((pl.col('label')==c) & (pl.col('source_interval_id').is_in(list(f)))).select('source_interval_id').unique().height) for c in CLASSES]})")

    rows = []
    all_y_true, all_y_pred = [], []
    cms = []

    for k in range(K_FOLDS):
        test_iv  = folds[k]
        trainval_iv = set().union(*[folds[j] for j in range(K_FOLDS) if j != k])

        te_pool = windows.filter(pl.col("source_interval_id").is_in(list(test_iv)))
        tv_pool = windows.filter(pl.col("source_interval_id").is_in(list(trainval_iv)))

        # interval-aware val split within trainval (per class)
        val_iv, train_iv = set(), set()
        for c in CLASSES:
            ids = (tv_pool.filter(pl.col("label") == c)
                          .select("source_interval_id").unique().to_series().to_list())
            rng.shuffle(ids)
            n_val = max(1, int(round(len(ids) * VAL_FRAC)))
            val_iv  |= set(ids[:n_val])
            train_iv |= set(ids[n_val:])

        tr_pool = tv_pool.filter(pl.col("source_interval_id").is_in(list(train_iv)))
        vl_pool = tv_pool.filter(pl.col("source_interval_id").is_in(list(val_iv)))

        bal_rng = np.random.default_rng(DATA_SPLIT_SEED + k)
        tr = balance(tr_pool, bal_rng)
        vl = balance(vl_pool, bal_rng)
        te = balance(te_pool, bal_rng)

        Xtr, ytr = to_arrays(tr); Xvl, yvl = to_arrays(vl); Xte, yte = to_arrays(te)
        print(f"\n--- fold {k} ---  train={tr.height}  val={vl.height}  test={te.height}  "
              f"(per-class {tr.height//N_CLASSES}/{vl.height//N_CLASSES}/{te.height//N_CLASSES})")

        seed_logits = []
        per_seed_acc = []
        for s in SEEDS:
            te_logits = train_one_seed(s, Xtr, ytr, Xvl, yvl, Xte)
            seed_logits.append(te_logits)
            acc = accuracy_score(yte, te_logits.argmax(1))
            per_seed_acc.append(acc)
            print(f"  seed {s}: test {acc:.3f}")

        ens_logits = np.mean(seed_logits, axis=0)
        ens_pred = ens_logits.argmax(1)
        fold_acc = accuracy_score(yte, ens_pred)
        cm = confusion_matrix(yte, ens_pred, labels=list(range(N_CLASSES)))
        cms.append(cm)
        all_y_true.append(yte); all_y_pred.append(ens_pred)

        rows.append({
            "fold": k,
            "n_train": tr.height, "n_val": vl.height, "n_test": te.height,
            "per_seed_acc_mean": float(np.mean(per_seed_acc)),
            "per_seed_acc_std":  float(np.std(per_seed_acc)),
            "ensemble_acc":      float(fold_acc),
        })
        print(f"  ensemble: test {fold_acc:.3f}   (per-seed mean {np.mean(per_seed_acc):.3f} ± {np.std(per_seed_acc):.3f})")

    df = pl.DataFrame(rows)
    print()
    print("Per-fold summary:")
    print(df)
    ens_accs = df["ensemble_acc"].to_numpy()
    print(f"\nensemble accuracy across {K_FOLDS} folds: mean {ens_accs.mean():.3f} ± {ens_accs.std():.3f}  "
          f"range {ens_accs.min():.3f}..{ens_accs.max():.3f}")

    # 95% CI on the mean
    se = ens_accs.std(ddof=1) / np.sqrt(K_FOLDS)
    ci_lo, ci_hi = ens_accs.mean() - 1.96 * se, ens_accs.mean() + 1.96 * se
    print(f"95% CI on mean accuracy: [{ci_lo:.3f}, {ci_hi:.3f}]")

    df.write_csv(interim / "phase12_cnn_kfold.csv")

    # Aggregated CM across folds
    y_true_all = np.concatenate(all_y_true); y_pred_all = np.concatenate(all_y_pred)
    cm_total = confusion_matrix(y_true_all, y_pred_all, labels=list(range(N_CLASSES)))
    cm_total_n = cm_total / cm_total.sum(axis=1, keepdims=True).clip(min=1)
    print()
    print("Aggregated classification report (across all fold tests):")
    print(classification_report(y_true_all, y_pred_all,
                                target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3, zero_division=0))

    # ---- Figure ----
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
    ax = axes[0]
    folds_ax = list(range(K_FOLDS))
    ax.errorbar(folds_ax, df["per_seed_acc_mean"], yerr=df["per_seed_acc_std"], fmt="o-",
                color="C0", label="mean ± std of 3 seeds per fold")
    ax.plot(folds_ax, df["ensemble_acc"], "s-", color="C2", label="ensemble (3-seed mean logits)")
    ax.axhline(1/N_CLASSES, color="r", ls=":", lw=0.7, alpha=0.6, label=f"chance ({1/N_CLASSES:.2f})")
    ax.axhline(ens_accs.mean(), color="grey", ls="--", lw=0.7, alpha=0.6,
               label=f"mean across folds ({ens_accs.mean():.3f})")
    ax.fill_between(folds_ax, [ci_lo]*K_FOLDS, [ci_hi]*K_FOLDS, color="grey", alpha=0.12, label="95% CI on mean")
    ax.set_xlabel("fold"); ax.set_ylabel("test accuracy")
    ax.set_title(f"Phase 12 — 5-fold CV (3-seed ens per fold)\nmean acc {ens_accs.mean():.3f} ± {ens_accs.std():.3f}")
    ax.set_ylim(0.25, 0.85); ax.legend(fontsize=8, loc="lower right")
    ax.set_xticks(folds_ax); ax.grid(alpha=0.3)

    ax = axes[1]
    im = ax.imshow(cm_total_n, cmap="Blues", vmin=0, vmax=1)
    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    ax.set_xticks(range(N_CLASSES), names, rotation=20)
    ax.set_yticks(range(N_CLASSES), names)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Aggregated confusion across {K_FOLDS} folds (n={cm_total.sum()})")
    for i in range(N_CLASSES):
        for j in range(N_CLASSES):
            ax.text(j, i, f"{cm_total_n[i,j]:.2f}\n({cm_total[i,j]})", ha="center", va="center",
                    color="white" if cm_total_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig_path = figures / "phase12_cnn_kfold.png"
    fig.savefig(fig_path, dpi=130); plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
