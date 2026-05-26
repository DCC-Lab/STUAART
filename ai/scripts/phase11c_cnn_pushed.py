"""Phase 11c — 1-D CNN with bigger kernels, augmentation, longer training.

Same setup as 11b (3-class, raw, interval-aware split) but:
  - kernel sizes 21 / 15 / 9 (vs 11 / 7 / 5)
  - data aug: random shift ±4 samples (±50 ms), additive Gaussian noise σ=0.3 g
  - 200 epochs with cosine LR schedule, patience=30
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

RNG_SEED  = 42
CLASSES   = (1, 3, 4)
TEST_FRAC = 0.20
VAL_FRAC  = 0.15
WIN_N     = 160
N_CLASSES = len(CLASSES)
DEVICE    = "cuda" if torch.cuda.is_available() else "cpu"

EPOCHS    = 200
BATCH     = 32
LR        = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE  = 30

AUG_SHIFT_SAMPLES = 4    # ±50 ms
AUG_NOISE_STD     = 0.3  # grams (added directly to raw m_total)


def split_3way_by_interval(windows, rng):
    train, val, test = set(), set(), set()
    for c in CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        n = len(ids); n_test = max(1, int(round(n * TEST_FRAC)))
        n_val = max(1, int(round(n * VAL_FRAC)))
        test |= set(ids[:n_test])
        val |= set(ids[n_test:n_test+n_val])
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


def augment(X: torch.Tensor, shift: int = AUG_SHIFT_SAMPLES, noise_std: float = AUG_NOISE_STD) -> torch.Tensor:
    """Random per-sample temporal shift (with edge-padding) + additive Gaussian noise."""
    B, N = X.shape
    # Random integer shifts uniform in [-shift, +shift]
    shifts = torch.randint(-shift, shift + 1, (B,), device=X.device)
    out = torch.empty_like(X)
    for i in range(B):
        s = int(shifts[i].item())
        if s == 0:
            out[i] = X[i]
        elif s > 0:
            out[i, :-s] = X[i, s:]
            out[i, -s:] = X[i, -1]  # edge pad
        else:
            k = -s
            out[i, k:] = X[i, :-k]
            out[i, :k] = X[i, 0]
    if noise_std > 0:
        out = out + torch.randn_like(out) * noise_std
    return out


class CNN1D(nn.Module):
    def __init__(self, n_classes, p_drop=0.3):
        super().__init__()
        self.feat = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=21, padding=10),
            nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(2),         # 160 -> 80
            nn.Conv1d(16, 32, kernel_size=15, padding=7),
            nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(2),         # 80 -> 40
            nn.Conv1d(32, 64, kernel_size=9, padding=4),
            nn.BatchNorm1d(64), nn.ReLU(), nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(p_drop), nn.Linear(64, n_classes))

    def forward(self, x):
        if x.ndim == 2:
            x = x.unsqueeze(1)
        return self.head(self.feat(x))


def train_eval(Xtr, ytr, Xvl, yvl, Xte, yte):
    torch.manual_seed(RNG_SEED); np.random.seed(RNG_SEED)
    model = CNN1D(N_CLASSES).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=EPOCHS)
    loss_fn = nn.CrossEntropyLoss()

    T = lambda a, d=torch.float32: torch.from_numpy(a).to(DEVICE).to(d)
    Xtr_t = T(Xtr); ytr_t = T(ytr, torch.long)
    Xvl_t = T(Xvl); yvl_t = T(yvl, torch.long)
    Xte_t = T(Xte); yte_t = T(yte, torch.long)

    history = []; best_val = -1.0; best_state = None; bad = 0
    n = Xtr_t.shape[0]
    for epoch in range(EPOCHS):
        model.train()
        perm = torch.randperm(n, device=DEVICE)
        ep_loss = 0.0
        for i in range(0, n, BATCH):
            j = perm[i:i+BATCH]
            xb = augment(Xtr_t[j])
            opt.zero_grad()
            loss = loss_fn(model(xb), ytr_t[j])
            loss.backward(); opt.step()
            ep_loss += loss.item() * len(j)
        sched.step()
        ep_loss /= n
        model.eval()
        with torch.no_grad():
            tr_acc = (model(Xtr_t).argmax(1) == ytr_t).float().mean().item()
            vl_acc = (model(Xvl_t).argmax(1) == yvl_t).float().mean().item()
        history.append({"epoch": epoch, "loss": ep_loss, "train_acc": tr_acc, "val_acc": vl_acc,
                        "lr": opt.param_groups[0]["lr"]})
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
        te_pred = model(Xte_t).argmax(1).cpu().numpy()
        tr_pred = model(Xtr_t).argmax(1).cpu().numpy()
    return {
        "history": history,
        "test_acc": accuracy_score(yte, te_pred),
        "train_acc": accuracy_score(ytr, tr_pred),
        "best_val": best_val,
        "y_true": yte, "y_pred": te_pred,
        "cm": confusion_matrix(yte, te_pred, labels=list(range(N_CLASSES))),
    }


def main():
    interim = ROOT / "data" / "interim"; figures = ROOT / "figures"
    rng = np.random.default_rng(RNG_SEED)
    windows = pl.read_parquet(ROOT / "data" / "processed" / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"3-class windows: {windows.height:,}  chance={1/N_CLASSES:.3f}  device={DEVICE}")

    tr_ids, vl_ids, te_ids = split_3way_by_interval(windows, rng)
    tr = balance(windows.filter(pl.col("source_interval_id").is_in(list(tr_ids))), rng)
    vl = balance(windows.filter(pl.col("source_interval_id").is_in(list(vl_ids))), rng)
    te = balance(windows.filter(pl.col("source_interval_id").is_in(list(te_ids))), rng)
    print(f"balanced: train {tr.height}  val {vl.height}  test {te.height}   "
          f"per-class {tr.height//N_CLASSES} / {vl.height//N_CLASSES} / {te.height//N_CLASSES}")

    Xtr, ytr = to_arrays(tr); Xvl, yvl = to_arrays(vl); Xte, yte = to_arrays(te)
    print(f"\nstarting training: kernels 21/15/9, aug shift ±{AUG_SHIFT_SAMPLES}, aug noise σ={AUG_NOISE_STD} g, epochs={EPOCHS}, patience={PATIENCE}")
    r = train_eval(Xtr, ytr, Xvl, yvl, Xte, yte)
    print(f"\nepochs trained: {len(r['history'])}   best val {r['best_val']:.3f}")
    print(f"train (best ckpt) {r['train_acc']:.3f}    test {r['test_acc']:.3f}")
    print(classification_report(r["y_true"], r["y_pred"],
                                target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3, zero_division=0))

    cm = r["cm"]; cm_n = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    pl.DataFrame([{"train_acc": r["train_acc"], "val_acc": r["best_val"], "test_acc": r["test_acc"],
                   "epochs": len(r["history"])}]).write_csv(interim / "phase11c_cnn_pushed_results.csv")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)
    h = r["history"]; ep = [d["epoch"] for d in h]
    ax = axes[0]
    ax.plot(ep, [d["train_acc"] for d in h], label="train", lw=1.5)
    ax.plot(ep, [d["val_acc"]   for d in h], label="val",   lw=1.5)
    ax.axhline(1/N_CLASSES, color="r", ls=":", lw=0.7, alpha=0.6, label=f"chance ({1/N_CLASSES:.2f})")
    ax.axhline(r["test_acc"], color="g", ls="--", lw=0.7, alpha=0.6, label=f"test ({r['test_acc']:.3f})")
    ax.set_xlabel("epoch"); ax.set_ylabel("accuracy"); ax.legend(); ax.grid(alpha=0.3)
    ax.set_title(f"Phase 11c — pushed CNN 3-class\nbest val {r['best_val']:.3f}, test {r['test_acc']:.3f}")
    ax.set_ylim(0.25, 1.02)

    ax = axes[1]
    im = ax.imshow(cm_n, cmap="Blues", vmin=0, vmax=1)
    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    ax.set_xticks(range(N_CLASSES), names, rotation=20)
    ax.set_yticks(range(N_CLASSES), names)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Test accuracy = {r['test_acc']:.3f}")
    for i in range(N_CLASSES):
        for j in range(N_CLASSES):
            ax.text(j, i, f"{cm_n[i,j]:.2f}\n({cm[i,j]})", ha="center", va="center",
                    color="white" if cm_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig_path = figures / "phase11c_cnn_pushed.png"
    fig.savefig(fig_path, dpi=130); plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
