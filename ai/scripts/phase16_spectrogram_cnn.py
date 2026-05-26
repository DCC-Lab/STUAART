"""Phase 16 — 2-D CNN on time-frequency spectrograms.

Same data, same 5-fold-with-3-seed protocol as Phase 12 (1-D CNN got 0.604).
But the input is a (freq × time) spectrogram of each window, computed with
scipy.signal.spectrogram. This explicitly hands the model rhythm-in-time
structure instead of asking it to learn it from raw values.

Output: data/interim/phase16_cnn2d_kfold.csv, figures/phase16_cnn2d.png
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
from scipy.signal import spectrogram
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

from mousepipe.labels import CLASS_TO_GESTURE

CLASSES   = (1, 3, 4)
K_FOLDS   = 5
SEEDS     = [42, 123, 314]
N_CLASSES = len(CLASSES)
DEVICE    = "cuda" if torch.cuda.is_available() else "cpu"

EPOCHS   = 60
BATCH    = 32
LR       = 1e-3
WEIGHT_DECAY = 1e-4
PATIENCE = 20
VAL_FRAC = 0.15
DATA_SPLIT_SEED = 42

# STFT params (80 Hz sample rate, 160-sample windows)
FS = 80
NPERSEG  = 32   # 400 ms → Δf = 2.5 Hz
NOVERLAP = 24   # 75 % overlap → 17 time bins


def compute_spectrogram(x: np.ndarray) -> np.ndarray:
    """Returns log-magnitude spectrogram (freq × time)."""
    f, t, Sxx = spectrogram(x, fs=FS, nperseg=NPERSEG, noverlap=NOVERLAP, mode="magnitude")
    return np.log1p(Sxx).astype(np.float32)


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


def to_arrays(windows):
    sigs = windows["signal"].to_list()
    specs = np.stack([compute_spectrogram(np.asarray(s, dtype=np.float32)) for s in sigs])
    y_raw = windows["label"].to_numpy().astype(int)
    label_idx = {c: i for i, c in enumerate(CLASSES)}
    y = np.array([label_idx[v] for v in y_raw], dtype=np.int64)
    return specs, y


class CNN2D(nn.Module):
    def __init__(self, n_classes, in_freq, in_time, p_drop=0.3):
        super().__init__()
        self.feat = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d(2),  # F/2 × T/2
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),  # F/4 × T/4
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64), nn.ReLU(), nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(p_drop), nn.Linear(64, n_classes))

    def forward(self, x):
        if x.ndim == 3:  # (B, F, T) → (B, 1, F, T)
            x = x.unsqueeze(1)
        return self.head(self.feat(x))


def train_one_seed(seed, in_freq, in_time, Xtr, ytr, Xvl, yvl, Xte):
    torch.manual_seed(seed); np.random.seed(seed)
    model = CNN2D(N_CLASSES, in_freq, in_time).to(DEVICE)
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
            opt.zero_grad()
            loss = loss_fn(model(Xtr_t[j]), ytr_t[j])
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
    print(f"3-class windows: {windows.height:,}")

    # Determine spectrogram dimensions from one window
    sample_sig = np.asarray(windows["signal"][0], dtype=np.float32)
    spec0 = compute_spectrogram(sample_sig)
    in_freq, in_time = spec0.shape
    print(f"spectrogram shape (freq × time): {in_freq} × {in_time}")

    folds = make_folds(windows, rng)
    rows = []; y_true_all = []; y_pred_all = []; cms = []

    for k in range(K_FOLDS):
        test_iv = folds[k]
        trainval_iv = set().union(*[folds[j] for j in range(K_FOLDS) if j != k])
        te_pool = windows.filter(pl.col("source_interval_id").is_in(list(test_iv)))
        tv_pool = windows.filter(pl.col("source_interval_id").is_in(list(trainval_iv)))
        val_iv = set(); train_iv = set()
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
        print(f"--- fold {k} --- train {tr.height} val {vl.height} test {te.height}")

        seed_logits = []; per_seed_acc = []
        for s in SEEDS:
            tl = train_one_seed(s, in_freq, in_time, Xtr, ytr, Xvl, yvl, Xte)
            seed_logits.append(tl)
            per_seed_acc.append(accuracy_score(yte, tl.argmax(1)))
        ens_logits = np.mean(seed_logits, axis=0)
        ens_pred = ens_logits.argmax(1)
        fold_acc = accuracy_score(yte, ens_pred)
        cm = confusion_matrix(yte, ens_pred, labels=list(range(N_CLASSES)))
        cms.append(cm); y_true_all.append(yte); y_pred_all.append(ens_pred)
        rows.append({"fold": k, "n_test": te.height,
                     "per_seed_mean": float(np.mean(per_seed_acc)),
                     "per_seed_std": float(np.std(per_seed_acc)),
                     "ensemble_acc": fold_acc})
        print(f"  per-seed {np.mean(per_seed_acc):.3f}±{np.std(per_seed_acc):.3f}   ensemble {fold_acc:.3f}")

    df = pl.DataFrame(rows)
    accs = df["ensemble_acc"].to_numpy()
    se = accs.std(ddof=1) / np.sqrt(K_FOLDS)
    ci = (accs.mean() - 1.96*se, accs.mean() + 1.96*se)
    print(f"\n2-D CNN on spectrograms: mean {accs.mean():.3f} ± {accs.std():.3f}   95 % CI [{ci[0]:.3f}, {ci[1]:.3f}]")
    print(f"Compare to 1-D CNN Phase 12: 0.604  95 % CI [0.567, 0.642]")

    y_true_all = np.concatenate(y_true_all); y_pred_all = np.concatenate(y_pred_all)
    cm_total = confusion_matrix(y_true_all, y_pred_all, labels=list(range(N_CLASSES)))
    cm_total_n = cm_total / cm_total.sum(axis=1, keepdims=True).clip(min=1)
    print(classification_report(y_true_all, y_pred_all,
                                target_names=[CLASS_TO_GESTURE[c] for c in CLASSES], digits=3,
                                zero_division=0))
    df.write_csv(interim / "phase16_cnn2d_kfold.csv")

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), constrained_layout=True)
    # Panel 1: example spectrogram
    ax = axes[0]
    im = ax.imshow(spec0, aspect="auto", origin="lower", cmap="viridis")
    ax.set_title(f"Example spectrogram (freq×time = {in_freq}×{in_time})")
    ax.set_xlabel("time bin"); ax.set_ylabel("frequency bin")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # Panel 2: per-fold accuracy
    ax = axes[1]
    fa = list(range(K_FOLDS))
    ax.errorbar(fa, df["per_seed_mean"], yerr=df["per_seed_std"], fmt="o-",
                color="C0", label="mean ± std of 3 seeds")
    ax.plot(fa, df["ensemble_acc"], "s-", color="C2", label="ensemble")
    ax.axhline(1/N_CLASSES, color="r", ls=":", lw=0.7, alpha=0.6, label=f"chance ({1/N_CLASSES:.2f})")
    ax.axhline(accs.mean(), color="grey", ls="--", lw=0.7, alpha=0.6, label=f"mean ({accs.mean():.3f})")
    ax.fill_between(fa, [ci[0]]*K_FOLDS, [ci[1]]*K_FOLDS, color="grey", alpha=0.12)
    ax.axhline(0.604, color="C1", ls="--", lw=0.7, alpha=0.6, label="1-D CNN baseline (0.604)")
    ax.set_xlabel("fold"); ax.set_ylabel("test accuracy")
    ax.set_title(f"Phase 16 — 2-D CNN  mean {accs.mean():.3f} ± {accs.std():.3f}")
    ax.set_ylim(0.25, 0.85); ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # Panel 3: aggregated confusion
    ax = axes[2]
    im = ax.imshow(cm_total_n, cmap="Blues", vmin=0, vmax=1)
    names = [CLASS_TO_GESTURE[c] for c in CLASSES]
    ax.set_xticks(range(N_CLASSES), names, rotation=20)
    ax.set_yticks(range(N_CLASSES), names)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Aggregated confusion (n={cm_total.sum()})")
    for i in range(N_CLASSES):
        for j in range(N_CLASSES):
            ax.text(j, i, f"{cm_total_n[i,j]:.2f}\n({cm_total[i,j]})", ha="center", va="center",
                    color="white" if cm_total_n[i,j] > 0.5 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig_path = figures / "phase16_cnn2d.png"
    fig.savefig(fig_path, dpi=130); plt.close(fig)
    print(f"wrote {fig_path}")


if __name__ == "__main__":
    main()
