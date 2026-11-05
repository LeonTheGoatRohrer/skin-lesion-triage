#!/usr/bin/env python
"""Schreibt die Ergebnis-Blöcke in README.md, README.en.md und docs/EXPERIMENTS.md
aus web/public/data/metrics.json (keine Zahl wird von Hand abgetippt).

Aufruf: python scripts/update_docs.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT / "web/public/data/metrics.json").read_text())

DOM_DE = {"clinical": "Kamerafotos", "tbp": "3D-TBP-Ausschnitte", "dermoscopic": "Dermoskopie"}
DOM_EN = {"clinical": "camera photos", "tbp": "3D TBP crops", "dermoscopic": "dermoscopy"}


def f(x, d=3, de=True):
    if x is None:
        return "–"
    s = f"{x:.{d}f}"
    return s.replace(".", ",") if de else s


def p(x, d=1, de=True):
    if x is None:
        return "–"
    s = f"{100 * x:.{d}f}"
    return (s.replace(".", ",") + " %") if de else (s + "%")


def ci(b, de=True):
    c = b.get("auroc_ci")
    return f" [{f(c[0], 3, de)}–{f(c[1], 3, de)}]" if c else ""


def replace_block(path: Path, tag: str, body: str) -> None:
    txt = path.read_text()
    new = re.sub(rf"<!-- {tag}:START -->.*?<!-- {tag}:END -->",
                 f"<!-- {tag}:START -->\n{body.strip()}\n<!-- {tag}:END -->", txt, flags=re.S)
    path.write_text(new)


def results(de: bool) -> str:
    test = M["splits"]["test"]["domains"]
    ext = M["splits"]["external"]["domains"]["clinical"]
    z = ext["zones"]
    rows = []
    for d in ("clinical", "tbp", "dermoscopic"):
        b = test.get(d)
        if not b:
            continue
        name = (f"Interner Test · {DOM_DE[d]}" if de else f"Internal test · {DOM_EN[d]}")
        rows.append((name, b))
    rows.append(("**Extern · PAD-UFES-20 (Smartphone)**" if de else "**External · PAD-UFES-20 (smartphone)**", ext))
    if de:
        head = ("| Datensatz | bösartig / gutartig | AUROC [95 %-KI] | pAUC80 | Sensitivität Gelb+Rot | Spezifität (nicht Rot) |\n"
                "|---|---:|---:|---:|---:|---:|")
    else:
        head = ("| Dataset | malignant / benign | AUROC [95% CI] | pAUC80 | Sensitivity yellow+red | Specificity (not red) |\n"
                "|---|---:|---:|---:|---:|---:|")
    lines = [head] + [
        f"| {n} | {b['n_malignant']} / {b['n_benign']} | {f(b['auroc'], 3, de)}{ci(b, de)} | {f(b['pauc80'], 3, de)} | "
        f"{p(b['at_t_low']['sensitivity'], 1, de)} | {p(b['at_t_high']['specificity'], 1, de)} |" for n, b in rows]
    table = "\n".join(lines)
    zr = []
    for key, de_name, en_name in (("malignant", "bösartig", "malignant"), ("precursor", "aktinische Keratose (Vorstufe)", "actinic keratosis (precursor)"),
                                  ("benign", "gutartig", "benign")):
        if key in z:
            zr.append(f"| {de_name if de else en_name} | {z[key]['n']} | {p(z[key]['green'], 1, de)} | {p(z[key]['yellow'], 1, de)} | {p(z[key]['red'], 1, de)} |")
    zhead = ("| PAD-UFES-20 | n | Grün | Gelb | Rot |\n|---|---:|---:|---:|---:|" if de
             else "| PAD-UFES-20 | n | green | yellow | red |\n|---|---:|---:|---:|---:|")
    scin = M.get("scin") or {}
    tz = test["clinical"]["zones"]
    tm = test["clinical"].get("melanoma", {})
    em = ext.get("melanoma", {})
    mel_found = round(em.get("n", 0) * (1 - em.get("green", 0)))
    bullets_de = "\n".join([
        f"- **Die Rangfolge überträgt sich:** AUROC intern {f(test['clinical']['auroc'])} → extern {f(ext['auroc'])} "
        "(andere Klinik, andere Kameras, anderes Land).",
        f"- **Die Schwellen übertragen sich schlechter:** Gutartige Fotos in Grün intern {p(tz['benign']['green'])}, "
        f"auf den fremden Handyfotos nur {p(z['benign']['green'])} – die meisten landen in Gelb. Das Modell ist bei fremden "
        "Kameras „nervöser“. Die Schwellen wurden bewusst nicht an PAD-UFES-20 angepasst, sonst wäre der Test nicht mehr extern.",
        f"- **Melanome:** intern {p(tm.get('green'))} in Grün (n = {tm.get('n', '–')}), extern {mel_found} von {em.get('n', '–')} "
        f"in Gelb/Rot; AUROC Melanom vs. Nävus {f(tm.get('auroc_vs_nevus'))} intern, {f(em.get('auroc_vs_nevus'))} extern.",
        f"- **„Nicht beurteilbar“ greift kaum:** Nur {p(scin.get('ood_rate'))} der SCIN-Handyfotos (meist Ausschläge) werden "
        "abgewiesen. Die App ist für einzelne Hautstellen gedacht; bei Ausschlägen ist das Ergebnis bedeutungslos.",
        "- Details, Experimente und Diagramme: Seite **So funktioniert’s** der App und [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).",
    ])
    bullets_en = "\n".join([
        f"- **Ranking transfers:** AUROC internal {f(test['clinical']['auroc'], 3, False)} → external {f(ext['auroc'], 3, False)} "
        "(different clinic, cameras, country).",
        f"- **Thresholds transfer worse:** benign photos kept green internally {p(tz['benign']['green'], 1, False)}, on the foreign "
        f"phone photos only {p(z['benign']['green'], 1, False)} – most end up yellow. The model is more “nervous” with unfamiliar "
        "cameras. Thresholds were deliberately not re-tuned on PAD-UFES-20, otherwise the test would no longer be external.",
        f"- **Melanomas:** internally {p(tm.get('green'), 1, False)} green (n = {tm.get('n', '–')}), externally {mel_found} of "
        f"{em.get('n', '–')} yellow/red; AUROC melanoma vs. nevus {f(tm.get('auroc_vs_nevus'), 3, False)} internal, "
        f"{f(em.get('auroc_vs_nevus'), 3, False)} external.",
        f"- **“Cannot be assessed” rarely triggers:** only {p(scin.get('ood_rate'), 1, False)} of SCIN phone photos (mostly rashes) "
        "are rejected. The app is meant for single spots; for rashes the result is meaningless.",
    ])
    if de:
        return f"""## Ergebnisse

