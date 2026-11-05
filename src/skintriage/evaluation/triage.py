"""Vom Score zur Ampel – und zu einer ehrlichen Prozentzahl.

Warum keine "Krebs-Wahrscheinlichkeit"? Ein kalibrierter Wert hängt von der Prävalenz ab:
In MILK10k sind ~70 % der Fotos bösartig, unter allen Muttermalen, die Menschen im Alltag
fotografieren, ist es ein winziger Bruchteil. Dieselbe Zahl wäre je nach Publikum falsch.

Stattdessen:
- **Auffälligkeit (Perzentil):** Anteil gutartiger Referenz-Hautstellen (Val-Split) mit
  niedrigerem Score. "Auffälliger als 93 % der gutartigen Hautstellen" bleibt bei jeder
  Prävalenz richtig.
- **Ampel:** zwei Schwellen, nur auf dem Validierungs-Split festgelegt:
  - ``t_low``: Sensitivität 95 % – höchstens ~5 % der bösartigen Hautstellen landen in Grün.
  - ``t_high``: Spezifität 90 % – höchstens ~10 % der gutartigen landen in Rot.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from skintriage.evaluation import metrics

ZONES = ("green", "yellow", "red")


@dataclass
class TriageRule:
    t_low: float
    t_high: float
    target_sensitivity: float
    target_specificity: float
    reference_benign: list[float]  # sortierte Scores gutartiger Referenzbilder

    def zone(self, s: np.ndarray) -> np.ndarray:
        s = np.asarray(s)
        return np.where(s >= self.t_high, 2, np.where(s >= self.t_low, 1, 0))

    def percentile(self, s: np.ndarray) -> np.ndarray:
        ref = np.asarray(self.reference_benign)
        return np.searchsorted(ref, np.asarray(s), side="right") / len(ref)

    def to_dict(self) -> dict:
        return asdict(self)


def fit_rule(y: np.ndarray, s: np.ndarray, w: np.ndarray | None = None,
             sensitivity: float = 0.95, specificity: float = 0.90) -> TriageRule:
    y, s = np.asarray(y), np.asarray(s)
    t_low = metrics.threshold_at_sensitivity(y, s, w, sensitivity)
    t_high = metrics.threshold_at_specificity(y, s, w, specificity)
    t_high = max(t_high, t_low)  # schwaches Modell: Gelb-Zone kann verschwinden, nie negativ werden
    ref = np.sort(s[y == 0]).astype(float).tolist()
    return TriageRule(float(t_low), float(t_high), sensitivity, specificity, ref)


def zone_table(rule: TriageRule, y: np.ndarray, s: np.ndarray, w: np.ndarray | None = None) -> dict:
    """Anteil je Ampelfarbe, getrennt nach Klasse (0 gutartig, 1 bösartig, 2 Vorstufe)."""
    y, s = np.asarray(y), np.asarray(s)
    w = np.ones(len(y)) if w is None else np.asarray(w, float)
    z = rule.zone(s)
    out = {}
    for cls, name in ((0, "benign"), (1, "malignant"), (2, "precursor")):
        m = y == cls
        if m.sum() == 0:
            continue
        tot = w[m].sum()
        out[name] = {"n": int(m.sum()), **{ZONES[k]: float(w[m & (z == k)].sum() / tot) for k in range(3)}}
    return out
