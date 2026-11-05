"""Zusatzdaten: Dermoskopie-Bilder aus dem ISIC-Archiv mit Melanom-Schwerpunkt (Experiment E4).

Warum: In E1 landeten auf den Validierungs-Kamerafotos 28 % der Melanome in Grün, während
Basalzellkarzinome fast nie übersehen wurden – bösartige Trainingsbilder sind überwiegend BCC.
Das Archiv hat ~10 000 Dermoskopie-Melanome; sie lehren den Unterschied Melanom ↔ Nävus.

Die Bilder werden beim Download sofort auf 160 px verkleinert und als eigener Memmap-Shard
gespeichert (die Originale sind teils mehrere MB groß). Splits: Teilt ein Bild Patient oder
Läsion mit dem bestehenden Katalog, erbt es dessen Split; sonst wird nach eigener Gruppe geteilt.
"""

from __future__ import annotations

import concurrent.futures as cf
import io
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from skintriage import config, labels
from skintriage.data.catalog import assign_groups, split_groups
from skintriage.data.preprocess import decode

PER_GROUP = {0: 5000, 4: 5000, 5: 1500, 1: 1500, 2: 800, 3: 800, 6: 800}
EXTRA_SOURCE = "isic_derm"


def select_extra(meta: pd.DataFrame, seed: int = config.SEED) -> pd.DataFrame:
    d = meta[(meta.image_type == "dermoscopic") & (meta.attribution != "MILK study team")].copy()
    d["group_label"] = [labels.group_from_diagnosis(a, b) for a, b in zip(d.diagnosis_1, d.diagnosis_3)]
    d = d[d.group_label.notna()].copy()
    d["group_label"] = d.group_label.astype(int)
    d["binary"] = [labels.binary_label(a, b) for a, b in zip(d.diagnosis_1, d.diagnosis_3)]
    # histologisch gesicherte Bilder zuerst, dann der Rest (zufällige Reihenfolge, fester Seed)
    rng = np.random.default_rng(seed)
    d["_r"] = rng.random(len(d)) + (d.diagnosis_confirm_type.astype(str) != "histopathology") * 1.0
    parts = [d[d.group_label == g].sort_values("_r").head(n) for g, n in PER_GROUP.items()]
    return pd.concat(parts).drop(columns="_r").reset_index(drop=True)


def assign_extra_splits(extra: pd.DataFrame, base: pd.DataFrame, seed: int = config.SEED) -> pd.Series:
    by_patient = base.dropna(subset=["patient_id"]).groupby("patient_id").split.first().to_dict()
    by_lesion = base.dropna(subset=["lesion_id"]).groupby("lesion_id").split.first().to_dict()
    inherited = [by_patient.get(p) or by_lesion.get(l) for p, l in zip(extra.patient_id, extra.lesion_id)]
    out = pd.Series(inherited, index=extra.index, dtype=object)
    # PAD-UFES-20 ist extern; ein Dermoskopie-Bild derselben Person darf nicht ins Training
    out = out.where(out != "external", "drop")
    free = out.isna()
    if free.any():
        sub = extra[free].copy()
        sub["group"] = assign_groups(sub.patient_id, sub.lesion_id)
        sub["domain"] = "dermoscopic"
        out[free] = split_groups(sub, seed=seed + 7).to_numpy()
    # innerhalb der Zusatzdaten: gleiche Gruppe -> gleicher Split (erster gewinnt)
    g = assign_groups(extra.patient_id, extra.lesion_id)
    first = pd.Series(out.to_numpy()).groupby(g).transform("first")
    return pd.Series(first.to_numpy(), index=extra.index)


def build_extra(raw_dir: Path = config.RAW_DIR, out_dir: Path = config.PROCESSED_DIR,
                size: int = config.STORE_SIZE, workers: int = 8) -> pd.DataFrame:
    meta = pd.read_parquet(raw_dir / "isic_meta" / "ISIC_metadata.parquet")
    base = pd.read_parquet(out_dir / "catalog.parquet")
    extra = select_extra(meta)
    extra = extra[~extra.isic_id.isin(base.isic_id)].reset_index(drop=True)
    extra["split"] = assign_extra_splits(extra, base)
    extra = extra[extra.split != "drop"].reset_index(drop=True)
    n = len(extra)
    path = out_dir / f"images_extra_{size}.u8"
    mm = np.memmap(path, dtype=np.uint8, mode="w+", shape=(n, size, size, 3))
    ok = np.zeros(n, dtype=bool)

    def one(i: int) -> tuple[int, bool]:
        url = f"{config.ISIC_BUCKET}/images/{extra.isic_id[i]}.jpg"
        for _ in range(4):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    data = r.read()
                mm[i] = decode(data, size)
                return i, True
            except Exception:  # noqa: BLE001
                continue
        return i, False

    with cf.ThreadPoolExecutor(workers) as ex:
        for k, fut in enumerate(cf.as_completed([ex.submit(one, i) for i in range(n)]), 1):
            i, good = fut.result()
            ok[i] = good
            if k % 2000 == 0:
                print(f"  {k}/{n}", flush=True)
    mm.flush()
    extra["mask_bits"] = [labels.mask_to_bits(labels.label_mask(a, b)) for a, b in zip(extra.diagnosis_1, extra.diagnosis_3)]
    extra["domain"] = "dermoscopic"
    extra["source"] = EXTRA_SOURCE
    extra["weight"] = 1.0
    extra["group"] = -1 - assign_groups(extra.patient_id, extra.lesion_id)  # negative IDs: eigener Namensraum
    extra["file"] = ""
    extra["member"] = ""
    extra["row"] = np.arange(n)
    extra["ok"] = ok
    cols = [c for c in base.columns if c in extra.columns]
    extra = extra[cols]
    extra.to_parquet(out_dir / "catalog_extra.parquet", index=False)
    (out_dir / "extra.ok").write_text(f"{int(ok.sum())}/{n}\n")
    return extra


if __name__ == "__main__":
    e = build_extra()
    print(e.groupby(["split", "group_label"]).size().unstack(fill_value=0))
    print("ok:", int(e.ok.sum()), "/", len(e))
