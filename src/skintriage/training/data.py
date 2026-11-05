"""Zugriff auf Katalog + Memmap(s) und der domänen-balancierte Sampler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from skintriage import config, labels


class ShardedImages:
    """Mehrere uint8-Memmaps [N_i,S,S,3] hintereinander, adressiert über globale Zeilennummern."""

    def __init__(self, shards: list[np.ndarray]):
        self.shards = shards
        self.offsets = np.cumsum([0] + [len(s) for s in shards])
        self.shape = (int(self.offsets[-1]),) + tuple(shards[0].shape[1:])

    def __len__(self) -> int:
        return self.shape[0]

    def __getitem__(self, rows):
        rows = np.asarray(rows)
        if rows.ndim == 0:
            k = int(np.searchsorted(self.offsets, rows, side="right") - 1)
            return self.shards[k][int(rows) - self.offsets[k]]
        out = np.empty((len(rows),) + self.shape[1:], dtype=np.uint8)
        shard = np.searchsorted(self.offsets, rows, side="right") - 1
        for k in np.unique(shard):
            m = shard == k
            out[m] = self.shards[k][rows[m] - self.offsets[k]]
        return out


@dataclass
class ImageStore:
    catalog: pd.DataFrame
    images: np.ndarray | ShardedImages

    @classmethod
    def open(cls, processed_dir: Path = config.PROCESSED_DIR, size: int = config.STORE_SIZE,
             use_extra: bool = False) -> "ImageStore":
        cat = pd.read_parquet(processed_dir / "catalog.parquet")
        base = np.memmap(processed_dir / f"images_{size}.u8", dtype=np.uint8, mode="r",
                         shape=(len(cat), size, size, 3))
        if not use_extra:
            return cls(cat[cat.ok].reset_index(drop=True), base)
        extra = pd.read_parquet(processed_dir / "catalog_extra.parquet")
        emm = np.memmap(processed_dir / f"images_extra_{size}.u8", dtype=np.uint8, mode="r",
                        shape=(len(extra), size, size, 3))
        extra = extra.assign(row=extra.row + len(cat))
        both = pd.concat([cat, extra], ignore_index=True)
        return cls(both[both.ok].reset_index(drop=True), ShardedImages([base, emm]))

    def batch(self, rows: np.ndarray) -> torch.Tensor:
        order = np.argsort(rows)
        out = np.empty((len(rows),) + tuple(self.images.shape[1:]), dtype=np.uint8)
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

    ``group_balance`` (0 … 1) gleicht zusätzlich die Diagnose-Gruppen *innerhalb* einer
    Schicht an: Ziehgewicht ∝ (Anzahl der Gruppe)^(−group_balance). Bei 0 dominieren unter den
    bösartigen Kamerafotos die Basalzellkarzinome (~70 %), Melanome kämen kaum vor.
    """

    def __init__(self, catalog: pd.DataFrame, idx: np.ndarray, fractions: dict[str, float],
                 pos_fraction: dict[str, float], seed: int, group_balance: float = 0.0):
        self.rng = np.random.default_rng(seed)
        cat = catalog.iloc[idx]
        self.strata: list[tuple[np.ndarray, float, np.ndarray | None]] = []
        total = sum(fractions.values())
        glab = cat.group_label.to_numpy()
        for dom, frac in fractions.items():
            if frac <= 0:
                continue
            pf = pos_fraction.get(dom, 0.5)
            dmask = (cat.domain == dom).to_numpy()
            for is_pos, share in ((True, pf), (False, 1 - pf)):
                m = dmask & ((cat.binary == labels.BIN_MALIGNANT).to_numpy() == is_pos)
                pool = idx[m]
                if len(pool) == 0:
                    raise ValueError(f"Domäne {dom}: keine {'Positiv' if is_pos else 'Negativ'}beispiele")
                probs = None
                if group_balance > 0:
                    g = glab[m]
                    _, inv, cnt = np.unique(g, return_inverse=True, return_counts=True)
                    w = cnt[inv].astype(float) ** (-group_balance)
                    probs = w / w.sum()
                self.strata.append((pool, frac / total * share, probs))

    def epoch(self, n: int) -> np.ndarray:
        counts = self.rng.multinomial(n, [w for _, w, _ in self.strata])
        parts = [self.rng.choice(pool, size=c, replace=True, p=pr)
                 for (pool, _, pr), c in zip(self.strata, counts)]
        out = np.concatenate(parts)
        self.rng.shuffle(out)
        return out
