"""Bilder einmalig dekodieren, quadratisch zuschneiden, verkleinern und als uint8-Memmap ablegen.

Ergebnis (unter ``data/processed/``):
- ``images_{S}.u8``  – Array (N, S, S, 3), uint8, Zeile i gehört zu Katalog-Zeile i
- ``catalog.parquet`` – Katalog inkl. Spalte ``row``

Das Training liest danach nur noch zusammenhängenden Speicher statt 86 000 JPEGs.
"""

from __future__ import annotations

import io
import multiprocessing as mp
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageOps

from skintriage import config


def square_resize(img: Image.Image, size: int) -> np.ndarray:
    """Mittiges Quadrat (kürzere Seite) -> size x size, RGB uint8."""
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    s = min(w, h)
    left, top = (w - s) // 2, (h - s) // 2
    img = img.crop((left, top, left + s, top + s))
    img = img.resize((size, size), Image.Resampling.BICUBIC, reducing_gap=3.0)
    return np.asarray(img, dtype=np.uint8)


def decode(data: bytes, size: int) -> np.ndarray:
    img = Image.open(io.BytesIO(data))
    if img.format == "JPEG":
        img.draft("RGB", (size * 2, size * 2))  # schnelles Herunterskalieren beim Dekodieren
    return square_resize(img, size)


_zips: dict[str, zipfile.ZipFile] = {}
_out: np.memmap | None = None


def _init(out_path: str, n: int, size: int) -> None:
    global _out
    _out = np.memmap(out_path, dtype=np.uint8, mode="r+", shape=(n, size, size, 3))


def _read(file: str, member: str) -> bytes:
    if member:
        z = _zips.get(file)
        if z is None:
            z = _zips[file] = zipfile.ZipFile(file)
        return z.read(member)
    return Path(file).read_bytes()


def _work(args) -> tuple[int, bool]:
    i, file, member, size = args
    try:
        _out[i] = decode(_read(file, member), size)
        return i, True
    except Exception:  # noqa: BLE001 - defekte Datei -> als fehlend markieren
        return i, False


def build_memmap(df: pd.DataFrame, out_path: Path, size: int = config.STORE_SIZE,
                 workers: int = 4) -> np.ndarray:
    """Schreibt alle Bilder aus ``df`` (Spalten file, member) nach ``out_path``. Gibt ok-Maske zurück."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = len(df)
    np.memmap(out_path, dtype=np.uint8, mode="w+", shape=(n, size, size, 3)).flush()
    jobs = [(i, f, m, size) for i, (f, m) in enumerate(zip(df.file, df.member))]
    # nach Datei sortieren: Zip-Zugriffe bleiben lokal
    jobs.sort(key=lambda j: (j[1], j[2]))
    ok = np.zeros(n, dtype=bool)
    with mp.get_context("fork").Pool(workers, initializer=_init, initargs=(str(out_path), n, size)) as pool:
        for k, (i, good) in enumerate(pool.imap_unordered(_work, jobs, chunksize=256), 1):
            ok[i] = good
            if k % 10000 == 0:
                print(f"  {k}/{n}", flush=True)
    return ok


def open_images(path: Path, n: int, size: int = config.STORE_SIZE) -> np.memmap:
    return np.memmap(path, dtype=np.uint8, mode="r", shape=(n, size, size, 3))


def preprocess_all(raw_dir: Path = config.RAW_DIR, out_dir: Path = config.PROCESSED_DIR,
                   size: int = config.STORE_SIZE) -> pd.DataFrame:
    from skintriage.data.catalog import build_catalog

    cat = build_catalog(raw_dir)
    present = np.array([Path(f).exists() for f in cat.file])
    if (~present).any():
        print(f"  WARNUNG: {int((~present).sum())} Bilder fehlen auf der Platte und werden ausgelassen")
    cat = cat[present].reset_index(drop=True)
    ok = build_memmap(cat, out_dir / f"images_{size}.u8", size)
    cat["row"] = np.arange(len(cat))
    cat["ok"] = ok
    if (~ok).any():
        print(f"  WARNUNG: {int((~ok).sum())} Bilder nicht dekodierbar (ok=False)")
    cat.to_parquet(out_dir / "catalog.parquet", index=False)
    return cat


def preprocess_scin(raw_dir: Path = config.RAW_DIR, out_dir: Path = config.PROCESSED_DIR,
                    size: int = config.STORE_SIZE) -> pd.DataFrame:
    """SCIN-Nahaufnahmen (nur für die Analyse 'nicht beurteilbar')."""
    import ast

    folder = raw_dir / "scin"
    cases = pd.read_csv(folder / "scin_cases.csv")
    lab = pd.read_csv(folder / "scin_labels.csv")
    cases = cases.merge(lab[["case_id", "weighted_skin_condition_label"]], on="case_id", how="left")
    cases["file"] = [str(folder / "images" / Path(p).name) for p in cases.image_1_path]
    cases = cases[[Path(f).exists() for f in cases.file]].reset_index(drop=True)

    def top(v):
        d = ast.literal_eval(v) if isinstance(v, str) else {}
        return max(d, key=d.get) if d else ""

    cases["top_condition"] = cases.weighted_skin_condition_label.map(top)
    cases["member"] = ""
    ok = build_memmap(cases, out_dir / f"scin_{size}.u8", size)
    cases["row"] = np.arange(len(cases))
    cases["ok"] = ok
    cols = ["case_id", "top_condition", "fitzpatrick_skin_type", "image_1_shot_type", "row", "ok"]
    cases[cols].to_parquet(out_dir / "scin.parquet", index=False)
    return cases[cols]
