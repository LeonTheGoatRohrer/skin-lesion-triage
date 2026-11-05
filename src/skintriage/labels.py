"""Diagnose-Gruppen und Mengen-Labels.

Das Modell sagt eine Verteilung über 7 Diagnose-Gruppen voraus. Nicht jedes Bild ist so fein
annotiert: Viele SLICE-3D-Bilder sind nur als "Benign" markiert. Solche Bilder bekommen ein
*Mengen-Label* (z. B. {NEV, BKL, OTHER}); der Verlust maximiert dann die Summe der
Wahrscheinlichkeiten innerhalb der Menge (siehe ``models.losses``).
"""

from __future__ import annotations

import math

import numpy as np

GROUPS = ("MEL", "BCC", "SCC", "AK", "NEV", "BKL", "OTHER")
N_GROUPS = len(GROUPS)
MALIGNANT = (0, 1, 2)
PRECURSOR = (3,)
BENIGN = (4, 5, 6)

GROUP_NAMES_DE = {
    "MEL": "Melanom (schwarzer Hautkrebs)",
    "BCC": "Basalzellkarzinom (weißer Hautkrebs)",
    "SCC": "Plattenepithelkarzinom (weißer Hautkrebs)",
    "AK": "Aktinische Keratose (Krebsvorstufe)",
    "NEV": "Muttermal (Nävus)",
    "BKL": "Gutartige Keratose / Altersfleck",
    "OTHER": "Andere gutartige Hautveränderung",
}
GROUP_NAMES_EN = {
    "MEL": "Melanoma",
    "BCC": "Basal cell carcinoma",
    "SCC": "Squamous cell carcinoma",
    "AK": "Actinic keratosis (precancer)",
    "NEV": "Nevus (mole)",
    "BKL": "Benign keratosis / age spot",
    "OTHER": "Other benign lesion",
}

# binäres Label für die Auswertung
BIN_BENIGN, BIN_MALIGNANT, BIN_PRECURSOR, BIN_UNKNOWN = 0, 1, 2, -1

_BKL = ("seborrheic keratosis", "solar lentigo", "lichen planus like keratosis", "ink-spot lentigo",
        "clear cell acanthoma", "lentigo")


def _clean(x) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and math.isnan(x):
        return ""
    return str(x).strip()


def group_from_diagnosis(diag1, diag3) -> int | None:
    """Feine Gruppe (Index in GROUPS) oder None, wenn nur die Grobklasse bekannt ist."""
    d1 = _clean(diag1).lower()
    d3 = _clean(diag3).lower()
    if not d3:
        return None
    if "melanoma" in d3:
        return 0
    if "basal cell carcinoma" in d3:
        return 1
    if "squamous cell carcinoma" in d3 or "keratoacanthoma" in d3:
        return 2
    if "actinic keratosis" in d3:
        return 3
    if d1 == "malignant" or d1 == "indeterminate":
        return None  # z. B. Merkelzellkarzinom oder atypische melanozytäre Neoplasie
    if d3 == "nevus" or d3.startswith("nevus"):
        return 4
    if any(d3.startswith(k) for k in _BKL):
        return 5
    if d1 == "benign":
        return 6
    return None


def label_mask(diag1, diag3) -> np.ndarray | None:
    """Erlaubte Gruppen als bool-Maske (7,) oder None, wenn das Bild nicht trainierbar ist."""
    g = group_from_diagnosis(diag1, diag3)
    m = np.zeros(N_GROUPS, dtype=bool)
    if g is not None:
        m[g] = True
        return m
    d1 = _clean(diag1).lower()
    if d1 == "malignant":
        m[list(MALIGNANT)] = True
        return m
    if d1 == "benign":
        m[list(BENIGN)] = True
        return m
    return None  # Indeterminate ohne AK oder unbekannt -> nicht trainieren


def binary_label(diag1, diag3) -> int:
    """1 = bösartig, 0 = gutartig, 2 = Krebsvorstufe (AK), -1 = unklar."""
    g = group_from_diagnosis(diag1, diag3)
    if g in MALIGNANT:
        return BIN_MALIGNANT
    if g in PRECURSOR:
        return BIN_PRECURSOR
    d1 = _clean(diag1).lower()
    if d1 == "malignant":
        return BIN_MALIGNANT
    if d1 == "benign":
        return BIN_BENIGN
    return BIN_UNKNOWN


def mask_to_bits(m: np.ndarray) -> int:
    return int(sum(1 << i for i, v in enumerate(m) if v))


def bits_to_mask(bits: int) -> np.ndarray:
    return np.array([(bits >> i) & 1 for i in range(N_GROUPS)], dtype=bool)
