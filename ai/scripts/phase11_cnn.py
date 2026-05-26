"""Phase 11 — 1-D CNN on raw m_total windows.

Same interval-aware 80/10/10 (train/val/test) split as before, classes 0/1/3/4,
balanced. Two variants: raw signal vs per-window z-normalized signal.

Lightweight CNN: 3 conv blocks → global average pool → linear head. Dropout for
regularization. Early stopping on validation accuracy.
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
CLASSES   = (0, 1, 3, 4)
TEST_FRAC = 0.20
VAL_FRAC  = 0.15   # of training intervals
WIN_N     = 160
N_CLASSES = len(CLASSES)
DEVICE    = "cuda" if torch.cuda.is_available() else "cpu"

EPOCHS    = 80
BATCH     = 32
LR        = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE  = 15  # early stop


def split_3way_by_interval(windows: pl.DataFrame, rng):
    train, val, test = set(), set(), set()
    for c in CLASSES:
        ids = (windows.filter(pl.col("label") == c)
                      .select("source_interval_id").unique().to_series().to_list())
        rng.shuffle(ids)
        n = len(ids); n_test = max(1, int(round(n * TEST_FRAC)))
        n_val = max(1, int(round(n * VAL_FRAC)))
        test  |= set(ids[:n_test])
        val   |= set(ids[n_test:n_test+n_val])
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


def to_arrays(windows: pl.DataFrame, normalize: bool):
    X = np.array(windows["signal"].to_list(), dtype=np.float32)
    if normalize:
        m = X.mean(axis=1, keepdims=True)
        s = X.std(axis=1, keepdims=True)
        s = np.where(s < 1e-6, 1.0, s)
        X = (X - m) / s
    y_raw = windows["label"].to_numpy().astype(int)
    label_idx = {c: i for i, c in enumerate(CLASSES)}
    y = np.array([label_idx[v] for v in y_raw], dtype=np.int64)
    return X, y


class CNN1D(nn.Module):
    def __init__(self, n_classes: int = N_CLASSES, p_drop: float = 0.3):
        super().__init__()
        self.feat = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=11, padding=5),
            nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(2),         # 160 -> 80
            nn.Conv1d(16, 32, kernel_size=7, padding=3),
            nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(2),         # 80 -> 40
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64), nn.ReLU(), nn.AdaptiveAvgPool1d(1), # -> 1
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(p_drop),
            nn.Linear(64, n_classes),
        )

    def forward(self, x):
        # x: (B, N) → (B, 1, N)
        if x.ndim == 2:
            x = x.unsqueeze(1)
        return self.head(self.feat(x))


def train_eval_cnn(name: str, Xtr, ytr, Xvl, yvl, Xte, yte) -> dict:
    torch.manual_seed(RNG_SEED)
    np.random.seed(RNG_SEED)

    model = CNN1D().to(DEVICE)
    opt   = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    loss_fn = nn.CrossEntropyLoss()

    Xtr_t = torch.from_numpy(Xtr).float().to(DEVICE)
    ytr_t = torch.from_numpy(ytr).long().to(DEVICE)
    Xvl_t = torch.from_numpy(Xvl).float().to(DEVICE)
    yvl_t = torch.from_numpy(yvl).long().to(DEVICE)
    Xte_t = torch.from_numpy(Xte).float().to(DEVICE)
    yte_t = torch.from_numpy(yte).long().to(DEVICE)

    history = []
    best_val = -1.0
    best_state = None
    bad = 0
    n = Xtr_t.shape[0]

    for epoch in range(EPOCHS):
        model.train()
        perm = torch.randperm(n, device=DEVICE)
        ep_loss = 0.0
        for i in range(0, n, BATCH):
            j = perm[i:i+BATCH]
            opt.zero_grad()
            logits = model(Xtr_t[j])
            loss = loss_fn(logits, ytr_t[j])
            loss.backward()
            opt.step()
            ep_loss += loss.item() * len(j)
        ep_loss /= n

        model.eval()
        with torch.no_grad():
            tr_pred = model(Xtr_t).argmax(1)
            vl_pred = model(Xvl_t).argmax(1)
            tr_acc = (tr_pred == ytr_t).float().mean().item()
            vl_acc = (vl_pred == yvl_t).float().mean().item()
        history.append({"epoch": epoch, "loss": ep_loss, "train_acc": tr_acc, "val_acc": vl_acc})

        if vl_acc > best_val:
            best_val = vl_acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
            if bad >= PATIENCE:
                break

    # Reload best, evaluate on test
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        te_pred = model(Xte_t).argmax(1).cpu().numpy()
        tr_pred = model(Xtr_t).argmax(1).cpu().numpy()
    test_acc = accuracy_score(yte, te_pred)
    train_acc_final = accuracy_score(ytr, tr_pred)

    print(f"\n=== {name} ===")
    print(f"epochs trained: {len(history)} (best val_acc = {best_val:.3f} at epoch {np.argmax([h['val_acc'] for h in history])})")
    print(f"train acc (best ckpt): {train_acc_final:.3f}    test acc: {test_acc:.3f}")
    print(classification_report(yte, te_pred, target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3))

    cm = confusion_matrix(yte, te_pred, labels=list(range(N_CLASSES)))
    return {
        "name": name, "history": history, "test_acc": test_acc, "train_acc": train_acc_final,
        "best_val": best_val, "cm": cm,
        "cm_norm": cm / cm.sum(axis=1, keepdims=True).clip(min=1),
        "y_true": yte, "y_pred": te_pred,
    }


def main():
    interim = ROOT / "data" / "interim"; figures = ROOT / "figures"
    rng = np.random.default_rng(RNG_SEED)

    windows = pl.read_parquet(ROOT / "data" / "processed" / "windows_train.parquet")
    windows = windows.filter(pl.col("label").is_in(list(CLASSES)))
    print(f"4-class windows: {windows.height:,}  device={DEVICE}")

    tr_ids, vl_ids, te_ids = split_3way_by_interval(windows, rng)
    tr = balance(windows.filter(pl.col("source_interval_id").is_in(list(tr_ids))), rng)
    vl = balance(windows.filter(pl.col("source_interval_id").is_in(list(vl_ids))), rng)
    te = balance(windows.filter(pl.col("source_interval_id").is_in(list(te_ids))), rng)
    print(f"balanced: train {tr.height}  val {vl.height}  test {te.height}   "
          f"per-class {tr.height//N_CLASSES} / {vl.height//N_CLASSES} / {te.height//N_CLASSES}")

    Xtr_r, ytr = to_arrays(tr, normalize=False)
    Xvl_r, yvl = to_arrays(vl, normalize=False)
    Xte_r, yte = to_arrays(te, normalize=False)
    Xtr_n, _   = to_arrays(tr, normalize=True)
    Xvl_n, _   = to_arrays(vl, normalize=True)
    Xte_n, _   = to_arrays(te, normalize=True)

    r_raw  = train_eval_cnn("CNN on RAW",        Xtr_r, ytr, Xvl_r, yvl, Xte_r, yte)
    r_norm = train_eval_cnn("CNN on Z-NORM",     Xtr_n, ytr, Xvl_n, yvl, Xte_n, yte)

    pl.DataFrame([
        {"variant": "raw",         "train_acc": r_raw["train_acc"],  "val_acc": r_raw["best_val"],  "test_acc": r_raw["test_acc"]},
        {"variant": "z-normalized", "train_acc": r_norm["train_acc"], "val_acc": r_norm["best_val"], "test_acc": r_norm["test_acc"]},
    ]).write_csv(interim / "phase11_cnn_results.csv")

    # Plot learning curves + confusions
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
    for ax, r in zip(axes[0], (r_raw, r_norm)):
        h = r["history"]
        ep = [d["epoch"] for d in h]
        ax.plot(ep, [d["train_acc"] for d in h], label="train", lw=1.5)
        ax.plot(ep, [d["val_acc"]   for d in h], label="val",   lw=1.5)
        ax.axhline(1/N_CLASSES, color="r", ls=":", lw=0.7, alpha=0.6, label=f"chance ({1/N_CLASSES:.2f})")
        ax.axhline(r["test_acc"], color="g", ls="--", lw=0.7, alpha=0.6, label=f"test ({r['test_acc']:.3f})")
        ax.set_title(f"{r['name']}: best val {r['best_val']:.3f}, test {r['test_acc']:.3f}")
        ax.set_xlabel("epoch"); ax.set_ylabel("accuracy"); ax.legend(); ax.grid(alpha=0.3)
        ax.set_ylim(0.15, 1.02)

    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    for ax, r in zip(axes[1], (r_raw, r_norm)):
        cm = r["cm_norm"]
        im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(N_CLASSES), names, rotation=20)
        ax.set_yticks(range(N_CLASSES), names)
        ax.set_xlabel("predicted"); ax.set_ylabel("true")
        ax.set_title(f"{r['name']}  test={r['test_acc']:.3f}")
        for i in range(N_CLASSES):
            for j in range(N_CLASSES):
                ax.text(j, i, f"{cm[i,j]:.2f}\n({r['cm'][i,j]})", ha="center", va="center",
                        color="white" if cm[i,j] > 0.5 else "black", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig_path = figures / "phase11_cnn.png"
    fig.savefig(fig_path, dpi=130); plt.close(fig)
    print(f"\nwrote {fig_path}")


if __name__ == "__main__":
    main()
