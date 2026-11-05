"""Kennzahlen für einen binären Triage-Score (höher = auffälliger).

Alle Funktionen akzeptieren Stichprobengewichte: SLICE-3D-Gutartige sind unterabgetastet und
tragen Gewicht 1/p, damit Spezifität, Prävalenz und Kalibrierung unverzerrt bleiben.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve


def _w(y, w):
    return np.ones(len(y)) if w is None else np.asarray(w, dtype=float)


def auroc(y, s, w=None) -> float:
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, s, sample_weight=w))


def roc(y, s, w=None):
    fpr, tpr, thr = roc_curve(y, s, sample_weight=w, drop_intermediate=True)
    return fpr, tpr, thr


def pauc_above_tpr(y, s, w=None, min_tpr: float = 0.8) -> float:
    """Fläche unter der ROC-Kurve oberhalb von TPR=min_tpr (Metrik der ISIC-2024-Challenge).

    Wertebereich [0, 1-min_tpr]; zufällig ≈ (1-min_tpr)²/2, perfekt = 1-min_tpr.
    """
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return float("nan")
    # wie im offiziellen ISIC-2024-Code: Labels und Scores umdrehen, dann sklearn mit max_fpr
    # (McClish-standardisiert) und zurückrechnen auf die nicht standardisierte Fläche
    max_fpr = 1 - min_tpr
    scaled = roc_auc_score(1 - y, -np.asarray(s), sample_weight=w, max_fpr=max_fpr)
    return float(0.5 * max_fpr**2 + (max_fpr - 0.5 * max_fpr**2) / 0.5 * (scaled - 0.5))


def threshold_at_sensitivity(y, s, w, target: float) -> float:
    """Größte Schwelle, bei der Sensitivität (Score >= t) noch >= target ist."""
    y, s, w = np.asarray(y), np.asarray(s), _w(y, w)
    pos = np.sort(s[y == 1])[::-1]
    pw = w[y == 1][np.argsort(s[y == 1])[::-1]]
    cum = np.cumsum(pw) / pw.sum()
    k = int(np.searchsorted(cum, target - 1e-12))
    return float(pos[min(k, len(pos) - 1)])


def threshold_at_specificity(y, s, w, target: float) -> float:
    """Kleinste Schwelle, bei der Spezifität (Score < t) >= target ist."""
    y, s, w = np.asarray(y), np.asarray(s), _w(y, w)
    order = np.argsort(s[y == 0])
    neg = s[y == 0][order]
    nw = w[y == 0][order]
    cum = np.cumsum(nw) / nw.sum()
    k = int(np.searchsorted(cum, target - 1e-12))
    k = min(k, len(neg) - 1)
    return float(np.nextafter(neg[k], np.inf))


def sens_spec(y, s, w, t: float) -> tuple[float, float]:
    y, s, w = np.asarray(y), np.asarray(s), _w(y, w)
    flag = s >= t
    sens = (w * (flag & (y == 1))).sum() / max(w[y == 1].sum(), 1e-12)
    spec = (w * (~flag & (y == 0))).sum() / max(w[y == 0].sum(), 1e-12)
    return float(sens), float(spec)


def calibration(y, p, w=None, n_bins: int = 10) -> dict:
    """Reliability-Bins (gleich viele Gewichte je Bin), ECE und Brier-Score."""
    y, p, w = np.asarray(y, float), np.asarray(p, float), _w(y, w)
    order = np.argsort(p)
    cw = np.cumsum(w[order]) / w.sum()
    bins = np.minimum((cw * n_bins).astype(int), n_bins - 1)
    out, ece = [], 0.0
    for b in range(n_bins):
        sel = order[bins == b]
        if len(sel) == 0:
            continue
        ws = w[sel].sum()
        mp, my = float((w[sel] * p[sel]).sum() / ws), float((w[sel] * y[sel]).sum() / ws)
        out.append({"mean_pred": mp, "frac_pos": my, "weight": float(ws / w.sum())})
        ece += ws / w.sum() * abs(mp - my)
    brier = float((w * (p - y) ** 2).sum() / w.sum())
    return {"bins": out, "ece": float(ece), "brier": brier}


def bootstrap_ci(fn, y, s, w, groups, n_boot: int = 500, seed: int = 0, alpha: float = 0.05):
    """Konfidenzintervall durch Ziehen ganzer Gruppen (Patienten/Läsionen) mit Zurücklegen."""
    y, s, w, groups = map(np.asarray, (y, s, _w(y, w), groups))
    rng = np.random.default_rng(seed)
    ug, inv = np.unique(groups, return_inverse=True)
    members = [np.flatnonzero(inv == g) for g in range(len(ug))]
    vals = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(ug), len(ug))
        idx = np.concatenate([members[g] for g in pick])
        if len(np.unique(y[idx])) < 2:
            continue
        vals.append(fn(y[idx], s[idx], w[idx]))
    if not vals:
        return float("nan"), float("nan")
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)
