"""Downloads aus dem öffentlichen ISIC-S3-Bucket und dem SCIN-Bucket (Google Cloud Storage).

Alle Dateien landen unter ``data/raw/``. Bereits vorhandene Dateien werden übersprungen; jede
Datei wird zuerst in eine ``.part``-Datei geschrieben und erst danach umbenannt, damit
abgebrochene Downloads nicht als fertig gelten.
"""

from __future__ import annotations

import concurrent.futures as cf
import os
import shutil
import time
import urllib.request
from pathlib import Path

import pandas as pd

from skintriage import config

BULK_FILES = {
    "isic_meta": ["snapshots/ISIC_metadata.parquet"],
    "milk10k": [
        "challenges/milk10k/MILK10k_Training_Input.zip",
        "challenges/milk10k/MILK10k_Training_Metadata.csv",
        "challenges/milk10k/MILK10k_Training_GroundTruth.csv",
        "challenges/milk10k/MILK10k_Training_Supplement.csv",
    ],
    "isic2024": [
        "challenges/2024/ISIC_2024_Training_Input.zip",
        "challenges/2024/ISIC_2024_Training_GroundTruth.csv",
        "challenges/2024/ISIC_2024_Training_Supplement.csv",
    ],
}

# Klinische Nahaufnahmen, die nicht in MILK10k enthalten sind, werden einzeln geladen
# (u. a. PAD-UFES-20 = echte Smartphone-Fotos, unser externer Test).
SINGLE_IMAGE_ATTRIBUTIONS = (
    "Federal University of Espírito Santo (UFES)",
    "Memorial Sloan Kettering Cancer Center",
    "Anonymous",
    "Hospital Italiano de Buenos Aires",
)


class DataUnavailableError(RuntimeError):
    pass


def fetch(url: str, dest: Path, retries: int = 4, timeout: float = 120.0) -> Path:
    """Lädt ``url`` nach ``dest`` (überspringt vorhandene Dateien)."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    delay = 2.0
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp, open(part, "wb") as fh:
                shutil.copyfileobj(resp, fh, length=1 << 20)
            os.replace(part, dest)
            return dest
        except Exception as exc:  # noqa: BLE001 - Netzwerkfehler aller Art
            part.unlink(missing_ok=True)
            if attempt == retries:
                raise DataUnavailableError(f"{url}: {exc}") from exc
            time.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")


def download_bulk(raw_dir: Path = config.RAW_DIR) -> list[Path]:
    out = []
    for folder, keys in BULK_FILES.items():
        for key in keys:
            dest = raw_dir / folder / Path(key).name
            print(f"  {key} -> {dest}", flush=True)
            out.append(fetch(f"{config.ISIC_BUCKET}/{key}", dest))
    return out


def single_image_ids(meta: pd.DataFrame) -> list[str]:
    sel = meta[(meta.image_type == "clinical: close-up") & meta.attribution.isin(SINGLE_IMAGE_ATTRIBUTIONS)]
    return sorted(sel.isic_id)


def download_single_images(raw_dir: Path = config.RAW_DIR, workers: int = 24) -> int:
    meta = pd.read_parquet(raw_dir / "isic_meta" / "ISIC_metadata.parquet",
                           columns=["isic_id", "image_type", "attribution"])
    ids = single_image_ids(meta)
    target = raw_dir / "archive_images"
    todo = [i for i in ids if not (target / f"{i}.jpg").exists()]
    print(f"  {len(ids)} Einzelbilder, davon {len(todo)} noch zu laden", flush=True)

    def one(isic_id: str):
        return fetch(f"{config.ISIC_BUCKET}/images/{isic_id}.jpg", target / f"{isic_id}.jpg")

    failed = 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for n, fut in enumerate(cf.as_completed([ex.submit(one, i) for i in todo]), 1):
            try:
                fut.result()
            except DataUnavailableError as exc:
                failed += 1
                print(f"  WARNUNG: {exc}", flush=True)
            if n % 500 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
    if failed:
        print(f"  {failed} Bilder fehlgeschlagen", flush=True)
    return len(ids) - failed


# --- SCIN (Google, crowdsourced Handyfotos aus den USA) -----------------------------------
# Nur als Realitätscheck für "nicht beurteilbar": überwiegend Ausschläge, kaum Hautkrebs.
SCIN_FILES = ("dataset/scin_cases.csv", "dataset/scin_labels.csv")


def download_scin(raw_dir: Path = config.RAW_DIR, n_images: int = 600, workers: int = 16) -> int:
    folder = raw_dir / "scin"
    for key in SCIN_FILES:
        fetch(f"{config.SCIN_BUCKET}/{key}", folder / Path(key).name)
    cases = pd.read_csv(folder / "scin_cases.csv")
    close = cases[cases.image_1_shot_type == "CLOSE_UP"].sample(frac=1.0, random_state=config.SEED)
    paths = list(close.image_1_path.head(n_images))

    def one(p: str):
        return fetch(f"{config.SCIN_BUCKET}/{p}", folder / "images" / Path(p).name)

    with cf.ThreadPoolExecutor(workers) as ex:
        ok = sum(1 for f in [ex.submit(one, p) for p in paths] if f.exception() is None)
    print(f"  SCIN: {ok}/{len(paths)} Nahaufnahmen", flush=True)
    return ok
