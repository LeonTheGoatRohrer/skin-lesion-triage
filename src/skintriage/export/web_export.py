"""Exportiert das gewählte Modell und alle Kennzahlen für die Web-App.

Voraussetzung: Der Lauf wurde final ausgewertet
(``skintriage evaluate --run <run> --splits val,test,external``).

Erzeugt:
- ``web/public/model/model.onnx`` – Netz inkl. Normalisierung, TTA, Score und OOD-Abstand
- ``web/public/model/meta.json``  – Schwellen, Perzentil-Referenz, Qualitätsgrenzen, Gruppen
- ``web/public/data/metrics.json`` – alles für die Seite "So funktioniert's"
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import torch

from skintriage import config, labels
from skintriage.evaluation.ood import OODModel
from skintriage.export.onnx_export import WebModel, check_parity, compress_weights_fp16, export_onnx
from skintriage.export.quality import derive_limits, quality_features
from skintriage.training.augment import to_model_input
from skintriage.training.data import ImageStore
from skintriage.training.train import load_model

FINAL_EVAL = "eval_val_test_external_tta.json"


def _round(obj, nd=4):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round(v, nd) for v in obj]
    return obj


def load_ood(run_dir: Path) -> OODModel:
    d = np.load(run_dir / "ood.npz")
    return OODModel(d["mean"], d["components"], d["variances"], float(d["residual_var"]), float(d["threshold"]))


def dataset_summary(cat) -> dict:
    out = {"total_images": int(len(cat)), "rows": []}
    g = cat.groupby(["split", "domain", "source"])
    for (split, dom, src), sub in g:
        out["rows"].append({"split": split, "domain": dom, "source": src, "images": int(len(sub)),
                            "malignant": int((sub.binary == 1).sum()), "benign": int((sub.binary == 0).sum()),
                            "precursor": int((sub.binary == 2).sum()),
                            "groups": int(sub.group.nunique()),
                            "benign_weighted": float(sub.weight[sub.binary == 0].sum())})
    return out


def experiments_table(runs_dir: Path) -> list[dict]:
    rows = []
    for p in sorted(runs_dir.glob("*/eval_val_tta.json")) + sorted(runs_dir.glob("*/eval_val.json")):
        r = json.loads(p.read_text())
        s = r["summary"]
        rows.append({"run": r["run"], "tta": r.get("tta", False), "backbone": r["config"]["backbone"],
                     "image_size": r["config"]["image_size"], "epochs": r["config"]["epochs"],
                     "domains": r["config"]["domains"],
                     "val_clinical_auroc": s.get("val/clinical", {}).get("auroc"),
                     "val_tbp_auroc": s.get("val/tbp", {}).get("auroc"),
                     "val_tbp_pauc80": s.get("val/tbp", {}).get("pauc80"),
                     "val_dermoscopic_auroc": s.get("val/dermoscopic", {}).get("auroc"),
                     "val_clinical_spec_at_low": s.get("val/clinical", {}).get("spec@t_low"),
                     "val_clinical_mel_vs_nev": s.get("val/clinical", {}).get("mel_vs_nev_auroc"),
                     "use_extra": r["config"].get("use_extra", False),
                     "group_balance": r["config"].get("group_balance", 0.0)})
    base = runs_dir.parent / "baseline" / "linear_probe.json"
    if base.exists():
        b = json.loads(base.read_text())
        rows.insert(0, {"run": "e0_linear_probe", "tta": False, "backbone": b["backbone"],
                        "image_size": b["image_size"], "epochs": 0, "domains": "alle",
                        "val_clinical_auroc": b["val"].get("clinical"), "val_tbp_auroc": b["val"].get("tbp"),
                        "val_tbp_pauc80": b.get("val_pauc80", {}).get("tbp"),
                        "val_dermoscopic_auroc": b["val"].get("dermoscopic")})
    return rows


def _thin(values: list[float], n: int = 400) -> list[float]:
    v = np.asarray(values)
    if len(v) <= n:
        return [round(float(x), 4) for x in v]
    q = np.quantile(v, np.linspace(0, 1, n))
    return [round(float(x), 4) for x in q]


def export_all(run_dir: Path, web_public: Path = config.WEB_PUBLIC, preliminary: bool = False) -> dict:
    """``preliminary=True``: nur mit Val-Auswertung exportieren (zum Entwickeln der Web-App)."""
    run_dir = Path(run_dir)
    eval_path = run_dir / FINAL_EVAL
    if preliminary and not eval_path.exists():
        eval_path = run_dir / "eval_val_tta.json"
    if not eval_path.exists():
        raise FileNotFoundError(f"{eval_path} fehlt – zuerst final auswerten: "
                                f"skintriage evaluate --run {run_dir} --splits val,test,external")
    res = json.loads(eval_path.read_text())
    net, cfg = load_model(run_dir)
    size = cfg["image_size"]
    ood = load_ood(run_dir)

    # 1) ONNX (float32, Paritätstest) -> Web-Version mit float16-Gewichten (halbe Größe)
    fp32_path = run_dir / "model_fp32.onnx"
    export_onnx(net, ood, fp32_path, size)
    wm = WebModel(net.to(memory_format=torch.contiguous_format), ood).eval()
    diff32 = check_parity(wm, fp32_path, size)
    if diff32 > 1e-3:
        raise RuntimeError(f"ONNX weicht von PyTorch ab: {diff32}")
    onnx_path = web_public / "model" / "model.onnx"
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    compress_weights_fp16(fp32_path, onnx_path)
    diff = check_parity(wm, onnx_path, size)
    print(f"  ONNX: float32 {fp32_path.stat().st_size / 1e6:.1f} MB (Abw. {diff32:.1e}), "
          f"Web/float16-Gewichte {onnx_path.stat().st_size / 1e6:.1f} MB (Abw. {diff:.1e})")
    if diff > 0.05:
        raise RuntimeError(f"float16-Gewichte verändern das Ergebnis zu stark: {diff}")

    # 2) Qualitätsgrenzen aus Val-Kamerafotos
    store = ImageStore.open(use_extra=bool(cfg.get("use_extra", False)))
    cat = store.catalog
    vidx = cat.index[(cat.split == "val") & (cat.domain == "clinical")].to_numpy()
    x = to_model_input(torch.from_numpy(np.asarray(store.images[np.sort(cat.row.to_numpy()[vidx])])), size)
    q = derive_limits(quality_features(x.permute(0, 2, 3, 1).numpy()))

    rule = res["rule"]
    ext = res["splits"].get("external", {}).get("domains", {}).get("clinical", {})
    tst = res["splits"].get("test", {}).get("domains", {}).get("clinical", {})
    meta = {
        "version": f"{run_dir.name}-{dt.date.today().isoformat()}" + ("-vorläufig" if preliminary else ""),
        "image_size": size,
        "input": "RGB float32 [N,3,S,S] in [0,1]; Normalisierung und TTA stecken im Modell",
        "groups": [{"key": k, "de": labels.GROUP_NAMES_DE[k], "en": labels.GROUP_NAMES_EN[k],
                    "kind": "malignant" if i in labels.MALIGNANT else ("precursor" if i in labels.PRECURSOR
                                                                       else "benign")}
                   for i, k in enumerate(labels.GROUPS)],
        "rule": {"t_low": rule["t_low"], "t_high": rule["t_high"],
                 "target_sensitivity": rule["target_sensitivity"],
                 "target_specificity": rule["target_specificity"],
                 "reference_benign": _thin(rule["reference_benign"])},
        "ood_threshold": res["ood"]["threshold"],
        "quality": _round(q, 5),
        "zone_stats": {"internal_test": _round({**tst.get("zones", {}), "melanoma": tst.get("melanoma")}, 3),
                       "external_pad_ufes": _round({**ext.get("zones", {}), "melanoma": ext.get("melanoma")}, 3)},
    }
    (web_public / "model").mkdir(parents=True, exist_ok=True)
    (web_public / "model" / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))

    # 3) Kennzahlen für die Erklär-Seite
    hist_path = run_dir / "history.json"
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    metrics_out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "run": run_dir.name,
        "config": {k: cfg[k] for k in ("backbone", "image_size", "epochs", "samples_per_epoch", "domains",
                                       "pos_fraction", "lr", "batch_size")},
        "onnx": {"size_mb": round(onnx_path.stat().st_size / 1e6, 2), "parity_max_abs_diff": diff,
                 "parity_fp32_max_abs_diff": diff32},
        "dataset": dataset_summary(cat),
        "rule": {k: rule.get(k) for k in ("t_low", "t_high", "target_sensitivity", "target_specificity",
                                          "melanoma_sensitivity")},
        "ood": res["ood"],
        "splits": res["splits"],
        "scin": res.get("scin"),
        "history": [{"epoch": h["epoch"], "loss": h["loss"],
                     **{f"{d}_auroc": h["val"][d]["auroc"] for d in config.DOMAINS if d in h["val"]}}
                    for h in history],
        "experiments": experiments_table(run_dir.parent),
        "groups": [labels.GROUP_NAMES_DE[k] for k in labels.GROUPS],
        "groups_en": [labels.GROUP_NAMES_EN[k] for k in labels.GROUPS],
    }
    (web_public / "data").mkdir(parents=True, exist_ok=True)
    (web_public / "data" / "metrics.json").write_text(json.dumps(_round(metrics_out), ensure_ascii=False))
    print(f"  meta.json + metrics.json geschrieben ({web_public})")
    return meta
