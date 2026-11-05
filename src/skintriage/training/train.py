"""Trainingsschleife (CPU-tauglich): domänen-balancierter Sampler, Batch-Augmentierung,
AdamW + Cosinus, EMA der Gewichte, Validierung je Epoche nur auf dem Val-Split.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

import numpy as np
import torch
from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn

from skintriage import config, labels
from skintriage.evaluation import metrics
from skintriage.models.infer import malignant_logit_np, predict
from skintriage.models.losses import set_nll
from skintriage.models.net import TriageNet
from skintriage.training.augment import AugConfig, augment, normalize
from skintriage.training.data import ImageStore, StratifiedSampler


@dataclass
class TrainConfig:
    name: str = "default"
    backbone: str = "mobilenetv3_large_100"
    image_size: int = config.IMAGE_SIZE
    epochs: int = 10
    samples_per_epoch: int = 16_000
    batch_size: int = 64
    lr: float = 6e-4
    head_lr_mult: float = 5.0
    weight_decay: float = 0.02
    warmup_steps: int = 150
    domains: dict = field(default_factory=lambda: {"clinical": 0.4, "tbp": 0.3, "dermoscopic": 0.3})
    pos_fraction: dict = field(default_factory=lambda: {"clinical": 0.5, "tbp": 0.35, "dermoscopic": 0.5})
    ema_decay: float = 0.998
    smoothing: float = 0.05
    drop_rate: float = 0.2
    aug: dict = field(default_factory=dict)
    seed: int = 0
    threads: int = 4
    val_max_tbp_benign: int = 6000  # Val je Epoche: Stichprobe der SLICE-3D-Gutartigen (Tempo)

    @classmethod
    def from_json(cls, path: str | Path) -> "TrainConfig":
        return cls(**json.loads(Path(path).read_text()))

    def override(self, key: str, value: str) -> "TrainConfig":
        types = {f.name: f.type for f in fields(self)}
        if key not in types:
            raise KeyError(f"Unbekanntes Feld: {key}")
        try:
            v = json.loads(value)
        except json.JSONDecodeError:
            v = value
        return replace(self, **{key: v})


def _lr_factor(step: int, total: int, warmup: int) -> float:
    if step < warmup:
        return (step + 1) / warmup
    p = (step - warmup) / max(1, total - warmup)
    return 0.5 * (1 + math.cos(math.pi * min(1.0, p)))


def val_indices(cat, max_tbp_benign: int, seed: int) -> np.ndarray:
    v = cat.index[(cat.split == "val") & cat.binary.isin([0, 1])].to_numpy()
    tbp_neg = v[((cat.domain == "tbp") & (cat.binary == 0)).to_numpy()[v]]
    if len(tbp_neg) > max_tbp_benign:
        drop = np.random.default_rng(seed).choice(tbp_neg, len(tbp_neg) - max_tbp_benign, replace=False)
        v = np.setdiff1d(v, drop)
    return v


def quick_eval(model, store: ImageStore, idx: np.ndarray, size: int) -> dict:
    cat = store.catalog
    logits, _ = predict(model, store.images, cat.row.to_numpy()[idx], size)
    s = malignant_logit_np(logits)
    out = {}
    for dom in config.DOMAINS:
        m = (cat.domain.to_numpy()[idx] == dom)
        if m.sum() == 0:
            continue
        y = cat.binary.to_numpy()[idx][m]
        out[dom] = {"auroc": metrics.auroc(y, s[m]), "pauc80": metrics.pauc_above_tpr(y, s[m]),
                    "n_pos": int(y.sum()), "n": int(m.sum())}
    out["selection"] = float(np.nanmean([out[d]["auroc"] for d in ("clinical", "tbp") if d in out]))
    return out


def train(cfg: TrainConfig, out_dir: Path, store: ImageStore | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(asdict(cfg), indent=2))
    torch.set_num_threads(cfg.threads)
    torch.manual_seed(cfg.seed)
    g = torch.Generator().manual_seed(cfg.seed)

    store = store or ImageStore.open()
    cat = store.catalog
    doms = [d for d, f in cfg.domains.items() if f > 0]
    tr = cat.index[(cat.split == "train") & (cat.mask_bits > 0) & cat.domain.isin(doms)].to_numpy()
    sampler = StratifiedSampler(cat, tr, cfg.domains, cfg.pos_fraction, seed=cfg.seed)
    vidx = val_indices(cat, cfg.val_max_tbp_benign, cfg.seed)
    rows_all = cat.row.to_numpy()
    aug_cfg = replace(AugConfig(), **{k: tuple(v) if isinstance(v, list) else v for k, v in cfg.aug.items()})

    model = TriageNet(cfg.backbone, drop_rate=cfg.drop_rate).to(memory_format=torch.channels_last)
    ema = AveragedModel(model, multi_avg_fn=get_ema_multi_avg_fn(cfg.ema_decay), use_buffers=True)
    head = list(model.head.parameters())
    body = [p for n, p in model.named_parameters() if not n.startswith("head.")]
    decay = [p for p in body if p.ndim > 1]
    no_decay = [p for p in body if p.ndim <= 1]
    opt = torch.optim.AdamW([
        {"params": decay, "lr": cfg.lr, "weight_decay": cfg.weight_decay},
        {"params": no_decay, "lr": cfg.lr, "weight_decay": 0.0},
        {"params": head, "lr": cfg.lr * cfg.head_lr_mult, "weight_decay": cfg.weight_decay},
    ])
    base_lrs = [grp["lr"] for grp in opt.param_groups]
    steps_per_epoch = cfg.samples_per_epoch // cfg.batch_size
    total = steps_per_epoch * cfg.epochs
    history, step, t0 = [], 0, time.time()
    log = open(out_dir / "train.log", "a")

    def say(msg: str) -> None:
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    say(f"[{cfg.name}] Train-Pool {len(tr)} Bilder, {steps_per_epoch} Schritte/Epoche, Val {len(vidx)}")
    for epoch in range(cfg.epochs):
        model.train()
        idx = sampler.epoch(steps_per_epoch * cfg.batch_size)
        losses, te = [], time.time()
        for b in range(steps_per_epoch):
            bi = idx[b * cfg.batch_size:(b + 1) * cfg.batch_size]
            x = augment(store.batch(rows_all[bi]), cfg.image_size, aug_cfg, g)
            x = normalize(x).contiguous(memory_format=torch.channels_last)
            mask = store.masks(bi)
            for grp, base in zip(opt.param_groups, base_lrs):
                grp["lr"] = base * _lr_factor(step, total, cfg.warmup_steps)
            logits, _ = model(x)
            loss = set_nll(logits, mask, cfg.smoothing)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            ema.update_parameters(model)
            losses.append(loss.item())
            step += 1
            if (b + 1) % 50 == 0:
                say(f"  ep {epoch + 1} {b + 1}/{steps_per_epoch} loss {np.mean(losses[-50:]):.4f} "
                    f"({(b + 1) * cfg.batch_size / (time.time() - te):.0f} img/s)")
        ev = quick_eval(ema.module, store, vidx, cfg.image_size)
        history.append({"epoch": epoch + 1, "loss": float(np.mean(losses)), "val": ev,
                        "elapsed_min": (time.time() - t0) / 60})
        say(f"[{cfg.name}] Epoche {epoch + 1}/{cfg.epochs} loss {np.mean(losses):.4f} | " + " | ".join(
            f"{d} AUROC {ev[d]['auroc']:.3f} pAUC {ev[d]['pauc80']:.3f}" for d in config.DOMAINS if d in ev)
            + f" | {(time.time() - t0) / 60:.1f} min")
        (out_dir / "history.json").write_text(json.dumps(history, indent=2))
        torch.save({"config": asdict(cfg), "state_dict": ema.module.state_dict(), "epoch": epoch + 1},
                   out_dir / "model.pt")
    log.close()
    return out_dir / "model.pt"


def load_model(run_dir: Path) -> tuple[TriageNet, dict]:
    ck = torch.load(run_dir / "model.pt", map_location="cpu", weights_only=False)
    cfg = ck["config"]
    model = TriageNet(cfg["backbone"], drop_rate=cfg.get("drop_rate", 0.2), pretrained=False)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    return model.to(memory_format=torch.channels_last), cfg


__all__ = ["TrainConfig", "train", "load_model", "labels"]
