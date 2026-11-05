"""Einfache Bildqualitäts-Merkmale – identisch in Python und in der Web-App (web/src/lib/quality.js).

Gerechnet wird auf dem Modell-Eingang (S×S, RGB in [0,1]):
- Helligkeit: Mittelwert der Luminanz Y = 0.299 R + 0.587 G + 0.114 B
- Überbelichtung: Anteil der Pixel mit Y > 0.97
- Schärfe: Varianz des 4er-Laplace-Operators auf Y (nur innere Pixel)

Die Grenzwerte werden aus der Verteilung auf den Validierungsbildern abgeleitet.
"""

from __future__ import annotations

import numpy as np


def luminance(x: np.ndarray) -> np.ndarray:
    """x: [..., H, W, 3] in [0,1]."""
    return 0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2]


def quality_features(x: np.ndarray) -> dict[str, np.ndarray]:
    y = luminance(np.asarray(x, dtype=np.float64))
    lap = (y[..., :-2, 1:-1] + y[..., 2:, 1:-1] + y[..., 1:-1, :-2] + y[..., 1:-1, 2:]
           - 4 * y[..., 1:-1, 1:-1])
    return {
        "brightness": y.mean(axis=(-2, -1)),
        "overexposed": (y > 0.97).mean(axis=(-2, -1)),
        "sharpness": lap.var(axis=(-2, -1)),
    }


def derive_limits(feats: dict[str, np.ndarray]) -> dict[str, float]:
    return {
        "brightness_min": float(np.quantile(feats["brightness"], 0.005)),
        "brightness_max": float(np.quantile(feats["brightness"], 0.995)),
        "overexposed_max": float(max(0.05, np.quantile(feats["overexposed"], 0.995))),
        "sharpness_min": float(np.quantile(feats["sharpness"], 0.01)),
        "sharpness_median": float(np.median(feats["sharpness"])),
    }
