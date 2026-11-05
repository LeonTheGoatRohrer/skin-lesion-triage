"""Fotos mit dem exportierten ONNX-Modell bewerten (gleiche Logik wie die Web-App)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from skintriage import config
from skintriage.data.preprocess import square_resize

ZONE_TEXT = {0: "GRÜN  – aktuell unauffällig", 1: "GELB  – beobachten, bei Veränderung abklären",
             2: "ROT   – ärztlich abklären lassen"}


def load(model_dir: Path):
    import onnxruntime as ort

    meta = json.loads((model_dir / "model" / "meta.json").read_text())
    sess = ort.InferenceSession(str(model_dir / "model" / "model.onnx"), providers=["CPUExecutionProvider"])
    return sess, meta


def prepare(path: Path, size: int) -> np.ndarray:
    import torch

    from skintriage.training.augment import to_model_input

    arr = square_resize(Image.open(path), config.STORE_SIZE)
    return to_model_input(torch.from_numpy(arr[None]), size).numpy().astype(np.float32)


def predict_files(model_dir: Path, paths: list[Path]):
    sess, meta = load(model_dir)
    ref = np.asarray(meta["rule"]["reference_benign"])
    for p in paths:
        x = prepare(p, meta["image_size"])
        probs, score, ood = sess.run(None, {"image": x})
        s = float(score[0])
        zone = 2 if s >= meta["rule"]["t_high"] else (1 if s >= meta["rule"]["t_low"] else 0)
        pct = float(np.searchsorted(ref, s, side="right") / len(ref))
        top = np.argsort(probs[0])[::-1][:3]
        groups = ", ".join(f"{meta['groups'][i]['de']} {probs[0][i]:.0%}" for i in top)
        flag = "  ⚠ nicht beurteilbar (ungewöhnliches Bild)" if float(ood[0]) > meta["ood_threshold"] else ""
        yield (f"{p.name}: {ZONE_TEXT[zone]} | auffälliger als {pct:.0%} der gutartigen Referenzbilder | "
               f"Score {s:+.2f} | ähnlich: {groups}{flag}")