Modell `{M['run']}` (MobileNetV3-Large, {M['config']['image_size']} px, ONNX {f(M['onnx']['size_mb'], 1)} MB).
Konfiguration nur per Validierung gewählt; Test und externer Test wurden **einmal** am Ende ausgewertet.

{table}

**Ampel auf echten Smartphone-Fotos** (PAD-UFES-20, Brasilien, nie im Training; Schwellen aus der
Validierung unverändert übernommen):

{zhead}
{chr(10).join(zr)}

{bullets_de}
"""
    return f"""## Results

Model `{M['run']}` (MobileNetV3-Large, {M['config']['image_size']} px, ONNX {f(M['onnx']['size_mb'], 1, False)} MB).
Configuration chosen on validation only; test and external test were evaluated **once** at the end.

{table}

**Traffic light on real smartphone photos** (PAD-UFES-20, Brazil, never seen in training; thresholds
taken unchanged from validation):

{zhead}
{chr(10).join(zr)}

{bullets_en}
"""


def experiments() -> str:
    rows = ["| Run | Bildarten im Training | Val-AUROC Kamera | **Spez. an Gelb-Schwelle (Kamera)** | AUROC Melanom vs. Nävus (Kamera) | Val-AUROC 3D-TBP | Val-pAUC80 3D-TBP | Val-AUROC Dermoskopie |",
            "|---|---|---:|---:|---:|---:|---:|---:|"]
    for e in M.get("experiments", []):
        doms = e["domains"] if isinstance(e["domains"], str) else " + ".join(k for k, v in e["domains"].items() if v > 0)
        if e.get("use_extra"):
            doms += " + ISIC-Dermoskopie (Melanom-Fokus)"
        if e.get("group_balance"):
            doms += f", Diagnose-Balancierung {e['group_balance']}"
        star = " ★" if e["run"] == M["run"] else ""
        rows.append(f"| {e['run']}{star} | {doms} | {f(e['val_clinical_auroc'])} | {f(e.get('val_clinical_spec_at_low'))} | "
                    f"{f(e.get('val_clinical_mel_vs_nev'))} | {f(e['val_tbp_auroc'])} | {f(e['val_tbp_pauc80'])} | {f(e['val_dermoscopic_auroc'])} |")
    hist = M.get("history", [])
    h = ["| Epoche | Loss | Val-AUROC Kamera | Val-AUROC 3D-TBP | Val-AUROC Dermoskopie |", "|---:|---:|---:|---:|---:|"]
    for r in hist:
        h.append(f"| {r['epoch']} | {f(r['loss'])} | {f(r.get('clinical_auroc'))} | {f(r.get('tbp_auroc'))} | {f(r.get('dermoscopic_auroc'))} |")
    return ("## Läufe (nur Validierung, mit 4-facher TTA; MobileNetV3-Large, 128 px)\n\n" + "\n".join(rows)
            + f"\n\n★ = ausgewähltes Modell. Verlauf von `{M['run']}` (Validierung je Epoche, ohne TTA, "
              "SLICE-3D-Gutartige als 6 000er-Stichprobe):\n\n" + "\n".join(h))


if __name__ == "__main__":
    replace_block(ROOT / "README.md", "RESULTS", results(True))
    replace_block(ROOT / "README.en.md", "RESULTS", results(False))
    replace_block(ROOT / "docs/EXPERIMENTS.md", "EXPERIMENTS", experiments())
    print("README.md, README.en.md, docs/EXPERIMENTS.md aktualisiert")
