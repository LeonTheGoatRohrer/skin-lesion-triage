"""'Foto nicht beurteilbar': Abstand eines Bildes zu den Trainingsdaten im Merkmalsraum.

Wir passen eine PCA auf Embeddings der Trainingsbilder an und kombinieren
- den Mahalanobis-Abstand in den ersten k Hauptkomponenten (ungewöhnliche Kombination
  bekannter Merkmale) und
- den Rekonstruktionsfehler außerhalb dieser k Komponenten (Merkmale, die im Training nie
  vorkamen, z. B. eine Katze oder ein Stück Text).

Beide Teile sind so normiert, dass Trainingsbilder im Mittel ~1 liefern. Die Schwelle ist das
99. Perzentil auf dem Validierungs-Split: ~1 % normaler Bilder werden fälschlich abgewiesen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class OODModel:
    mean: np.ndarray        # (D,)
    components: np.ndarray  # (k, D)
    variances: np.ndarray   # (k,)
    residual_var: float     # mittlere quadrierte Restnorm auf Trainingsdaten
    threshold: float = float("inf")

    def score(self, emb: np.ndarray) -> np.ndarray:
        x = np.asarray(emb, dtype=np.float64) - self.mean
        z = x @ self.components.T
        maha = (z**2 / self.variances).mean(axis=1)
        resid = ((x**2).sum(axis=1) - (z**2).sum(axis=1)) / self.residual_var
        return 0.5 * (maha + resid)

    def to_dict(self) -> dict:
        return {"k": int(len(self.variances)), "threshold": float(self.threshold),
                "residual_var": float(self.residual_var)}


def fit_ood(train_emb: np.ndarray, k: int = 32) -> OODModel:
    x = np.asarray(train_emb, dtype=np.float64)
    mean = x.mean(axis=0)
    xc = x - mean
    _, sv, vt = np.linalg.svd(xc, full_matrices=False)
    comps = vt[:k]
    var = (sv[:k] ** 2) / (len(x) - 1)
    z = xc @ comps.T
    resid = ((xc**2).sum(axis=1) - (z**2).sum(axis=1)).mean()
    return OODModel(mean, comps, var, float(resid))


def calibrate_threshold(model: OODModel, val_emb: np.ndarray, quantile: float = 0.99) -> OODModel:
    model.threshold = float(np.quantile(model.score(val_emb), quantile))
    return model
