"""ONNX-Export und Gleichheit Python ↔ Browser (Qualitätsmerkmale in JavaScript)."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import torch

from skintriage.evaluation.ood import fit_ood
from skintriage.export.onnx_export import WebModel, check_parity, export_onnx
from skintriage.export.quality import quality_features
from skintriage.models.infer import malignant_logit_np
from skintriage.models.net import TriageNet

ROOT = Path(__file__).resolve().parents[1]


def test_onnx_matches_pytorch(tmp_path):
    torch.manual_seed(0)
    net = TriageNet("mobilenetv3_large_100", pretrained=False).eval()
    rng = np.random.default_rng(0)
    ood = fit_ood(rng.normal(size=(300, net.feat_dim)), k=8)
    path = export_onnx(net, ood, tmp_path / "m.onnx", 64)
    wm = WebModel(net, ood).eval()
    assert check_parity(wm, path, 64, n=3) < 1e-3


def test_fp16_weights_halve_size_and_keep_results(tmp_path):
    from skintriage.export.onnx_export import compress_weights_fp16

    torch.manual_seed(0)
    net = TriageNet("mobilenetv3_large_100", pretrained=False).eval()
    ood = fit_ood(np.random.default_rng(0).normal(size=(300, net.feat_dim)), k=8)
    p32 = export_onnx(net, ood, tmp_path / "m32.onnx", 64)
    p16 = compress_weights_fp16(p32, tmp_path / "m16.onnx")
    assert p16.stat().st_size < 0.6 * p32.stat().st_size
    assert check_parity(WebModel(net, ood).eval(), p16, 64, n=3) < 0.05


def test_webmodel_tta_equals_python_tta():
    """Die TTA im ONNX-Graph muss exakt der TTA in models.infer.predict entsprechen."""
    torch.manual_seed(1)
    net = TriageNet("mobilenetv3_large_100", pretrained=False).eval()
    ood = fit_ood(np.random.default_rng(1).normal(size=(200, net.feat_dim)), k=4)
    wm = WebModel(net, ood).eval()
    x = torch.rand(2, 3, 64, 64)
    with torch.no_grad():
        _, score, _ = wm(x)
        xn = (x - wm.mean) / wm.std
        views = [xn, xn.flip(3), xn.flip(2), xn.transpose(2, 3)]
        logits = sum(net(v)[0] for v in views) / 4
    assert np.allclose(score.numpy(), malignant_logit_np(logits.numpy()), atol=1e-5)


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht installiert")
def test_quality_features_python_equals_javascript(tmp_path):
    rng = np.random.default_rng(0)
    size = 32
    img = rng.random((size, size, 3)).astype(np.float32)
    img[8:20, 8:20] *= 0.3  # etwas Struktur
    chw = img.transpose(2, 0, 1).ravel().tolist()
    (tmp_path / "in.json").write_text(json.dumps({"chw": chw, "size": size}))
    script = f"""
      import {{ qualityFeatures }} from '{(ROOT / "web/src/lib/quality.js").as_posix()}';
      import {{ readFileSync }} from 'node:fs';
      const d = JSON.parse(readFileSync('{(tmp_path / "in.json").as_posix()}', 'utf8'));
      console.log(JSON.stringify(qualityFeatures(Float32Array.from(d.chw), d.size)));
    """
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    py = {k: float(v) for k, v in quality_features(img).items()}
    for k in ("brightness", "overexposed", "sharpness"):
        assert abs(js[k] - py[k]) < 1e-4 * max(1.0, abs(py[k])), (k, js[k], py[k])


def test_blur_lowers_sharpness():
    rng = np.random.default_rng(0)
    img = rng.random((64, 64, 3))
    blurred = (img + np.roll(img, 1, 0) + np.roll(img, 1, 1) + np.roll(img, (1, 1), (0, 1))) / 4
    assert quality_features(blurred)["sharpness"] < quality_features(img)["sharpness"]
