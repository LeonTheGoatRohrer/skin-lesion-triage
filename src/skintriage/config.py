"""Zentrale Pfade und Konstanten.

Alle Pfade sind relativ zum Repo-Root und lassen sich über die Umgebungsvariable
``SKINTRIAGE_ROOT`` umlenken (nützlich für Tests).
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("SKINTRIAGE_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = ROOT / "artifacts"
WEB_PUBLIC = ROOT / "web" / "public"
WEB_DATA = WEB_PUBLIC / "data"
WEB_MODEL = WEB_PUBLIC / "model"

ISIC_BUCKET = "https://isic-archive.s3.amazonaws.com"
SCIN_BUCKET = "https://storage.googleapis.com/dx-scin-public-data"

# Gespeicherte Bildgröße (quadratisch). Trainiert/inferiert wird auf IMAGE_SIZE.
STORE_SIZE = 160
IMAGE_SIZE = 128

# ImageNet-Normalisierung (die Backbones sind auf ImageNet vortrainiert)
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)

SEED = 20261105

# Domänen: wie wurde das Bild aufgenommen?
DOMAINS = ("clinical", "tbp", "dermoscopic")
DOMAIN_LABELS_DE = {
    "clinical": "Kamerafoto aus der Nähe",
    "tbp": "Ausschnitt aus 3D-Ganzkörperfoto",
    "dermoscopic": "Dermoskopie (Auflichtmikroskop)",
}

# Anteil der Gruppen (Patienten/Läsionen) für Validierung und internen Test
VAL_FRACTION = 0.15
TEST_FRACTION = 0.15

# SLICE-3D (ISIC 2024) hat ~400 000 gutartige Ausschnitte. Für Training und Auswertung
# reicht eine Zufallsstichprobe; jedes Bild trägt ein Gewicht = 1 / Ziehungswahrscheinlichkeit,
# damit Prävalenz und Kalibrierung trotzdem korrekt geschätzt werden.
TBP_BENIGN_SAMPLE = {"train": 40_000, "val": 12_000, "test": 20_000}

# PAD-UFES-20 (echte Smartphone-Fotos, Brasilien) bleibt komplett draußen: externer Test.
EXTERNAL_SOURCES = {"pad_ufes_20"}
