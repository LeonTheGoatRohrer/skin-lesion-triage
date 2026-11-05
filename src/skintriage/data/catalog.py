"""Bild-Katalog: eine Zeile pro Bild mit Label, Domäne, Quelle, Gruppe und Split.

Quelle der Wahrheit ist die Metadaten-Tabelle des gesamten ISIC-Archivs
(``snapshots/ISIC_metadata.parquet``). Sie enthält Diagnose, Patient, Läsion, Bildtyp und
Lizenz für alle verwendeten Datensätze (MILK10k, SLICE-3D/ISIC 2024, PAD-UFES-20, MSK).

Wichtig gegen Datenlecks: Bilder, die einen Patienten **oder** eine Läsion teilen, landen über
Union-Find in derselben Gruppe, und Gruppen werden nie über Splits verteilt. So liegen z. B. das
Kamerafoto und das Dermoskopie-Bild derselben MILK10k-Läsion immer im selben Split.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from skintriage import config, labels

SOURCE_BY_ATTRIBUTION = {
    "MILK study team": "milk10k",
    "Federal University of Espírito Santo (UFES)": "pad_ufes_20",
    "Memorial Sloan Kettering Cancer Center": "msk",
    "Anonymous": "anonymous",
    "Hospital Italiano de Buenos Aires": "hiba",
}


def _domain(image_type: str, attribution: str) -> str | None:
    if image_type == "clinical: close-up":
        return "clinical"
    if image_type == "TBP tile: close-up":
        return "tbp"
    if image_type == "dermoscopic" and attribution == "MILK study team":
        return "dermoscopic"  # nur die Dermoskopie-Paare zu den MILK10k-Kamerafotos
    return None


def _image_ref(row, raw_dir: Path) -> tuple[str, str]:
    if row.source == "milk10k":
        return (str(raw_dir / "milk10k" / "MILK10k_Training_Input.zip"),
                f"MILK10k_Training_Input/{row.lesion_id}/{row.isic_id}.jpg")
    if row.source == "slice3d":
        return (str(raw_dir / "isic2024" / "ISIC_2024_Training_Input.zip"),
                f"ISIC_2024_Training_Input/{row.isic_id}.jpg")
    return (str(raw_dir / "archive_images" / f"{row.isic_id}.jpg"), "")


class _UnionFind:
    def __init__(self, n: int):
        self.p = np.arange(n)

    def find(self, i: int) -> int:
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def assign_groups(patient_id: pd.Series, lesion_id: pd.Series) -> np.ndarray:
    """Gruppen-ID je Bild: verbunden, wenn Patient oder Läsion übereinstimmen."""
    n = len(patient_id)
    uf = _UnionFind(n)
    for key in (patient_id, lesion_id):
        first: dict[str, int] = {}
        for i, v in enumerate(key.to_numpy()):
            if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
                continue
            if v in first:
                uf.union(first[v], i)
            else:
                first[v] = i
    roots = np.array([uf.find(i) for i in range(n)])
    _, gid = np.unique(roots, return_inverse=True)
    return gid


def split_groups(df: pd.DataFrame, seed: int = config.SEED,
                 val_frac: float = config.VAL_FRACTION, test_frac: float = config.TEST_FRACTION) -> pd.Series:
    """Weist ganzen Gruppen train/val/test zu, stratifiziert nach (Domäne, enthält bösartig)."""
    g = df.groupby("group").agg(domain=("domain", lambda s: s.mode().iat[0]),
                                mal=("binary", lambda s: int((s == labels.BIN_MALIGNANT).any())),
                                n=("binary", "size"))
    rng = np.random.default_rng(seed)
    split_of_group: dict[int, str] = {}
    for _, sub in g.groupby(["domain", "mal"]):
        ids = sub.index.to_numpy().copy()
        rng.shuffle(ids)
        sizes = sub.loc[ids, "n"].to_numpy()
        frac = np.cumsum(sizes) / sizes.sum()
        for gid, f in zip(ids, frac):
            split_of_group[gid] = "test" if f <= test_frac else ("val" if f <= test_frac + val_frac else "train")
    return df["group"].map(split_of_group)


def build_catalog(raw_dir: Path = config.RAW_DIR, seed: int = config.SEED) -> pd.DataFrame:
    meta = pd.read_parquet(raw_dir / "isic_meta" / "ISIC_metadata.parquet")
    meta = meta[meta.image_type.isin(["clinical: close-up", "TBP tile: close-up", "dermoscopic"])]
    meta = meta.assign(domain=[_domain(t, a) for t, a in zip(meta.image_type, meta.attribution)])
    meta = meta[meta.domain.notna()].copy()
    meta["source"] = np.where(meta.domain == "tbp", "slice3d", meta.attribution.map(SOURCE_BY_ATTRIBUTION))
    meta = meta[meta.source.notna()]

    meta["binary"] = [labels.binary_label(a, b) for a, b in zip(meta.diagnosis_1, meta.diagnosis_3)]
    masks = [labels.label_mask(a, b) for a, b in zip(meta.diagnosis_1, meta.diagnosis_3)]
    meta["mask_bits"] = [labels.mask_to_bits(m) if m is not None else 0 for m in masks]
    meta["group_label"] = [g if g is not None else -1
                           for g in (labels.group_from_diagnosis(a, b)
                                     for a, b in zip(meta.diagnosis_1, meta.diagnosis_3))]
    meta = meta[meta.binary != labels.BIN_UNKNOWN].reset_index(drop=True)

    meta["group"] = assign_groups(meta.patient_id, meta.lesion_id)
    internal = ~meta.source.isin(config.EXTERNAL_SOURCES)
    meta["split"] = "external"
    meta.loc[internal, "split"] = split_groups(meta[internal], seed=seed).to_numpy()

    # SLICE-3D: gutartige Bilder je Split stichprobenartig, mit Gewicht 1/p
    meta["weight"] = 1.0
    meta["use"] = True
    rng = np.random.default_rng(seed + 1)
    for split, n_keep in config.TBP_BENIGN_SAMPLE.items():
        idx = meta.index[(meta.domain == "tbp") & (meta.split == split) & (meta.binary == labels.BIN_BENIGN)]
        if len(idx) > n_keep:
            keep = rng.choice(idx, size=n_keep, replace=False)
            meta.loc[idx, "use"] = False
            meta.loc[keep, "use"] = True
            meta.loc[keep, "weight"] = len(idx) / n_keep
    meta = meta[meta.use].drop(columns="use").reset_index(drop=True)

    refs = [_image_ref(r, raw_dir) for r in meta.itertuples()]
    meta["file"] = [r[0] for r in refs]
    meta["member"] = [r[1] for r in refs]

    keep_cols = ["isic_id", "domain", "source", "split", "group", "patient_id", "lesion_id",
                 "binary", "group_label", "mask_bits", "weight", "diagnosis_1", "diagnosis_3",
                 "diagnosis_confirm_type", "fitzpatrick_skin_type", "age_approx", "sex",
                 "anatom_site_general", "copyright_license", "attribution", "file", "member"]
    return meta[keep_cols]


def summarize(cat: pd.DataFrame) -> pd.DataFrame:
    t = cat.assign(n=1)
    return pd.pivot_table(t, index=["split", "domain", "source"], columns="binary", values="n",
                          aggfunc="sum", fill_value=0).rename(
        columns={0: "gutartig", 1: "bösartig", 2: "Vorstufe (AK)"})
