"""Batch-Inferenz über Bilder aus dem ImageStore (optional mit Test-Time-Augmentation)."""

from __future__ import annotations

import numpy as np
import torch

from skintriage.training.augment import normalize, to_model_input


@torch.no_grad()
def predict(model: torch.nn.Module, images: np.ndarray | torch.Tensor, rows: np.ndarray, size: int,
            batch_size: int = 256, tta: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Gibt (logits[N,7], embeddings[N,D]) zurück. ``images`` ist ein uint8-Array [M,H,W,3]."""
    model.eval()
    logits, embs = [], []
    for start in range(0, len(rows), batch_size):
        r = np.asarray(rows[start:start + batch_size])
        order = np.argsort(r)
        raw = np.empty((len(r),) + tuple(images.shape[1:]), dtype=np.uint8)
        raw[order] = images[r[order]]
        x = normalize(to_model_input(torch.from_numpy(raw), size)).contiguous(memory_format=torch.channels_last)
        views = [x, x.flip(3), x.flip(2), x.transpose(2, 3)] if tta else [x]
        lo, em = 0, 0
        for v in views:
            l_, e_ = model(v)
            lo, em = lo + l_, em + e_
        logits.append((lo / len(views)).numpy())
        embs.append((em / len(views)).numpy())
    return np.concatenate(logits), np.concatenate(embs)


def malignant_logit_np(logits: np.ndarray) -> np.ndarray:
    from skintriage.models.net import malignant_logit

    return malignant_logit(torch.from_numpy(logits)).numpy()


def group_probs_np(logits: np.ndarray) -> np.ndarray:
    return torch.softmax(torch.from_numpy(logits), dim=1).numpy()
