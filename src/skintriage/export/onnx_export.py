"""ONNX-Export für den Browser.

Das exportierte Netz enthält alles, was die Web-App braucht, damit der JavaScript-Teil trivial
bleibt und Python und Browser garantiert dasselbe rechnen:

    Eingang  image [N,3,S,S], RGB in [0,1]
    → ImageNet-Normalisierung
    → Test-Time-Augmentation (Original, gespiegelt ↔, gespiegelt ↕, transponiert), Mittelung
    → probs [N,7]  (Ähnlichkeit zu den Diagnose-Gruppen, Softmax)
      score [N]    (Triage-Score = log P(bösartig) − log P(nicht bösartig))
      ood   [N]    (Abstand zu den Trainingsdaten, > Schwelle = "nicht beurteilbar")
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from skintriage import config, labels
from skintriage.evaluation.ood import OODModel


class WebModel(nn.Module):
    def __init__(self, net: nn.Module, ood: OODModel):
        super().__init__()
        self.net = net
        self.register_buffer("mean", torch.tensor(config.MEAN).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(config.STD).view(1, 3, 1, 1))
        self.register_buffer("ood_mean", torch.from_numpy(ood.mean.astype(np.float32)))
        self.register_buffer("ood_comp", torch.from_numpy(ood.components.astype(np.float32)))
        self.register_buffer("ood_var", torch.from_numpy(ood.variances.astype(np.float32)))
        self.ood_resvar = float(ood.residual_var)
        self.mal = list(labels.MALIGNANT)
        self.rest = [i for i in range(labels.N_GROUPS) if i not in labels.MALIGNANT]

    def forward(self, image: torch.Tensor):
        x = (image - self.mean) / self.std
        n = x.shape[0]
        views = torch.cat([x, x.flip(3), x.flip(2), x.transpose(2, 3)], 0)
        logits, emb = self.net(views)
        logits = logits.reshape(4, n, -1).mean(0)
        emb = emb.reshape(4, n, -1).mean(0)
        probs = torch.softmax(logits, dim=1)
        score = torch.logsumexp(logits[:, self.mal], 1) - torch.logsumexp(logits[:, self.rest], 1)
        xc = emb - self.ood_mean
        z = xc @ self.ood_comp.T
        maha = (z * z / self.ood_var).mean(1)
        resid = (xc * xc).sum(1) - (z * z).sum(1)
        ood = 0.5 * (maha + resid / self.ood_resvar)
        return probs, score, ood


def export_onnx(net: nn.Module, ood: OODModel, path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wm = WebModel(net.to(memory_format=torch.contiguous_format).eval(), ood).eval()
    dummy = torch.rand(2, 3, size, size)
    batch = torch.export.Dim("batch", min=1, max=256)
    prog = torch.onnx.export(wm, (dummy,), dynamo=True, input_names=["image"],
                             output_names=["probs", "score", "ood"],
                             dynamic_shapes={"image": {0: batch}}, opset_version=18,
                             external_data=False)
    prog.optimize()
    prog.save(str(path), external_data=False)
    return path


def compress_weights_fp16(src: Path, dst: Path, min_elems: int = 1024) -> Path:
    """Große Gewichte als float16 speichern (halbe Downloadgröße), gerechnet wird weiter in float32.

    Jede komprimierte Gewichtsmatrix bekommt einen Cast-Knoten nach float32; onnxruntime faltet
    diese beim Laden einmalig. Die OOD-Parameter bleiben float32 (Differenzen großer Normen).
    """
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    m = onnx.load(str(src))
    g = m.graph
    casts, new_inits = [], []
    for init in list(g.initializer):
        n = int(np.prod(init.dims)) if len(init.dims) else 1
        if init.data_type != TensorProto.FLOAT or n < min_elems or "ood" in init.name:
            continue
        arr = numpy_helper.to_array(init).astype(np.float16)
        name16 = f"{init.name}__fp16"
        new_inits.append(numpy_helper.from_array(arr, name16))
        casts.append(helper.make_node("Cast", [name16], [init.name], to=TensorProto.FLOAT, name=f"{init.name}__cast"))
        g.initializer.remove(init)
    g.initializer.extend(new_inits)
    nodes = list(g.node)
    del g.node[:]
    g.node.extend(casts + nodes)
    onnx.checker.check_model(m)
    onnx.save(m, str(dst))
    return dst


def check_parity(wm_torch: nn.Module, onnx_path: Path, size: int, n: int = 6, seed: int = 0) -> float:
    """Maximale absolute Abweichung zwischen PyTorch und onnxruntime (sollte < 1e-3 sein)."""
    import onnxruntime as ort

    x = torch.rand(n, 3, size, size, generator=torch.Generator().manual_seed(seed))
    with torch.no_grad():
        ref = [t.numpy() for t in wm_torch(x)]
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    got = sess.run(None, {"image": x.numpy()})
    return float(max(np.abs(a - b).max() for a, b in zip(ref, got)))
