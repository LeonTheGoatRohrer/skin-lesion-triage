#!/usr/bin/env python
"""Beispielbilder für die Web-App aus PAD-UFES-20 (CC BY 4.0, echte Smartphone-Fotos).

Je Diagnose wird *zufällig* (fester Seed) ein Bild gezogen – keine Auswahl nach Modellergebnis.
PAD-UFES-20 ist der externe Testdatensatz; die Bilder waren nie im Training.

Aufruf: python scripts/make_examples.py
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from PIL import Image, ImageOps

from skintriage import config

PICKS = [  # (diagnosis_3, de, en)
    ("Nevus", "Muttermal (Nävus), gutartig", "Nevus (mole), benign"),
    ("Seborrheic keratosis", "Seborrhoische Keratose (Alterswarze), gutartig", "Seborrheic keratosis, benign"),
    ("Basal cell carcinoma", "Basalzellkarzinom (weißer Hautkrebs)", "Basal cell carcinoma"),
    ("Melanoma, NOS", "Melanom (schwarzer Hautkrebs)", "Melanoma"),
]
CONFIRM = {"histopathology": ("histologisch gesichert", "confirmed by histopathology"),
           "single contributor clinical assessment": ("klinische Einschätzung", "clinical assessment"),
           "single image expert consensus": ("Konsens von Fachleuten anhand des Bildes", "expert consensus from the image")}


def main() -> None:
    meta = pd.read_parquet(config.RAW_DIR / "isic_meta" / "ISIC_metadata.parquet")
    pad = meta[(meta.attribution == "Federal University of Espírito Santo (UFES)")
               & (meta.image_type == "clinical: close-up")]
    out_dir = config.WEB_PUBLIC / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(config.SEED)
    items = []
    for diag, de, en in PICKS:
        pool = pad[pad.diagnosis_3 == diag].sort_values("isic_id")
        row = pool.iloc[int(rng.integers(len(pool)))]
        img = ImageOps.exif_transpose(Image.open(config.RAW_DIR / "archive_images" / f"{row.isic_id}.jpg")).convert("RGB")
        img.thumbnail((640, 640), Image.Resampling.LANCZOS)
        fname = f"{row.isic_id}.jpg"
        img.save(out_dir / fname, quality=88)
        conf = CONFIRM.get(row.diagnosis_confirm_type, (str(row.diagnosis_confirm_type), str(row.diagnosis_confirm_type)))
        items.append({"file": fname, "isic_id": row.isic_id, "de": de, "en": en, "confirm": conf[0],
                      "confirm_en": conf[1], "attribution": row.attribution, "license": row.copyright_license,
                      "crop": 0})
        print(f"  {fname}: {diag} ({row.copyright_license})")
    (out_dir / "examples.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
