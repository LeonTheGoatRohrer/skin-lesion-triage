"""Batch-Augmentierung direkt auf Tensoren (schnell auf der CPU, kein Worker-Pool nötig).

Ziel ist, Klinik- und Scanner-Bilder wie Handyfotos aussehen zu lassen: beliebige Drehung,
Zoom/Verschiebung, Weißabgleich- und Belichtungsfehler, Unschärfe, Rauschen und geringe
Auflösung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn.functional as F

from skintriage import config


@dataclass
class AugConfig:
    rotate: bool = True
    scale: tuple[float, float] = (0.85, 1.35)  # >1 = hineinzoomen
    translate: float = 0.08
    brightness: float = 0.25
    contrast: float = 0.25
    saturation: float = 0.3
    hue: float = 0.04
    wb: float = 0.08            # Weißabgleich: Kanalfaktoren 1 ± wb
    gamma: float = 0.2
    p_blur: float = 0.3
    max_blur_sigma: float = 1.6
    p_lowres: float = 0.25
    p_noise: float = 0.3
    noise_std: float = 0.03


def _affine_grid(b: int, size: int, cfg: AugConfig, g: torch.Generator) -> torch.Tensor:
    ang = torch.rand(b, generator=g) * 2 * math.pi if cfg.rotate else torch.zeros(b)
    lo, hi = cfg.scale
    zoom = torch.exp(torch.empty(b).uniform_(math.log(lo), math.log(hi), generator=g))
    flip = torch.where(torch.rand(b, generator=g) < 0.5, -1.0, 1.0)
    tx, ty = (torch.rand(2, b, generator=g) * 2 - 1) * cfg.translate
    cos, sin = torch.cos(ang) / zoom, torch.sin(ang) / zoom
    theta = torch.stack([torch.stack([cos * flip, -sin, tx], 1),
                         torch.stack([sin * flip, cos, ty], 1)], 1)
    return F.affine_grid(theta, (b, 3, size, size), align_corners=False)


def _gaussian_blur(x: torch.Tensor, sigma: float) -> torch.Tensor:
    r = max(1, int(math.ceil(2 * sigma)))
    t = torch.arange(-r, r + 1, dtype=x.dtype)
    k = torch.exp(-0.5 * (t / sigma) ** 2)
    k = (k / k.sum()).to(x.device)
    c = x.shape[1]
    x = F.conv2d(F.pad(x, (r, r, 0, 0), mode="reflect"), k.view(1, 1, 1, -1).repeat(c, 1, 1, 1), groups=c)
    x = F.conv2d(F.pad(x, (0, 0, r, r), mode="reflect"), k.view(1, 1, -1, 1).repeat(c, 1, 1, 1), groups=c)
    return x


def augment(batch_u8: torch.Tensor, out_size: int, cfg: AugConfig, g: torch.Generator) -> torch.Tensor:
    """uint8 [B,H,W,3] -> float [B,3,out,out] in [0,1] (noch nicht normalisiert)."""
    x = batch_u8.permute(0, 3, 1, 2).float() / 255.0
    b = x.shape[0]
    x = F.grid_sample(x, _affine_grid(b, out_size, cfg, g), mode="bilinear",
                      padding_mode="reflection", align_corners=False)

    def u(s):  # gleichverteilt in [1-s, 1+s], Form [B,1,1,1]
        return (1 + (torch.rand(b, 1, 1, 1, generator=g) * 2 - 1) * s)

    x = x * torch.stack([u(cfg.wb) for _ in range(3)], 1).view(b, 3, 1, 1)  # Weißabgleich je Kanal
    gray = (0.299 * x[:, 0] + 0.587 * x[:, 1] + 0.114 * x[:, 2]).unsqueeze(1)
    x = gray + (x - gray) * u(cfg.saturation)
    mean = gray.mean(dim=(2, 3), keepdim=True)
    x = mean + (x - mean) * u(cfg.contrast)
    x = x * u(cfg.brightness)
    if cfg.hue > 0:  # Farbton als kleine Rotation im YIQ-Raum
        h = (torch.rand(b, generator=g) * 2 - 1) * cfg.hue * 2 * math.pi
        yiq = torch.tensor([[0.299, 0.587, 0.114], [0.596, -0.274, -0.322], [0.211, -0.523, 0.312]])
        rgb = torch.linalg.inv(yiq)
        c, s = torch.cos(h), torch.sin(h)
        rot = torch.zeros(b, 3, 3)
        rot[:, 0, 0] = 1
        rot[:, 1, 1], rot[:, 1, 2], rot[:, 2, 1], rot[:, 2, 2] = c, -s, s, c
        m = rgb @ rot @ yiq
        x = torch.einsum("bij,bjhw->bihw", m, x)
    x = x.clamp(0, 1)
    x = x ** u(cfg.gamma)

    sel = torch.rand(b, generator=g) < cfg.p_blur
    if sel.any():
        sigma = 0.4 + float(torch.rand(1, generator=g)) * (cfg.max_blur_sigma - 0.4)
        x[sel] = _gaussian_blur(x[sel], sigma)
    sel = torch.rand(b, generator=g) < cfg.p_lowres
    if sel.any():
        small = int(out_size * (0.35 + 0.4 * float(torch.rand(1, generator=g))))
        lo = F.interpolate(x[sel], size=small, mode="bilinear", antialias=True, align_corners=False)
        x[sel] = F.interpolate(lo, size=out_size, mode="bilinear", align_corners=False)
    sel = torch.rand(b, generator=g) < cfg.p_noise
    if sel.any():
        x[sel] = x[sel] + torch.randn(x[sel].shape, generator=g) * cfg.noise_std
    return x.clamp(0, 1)


def to_model_input(batch_u8: torch.Tensor, out_size: int) -> torch.Tensor:
    """Deterministische Vorverarbeitung für Auswertung/Inferenz: uint8 [B,H,W,3] -> [B,3,S,S] in [0,1]."""
    x = batch_u8.permute(0, 3, 1, 2).float() / 255.0
    if x.shape[-1] != out_size:
        x = F.interpolate(x, size=out_size, mode="bilinear", antialias=True, align_corners=False)
    return x


def normalize(x: torch.Tensor) -> torch.Tensor:
    mean = torch.tensor(config.MEAN, dtype=x.dtype).view(1, 3, 1, 1)
    std = torch.tensor(config.STD, dtype=x.dtype).view(1, 3, 1, 1)
    return (x - mean) / std
