"""Auswertung eines Trainingslaufs.

- Vorhersagen werden je Split zwischengespeichert (``<run>/preds/``).
- Ampel-Schwellen und Perzentil-Referenz werden **nur** auf dem Val-Split (Domäne
  Kamerafoto) festgelegt und danach unverändert auf Test und externe Daten angewendet.
- ``test`` und ``external`` werden erst ausgewertet, wenn die Konfiguration eingefroren ist
  (siehe docs/EXPERIMENTS.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from skintriage import config, labels
from skintriage.evaluation import metrics
from skintriage.evaluation.ood import calibrate_threshold, fit_ood
from skintriage.evaluation.triage import fit_rule, zone_table
from skintriage.models.infer import group_probs_np, malignant_logit_np, predict
from skintriage.training.data import ImageStore
from skintriage.training.train import load_model

N_BOOT = 400


def _cached_predict(run_dir: Path, tag: str, model, images, rows, size, tta) -> tuple[np.ndarray, np.ndarray]:
    path = run_dir / "preds" / f"{tag}{'_tta' if tta else ''}.npz"
    if path.exists():
        d = np.load(path)
        if len(d["logits"]) == len(rows):
            return d["logits"], d["emb"]
    path.parent.mkdir(parents=True, exist_ok=True)
    logits, emb = predict(model, images, rows, size, tta=tta)
    np.savez_compressed(path, logits=logits.astype(np.float32), emb=emb.astype(np.float16))
    return logits, emb


def _block(y, s, w, groups, rule, with_ci: bool = True) -> dict:
    """Kennzahlen für eine Teilmenge (y: 0/1/2; AUROC nur über 0/1)."""
    b = np.isin(y, [0, 1])
    out = {"n": int(len(y)), "n_malignant": int((y == 1).sum()), "n_benign": int((y == 0).sum()),
           "n_precursor": int((y == 2).sum())}
    if b.sum() and len(np.unique(y[b])) == 2:
        yb, sb, wb, gb = y[b], s[b], w[b], groups[b]
        out["auroc"] = metrics.auroc(yb, sb, wb)
        out["pauc80"] = metrics.pauc_above_tpr(yb, sb, wb)
        if with_ci:
            out["auroc_ci"] = metrics.bootstrap_ci(metrics.auroc, yb, sb, wb, gb, n_boot=N_BOOT)
        sens_lo, spec_lo = metrics.sens_spec(yb, sb, wb, rule.t_low)
        sens_hi, spec_hi = metrics.sens_spec(yb, sb, wb, rule.t_high)
        out["at_t_low"] = {"sensitivity": sens_lo, "specificity": spec_lo}
        out["at_t_high"] = {"sensitivity": sens_hi, "specificity": spec_hi}
        fpr, tpr, _ = metrics.roc(yb, sb, wb)
        keep = np.unique(np.linspace(0, len(fpr) - 1, min(len(fpr), 120)).astype(int))
        out["roc"] = {"fpr": np.round(fpr[keep], 4).tolist(), "tpr": np.round(tpr[keep], 4).tolist()}
    out["zones"] = zone_table(rule, y, s, w)
    return out


def _fitz_bucket(v) -> str | None:
    return {"I": "I–II", "II": "I–II", "III": "III–IV", "IV": "III–IV", "V": "V–VI", "VI": "V–VI"}.get(v)


def evaluate_run(run_dir: Path, splits=("val",), tta: bool = True, store: ImageStore | None = None) -> dict:
    run_dir = Path(run_dir)
    model, cfg = load_model(run_dir)
    torch.set_num_threads(cfg.get("threads", 4))
    size = cfg["image_size"]
    store = store or ImageStore.open()
    cat = store.catalog
    rows = cat.row.to_numpy()

    def preds_for(split: str):
        idx = cat.index[cat.split == split].to_numpy()
        logits, emb = _cached_predict(run_dir, split, model, store.images, rows[idx], size, tta)
        return idx, logits, emb

    # --- Regel (Ampel + Perzentil) nur auf Val, Domäne Kamerafoto -------------------------
    vidx, vlog, vemb = preds_for("val")
    vs = malignant_logit_np(vlog)
    vy = cat.binary.to_numpy()[vidx]
    vw = cat.weight.to_numpy()[vidx]
    clin = (cat.domain.to_numpy()[vidx] == "clinical") & np.isin(vy, [0, 1])
    rule = fit_rule(vy[clin], vs[clin], vw[clin])

    # --- OOD: PCA auf Trainings-Embeddings (Stichprobe je Domäne) ----------------------------
    rng = np.random.default_rng(config.SEED)
    tr = []
    for dom in config.DOMAINS:
        pool = cat.index[(cat.split == "train") & (cat.domain == dom)].to_numpy()
        tr.append(rng.choice(pool, size=min(len(pool), 3000), replace=False))
    tidx = np.sort(np.concatenate(tr))
    _, temb = _cached_predict(run_dir, "train_sub", model, store.images, rows[tidx], size, tta)
    ood = calibrate_threshold(fit_ood(temb.astype(np.float64)), vemb.astype(np.float64))
    np.savez(run_dir / "ood.npz", mean=ood.mean, components=ood.components, variances=ood.variances,
             residual_var=ood.residual_var, threshold=ood.threshold)

    results = {"run": run_dir.name, "config": cfg, "tta": tta, "rule": rule.to_dict(),
               "ood": ood.to_dict(), "splits": {}}
    for split in splits:
        idx, logits, emb = (vidx, vlog, vemb) if split == "val" else preds_for(split)
        s = malignant_logit_np(logits)
        sub = cat.iloc[idx]
        y, w, groups = sub.binary.to_numpy(), sub.weight.to_numpy(), sub.group.to_numpy()
        res: dict = {"domains": {}, "sources": {}}
        for dom in config.DOMAINS:
            m = (sub.domain == dom).to_numpy()
            if m.any():
                res["domains"][dom] = _block(y[m], s[m], w[m], groups[m], rule)
                res["domains"][dom]["ood_rate"] = float((ood.score(emb[m]) > ood.threshold).mean())
        for src in sorted(sub.source.unique()):
            m = (sub.source == src).to_numpy() & (sub.domain == "clinical").to_numpy()
            if m.sum() >= 20:
                res["sources"][src] = _block(y[m], s[m], w[m], groups[m], rule, with_ci=False)
        # Hauttyp (Fitzpatrick), wo annotiert
        fz = sub.fitzpatrick_skin_type.map(_fitz_bucket).to_numpy()
        res["fitzpatrick"] = {}
        for bucket in ("I–II", "III–IV", "V–VI"):
            m = (fz == bucket) & (sub.domain == "clinical").to_numpy()
            if m.sum() >= 10:
                res["fitzpatrick"][bucket] = _block(y[m], s[m], w[m], groups[m], rule, with_ci=False)
        # Diagnose-Gruppen: Top-1-Treffer, wo die feine Gruppe bekannt ist
        gl = sub.group_label.to_numpy()
        known = (gl >= 0) & (sub.domain == "clinical").to_numpy()
        if known.sum():
            pred = group_probs_np(logits[known]).argmax(1)
            conf = np.zeros((labels.N_GROUPS, labels.N_GROUPS), dtype=int)
            np.add.at(conf, (gl[known], pred), 1)
            recall = [conf[i, i] / conf[i].sum() if conf[i].sum() else None for i in range(labels.N_GROUPS)]
            res["groups"] = {"confusion": conf.tolist(), "recall": recall,
                             "balanced_accuracy": float(np.mean([r for r in recall if r is not None]))}
        results["splits"][split] = res

    # --- SCIN: Ausschläge & Co. – wie oft sagt das Modell "nicht beurteilbar"? --------------
    scin_path = config.PROCESSED_DIR / "scin.parquet"
    if scin_path.exists():
        scin = pd.read_parquet(scin_path)
        scin = scin[scin.ok].reset_index(drop=True)
        simg = np.memmap(config.PROCESSED_DIR / f"scin_{config.STORE_SIZE}.u8", dtype=np.uint8, mode="r",
                         shape=(int(scin.row.max()) + 1, config.STORE_SIZE, config.STORE_SIZE, 3))
        slog, semb = _cached_predict(run_dir, "scin", model, simg, scin.row.to_numpy(), size, tta)
        ss = malignant_logit_np(slog)
        flagged = ood.score(semb) > ood.threshold
        z = rule.zone(ss)
        results["scin"] = {"n": int(len(scin)), "ood_rate": float(flagged.mean()),
                           "zones_if_not_flagged": {k: float((z[~flagged] == i).mean())
                                                    for i, k in enumerate(("green", "yellow", "red"))},
                           "top_conditions": scin.top_condition.value_counts().head(8).to_dict()}

    results["summary"] = summarize(results)
    tag = "_".join(splits) + ("_tta" if tta else "")
    (run_dir / f"eval_{tag}.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    return results


def summarize(res: dict) -> dict:
    out = {"run": res["run"], "rule": {k: round(v, 3) for k, v in res["rule"].items()
                                       if k in ("t_low", "t_high")}}
    for split, r in res["splits"].items():
        for dom, b in r["domains"].items():
            if "auroc" not in b:
                continue
            key = f"{split}/{dom}"
            out[key] = {"auroc": round(b["auroc"], 3), "pauc80": round(b["pauc80"], 4),
                        "sens@t_low": round(b["at_t_low"]["sensitivity"], 3),
                        "spec@t_low": round(b["at_t_low"]["specificity"], 3),
                        "sens@t_high": round(b["at_t_high"]["sensitivity"], 3),
                        "spec@t_high": round(b["at_t_high"]["specificity"], 3),
                        "ood_rate": round(b.get("ood_rate", float("nan")), 3)}
            if "auroc_ci" in b:
                out[key]["auroc_ci"] = [round(v, 3) for v in b["auroc_ci"]]
        if "groups" in r:
            out[f"{split}/groups_bal_acc"] = round(r["groups"]["balanced_accuracy"], 3)
    if "scin" in res:
        out["scin_ood_rate"] = round(res["scin"]["ood_rate"], 3)
    return out
