"""Bildmodell: vortrainiertes CNN (timm) + linearer Kopf über 7 Diagnose-Gruppen.

Vortrainierte ImageNet-Gewichte kommen aus den GitHub-Releases von timm (Hugging Face und
download.pytorch.org sind in der Entwicklungsumgebung gesperrt).
"""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn

from skintriage import config, labels

_REL = "https://github.com/huggingface/pytorch-image-models/releases/download/v0.1-weights/"
PRETRAINED_URLS = {
    "mobilenetv3_large_100": _REL + "mobilenetv3_large_100_ra-f55367f5.pth",
    "efficientnet_b0": _REL + "efficientnet_b0_ra-3dd342df.pth",
}


def load_pretrained(model: nn.Module, name: str, cache_dir: Path = config.ARTIFACTS_DIR / "weights") -> None:
    url = PRETRAINED_URLS[name]
    path = cache_dir / Path(url).name
    if not path.exists():
        from skintriage.data.download import fetch

        fetch(url, path)
    sd = torch.load(path, map_location="cpu", weights_only=True)
    sd = {k: v for k, v in sd.items() if not k.startswith(("classifier.", "fc.", "head."))}
    missing, unexpected = model.load_state_dict(sd, strict=False)
    if unexpected or [m for m in missing if not m.startswith("classifier")]:
        raise RuntimeError(f"Gewichte passen nicht: missing={missing[:5]} unexpected={unexpected[:5]}")


class TriageNet(nn.Module):
    """Gibt (logits[B,7], embedding[B,D]) zurück."""

    def __init__(self, backbone: str = "mobilenetv3_large_100", n_classes: int = labels.N_GROUPS,
                 drop_rate: float = 0.2, drop_path_rate: float = 0.05, pretrained: bool = True):
        super().__init__()
        import timm

        self.backbone_name = backbone
        self.backbone = timm.create_model(backbone, pretrained=False, num_classes=0,
                                          drop_rate=0.0, drop_path_rate=drop_path_rate)
        if pretrained:
            load_pretrained(self.backbone, backbone)
        # MobileNetV3 hat nach dem Pooling noch eine 1x1-Schicht (960 -> 1280)
        self.feat_dim = getattr(self.backbone, "head_hidden_size", None) or self.backbone.num_features
        self.dropout = nn.Dropout(drop_rate)
        self.head = nn.Linear(self.feat_dim, n_classes)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        f = self.backbone(x)
        return self.head(self.dropout(f)), f


def malignant_logit(logits: torch.Tensor) -> torch.Tensor:
    """log P(bösartig) - log P(nicht bösartig) aus den Gruppen-Logits (Triage-Score)."""
    mal = list(labels.MALIGNANT)
    rest = [i for i in range(logits.shape[-1]) if i not in labels.MALIGNANT]
    return torch.logsumexp(logits[..., mal], -1) - torch.logsumexp(logits[..., rest], -1)
