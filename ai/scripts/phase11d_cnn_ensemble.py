"""Phase 11d — 5-seed CNN ensemble (3-class, raw).

Same architecture as 11b (smaller kernels, the version that worked) + light aug.
Trains 5 independent models with different seeds, averages logits at test time,
also reports per-seed test accuracy so we can see the run-to-run noise.
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

SEEDS     = [42, 123, 7, 2026, 314]
CLASSES   = (1, 3, 4)
TEST_FRAC = 0.20
VAL_FRAC  = 0.15
WIN_N     = 160
N_CLASSES = len(CLASSES)
DEVICE    = "cuda" if torch.cuda.is_available() else "cpu"

EPOCHS    = 100
BATCH     = 32
LR        = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE  = 25
AUG_SHIFT_SAMPLES = 2
AUG_NOISE_STD     = 0.15


def split_3way_by_interval(windows, rng):
    train, val, test = set(), set(), set()
    for c in CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        n = len(ids); n_test = max(1, int(round(n * TEST_FRAC)))
        n_val = max(1, int(round(n * VAL_FRAC)))
        test |= set(ids[:n_test])
        val  |= set(ids[n_test:n_test+n_val])
        train |= set(ids[n_test+n_val:])
    return train, val, test


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


def train_one(seed, Xtr, ytr, Xvl, yvl, Xte):
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
    return best_val, te_logits


def main():
    interim = ROOT / "data" / "interim"; figures = ROOT / "figures"
    # Use a fixed RNG for the data split so all seeds see the same split
    split_rng = np.random.default_rng(42)
    windows = pl.read_parquet(ROOT / "data" / "processed" / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    tr_ids, vl_ids, te_ids = split_3way_by_interval(windows, split_rng)
    bal_rng = np.random.default_rng(42)
    tr = balance(windows.filter(pl.col("source_interval_id").is_in(list(tr_ids))), bal_rng)
    vl = balance(windows.filter(pl.col("source_interval_id").is_in(list(vl_ids))), bal_rng)
    te = balance(windows.filter(pl.col("source_interval_id").is_in(list(te_ids))), bal_rng)
    Xtr, ytr = to_arrays(tr); Xvl, yvl = to_arrays(vl); Xte, yte = to_arrays(te)
    print(f"balanced: train {tr.height}  val {vl.height}  test {te.height}   "
          f"per-class {tr.height//N_CLASSES} / {vl.height//N_CLASSES} / {te.height//N_CLASSES}")
    print(f"seeds: {SEEDS}")

    per_seed = []
    all_logits = []
    for s in SEEDS:
        best_val, te_logits = train_one(s, Xtr, ytr, Xvl, yvl, Xte)
        pred = te_logits.argmax(1)
        acc = accuracy_score(yte, pred)
        per_seed.append({"seed": s, "best_val": best_val, "test_acc": acc})
        print(f"  seed {s}: val {best_val:.3f}  test {acc:.3f}")
        all_logits.append(te_logits)

    ens_logits = np.mean(all_logits, axis=0)
    ens_pred = ens_logits.argmax(1)
    ens_acc = accuracy_score(yte, ens_pred)
    print(f"\nensemble (mean of logits) test acc: {ens_acc:.3f}")
    print(classification_report(yte, ens_pred, target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3, zero_division=0))

    # Summary
    seed_acc = np.array([r["test_acc"] for r in per_seed])
    print(f"per-seed test acc: mean {seed_acc.mean():.3f}  std {seed_acc.std():.3f}  range {seed_acc.min():.3f}..{seed_acc.max():.3f}")

    pl.DataFrame(per_seed + [{"seed": "ensemble", "best_val": float("nan"), "test_acc": ens_acc}]).write_csv(
        interim / "phase11d_cnn_ensemble.csv"
    )

    # Figure: per-seed bars + ensemble confusion
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
    ax = axes[0]
    xs = [str(r["seed"]) for r in per_seed] + ["ensemble"]
    ys = list(seed_acc) + [ens_acc]
    bars = ax.bar(xs, ys, color=["C0"] * len(SEEDS) + ["C2"])
    for b, v in zip(bars, ys):
        ax.text(b.get_x() + b.get_width()/2, v, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    ax.axhline(1/N_CLASSES, color="r", ls=":", lw=0.7, alpha=0.6, label=f"chance ({1/N_CLASSES:.2f})")
    ax.axhline(seed_acc.mean(), color="grey", ls="--", lw=0.7, alpha=0.6, label=f"mean of seeds ({seed_acc.mean():.3f})")
    ax.set_ylim(0.25, 0.85); ax.set_ylabel("test accuracy")
    ax.set_title(f"Phase 11d — 5-seed ensemble\nmean {seed_acc.mean():.3f} ± {seed_acc.std():.3f}, ensemble {ens_acc:.3f}")
    ax.legend(); ax.grid(alpha=0.3, axis="y")

    cm = confusion_matrix(yte, ens_pred, labels=list(range(N_CLASSES)))
    cm_n = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    ax = axes[1]
    im = ax.imshow(cm_n, cmap="Blues", vmin=0, vmax=1)
    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    ax.set_xticks(range(N_CLASSES), names, rotation=20)
    ax.set_yticks(range(N_CLASSES), names)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Ensemble test acc = {ens_acc:.3f}")
    for i in range(N_CLASSES):
        for j in range(N_CLASSES):
            ax.text(j, i, f"{cm_n[i,j]:.2f}\n({cm[i,j]})", ha="center", va="center",
                    color="white" if cm_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig_path = figures / "phase11d_cnn_ensemble.png"
    fig.savefig(fig_path, dpi=130); plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
