"""E0 – Vergleichsbasis: ImageNet-Merkmale ohne Nachtraining + logistische Regression.

Zeigt, wie viel das Nachtrainieren (Fine-Tuning) tatsächlich bringt.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from skintriage import config
from skintriage.evaluation import metrics
from skintriage.models.infer import predict
from skintriage.models.net import TriageNet
from skintriage.training.data import ImageStore


def linear_probe(backbone: str = "mobilenetv3_large_100", size: int = config.IMAGE_SIZE,
                 per_stratum: int = 2500, out: Path = config.ARTIFACTS_DIR / "baseline" / "linear_probe.json") -> dict:
    torch.set_num_threads(4)
    store = ImageStore.open()
    cat = store.catalog
    net = TriageNet(backbone, pretrained=True).eval()
    rng = np.random.default_rng(config.SEED)

    tr = []
    for dom in config.DOMAINS:
        for mal in (True, False):
            pool = cat.index[(cat.split == "train") & (cat.domain == dom) & ((cat.binary == 1) == mal)].to_numpy()
            tr.append(rng.choice(pool, size=min(per_stratum, len(pool)), replace=False))
    tr = np.concatenate(tr)
    va = cat.index[(cat.split == "val") & cat.binary.isin([0, 1])].to_numpy()
    tbp_neg = va[((cat.domain == "tbp") & (cat.binary == 0)).to_numpy()[va]]
    va = np.setdiff1d(va, rng.choice(tbp_neg, len(tbp_neg) - 6000, replace=False))

    rows = cat.row.to_numpy()
    _, etr = predict(net, store.images, rows[tr], size)
    _, eva = predict(net, store.images, rows[va], size)
    scaler = StandardScaler().fit(etr)
    ytr = (cat.binary.to_numpy()[tr] == 1).astype(int)
    clf = LogisticRegression(C=0.1, max_iter=2000).fit(scaler.transform(etr), ytr)
    s = clf.decision_function(scaler.transform(eva))
    res = {"backbone": backbone, "image_size": size, "n_train": int(len(tr)), "val": {}, "val_pauc80": {}}
    for dom in config.DOMAINS:
        m = cat.domain.to_numpy()[va] == dom
        y = cat.binary.to_numpy()[va][m]
        res["val"][dom] = metrics.auroc(y, s[m])
        res["val_pauc80"][dom] = metrics.pauc_above_tpr(y, s[m])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    print(json.dumps(linear_probe(), indent=2))
