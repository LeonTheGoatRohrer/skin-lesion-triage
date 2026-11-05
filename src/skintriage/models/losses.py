"""Verlust für Mengen-Labels (partielle Annotation).

Ist für ein Bild nur bekannt, dass es *irgendeine* gutartige Veränderung ist, maximieren wir
P(NEV) + P(BKL) + P(OTHER) statt eine einzelne Klasse zu erzwingen:

    L = logsumexp(z) - logsumexp(z[S])     (S = erlaubte Gruppen)

Für ein vollständig annotiertes Bild ist das genau die Kreuzentropie.
"""

from __future__ import annotations

import torch


def set_nll(logits: torch.Tensor, mask: torch.Tensor, smoothing: float = 0.0) -> torch.Tensor:
    """Mittlerer Verlust; ``mask`` ist bool [B, C] mit mindestens einem True je Zeile."""
    if not bool(mask.any(dim=1).all()):
        raise ValueError("Jede Zeile braucht mindestens eine erlaubte Gruppe")
    full = torch.logsumexp(logits, dim=1)
    inside = torch.logsumexp(logits.masked_fill(~mask, float("-inf")), dim=1)
    loss = full - inside
    if smoothing > 0:
        # etwas Wahrscheinlichkeitsmasse gleichmäßig auf alle Gruppen (gegen Überkonfidenz)
        uniform = full - logits.mean(dim=1)
        loss = (1 - smoothing) * loss + smoothing * uniform
    return loss.mean()
