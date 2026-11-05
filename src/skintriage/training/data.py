"""Zugriff auf Katalog + Memmap und der domänen-balancierte Sampler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from skintriage import config, labels


@dataclass
class ImageStore:
    catalog: pd.DataFrame
    images: np.memmap

    @classmethod
    def open(cls, processed_dir: Path = config.PROCESSED_DIR, size: int = config.STORE_SIZE) -> "ImageStore":
        cat = pd.read_parquet(processed_dir / "catalog.parquet")
        imgs = np.memmap(processed_dir / f"images_{size}.u8", dtype=np.uint8, mode="r",
                         shape=(len(cat), size, size, 3))
        return cls(cat[cat.ok].reset_index(drop=True), imgs)

    def batch(self, rows: np.ndarray) -> torch.Tensor:
        order = np.argsort(rows)
        out = np.empty((len(rows),) + self.images.shape[1:], dtype=np.uint8)
        out[order] = self.images[rows[order]]  # sortierter Zugriff ist auf der Platte schneller
        return torch.from_numpy(out)

    def masks(self, idx: np.ndarray) -> torch.Tensor:
        bits = self.catalog.mask_bits.to_numpy()[idx]
        return torch.from_numpy(np.stack([labels.bits_to_mask(int(b)) for b in bits]))


class StratifiedSampler:
    """Zieht je Batch feste Anteile aus Schichten (Domäne × bösartig ja/nein).

    Damit verrät die *Domäne* im Training nichts über das Label: Ohne Balancierung wären
    MILK10k-Fotos zu 70 % bösartig, SLICE-3D-Ausschnitte zu 0,1 % – das Netz könnte
    "Kamerafoto = Krebs" lernen statt auf die Hautstelle zu schauen.
    """

    def __init__(self, catalog: pd.DataFrame, idx: np.ndarray, fractions: dict[str, float],
                 pos_fraction: dict[str, float], seed: int):
        self.rng = np.random.default_rng(seed)
        cat = catalog.iloc[idx]
        self.strata: list[tuple[np.ndarray, float]] = []
        total = sum(fractions.values())
        for dom, frac in fractions.items():
            if frac <= 0:
                continue
            pf = pos_fraction.get(dom, 0.5)
            dmask = (cat.domain == dom).to_numpy()
            pos = idx[dmask & (cat.binary == labels.BIN_MALIGNANT).to_numpy()]
            neg = idx[dmask & (cat.binary != labels.BIN_MALIGNANT).to_numpy()]
            if len(pos) == 0 or len(neg) == 0:
                raise ValueError(f"Domäne {dom}: keine Positiv- oder Negativbeispiele im Training")
            self.strata.append((pos, frac / total * pf))
            self.strata.append((neg, frac / total * (1 - pf)))

    def epoch(self, n: int) -> np.ndarray:
        counts = self.rng.multinomial(n, [w for _, w in self.strata])
        parts = [self.rng.choice(pool, size=c, replace=True) for (pool, _), c in zip(self.strata, counts)]
        out = np.concatenate(parts)
        self.rng.shuffle(out)
        return out
