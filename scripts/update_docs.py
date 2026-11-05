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
    if de:
        return f"""## Ergebnisse

Modell `{M['run']}` (MobileNetV3-Large, {M['config']['image_size']} px, ONNX {f(M['onnx']['size_mb'], 1)} MB).
Konfiguration nur per Validierung gewählt; Test und externer Test wurden **einmal** am Ende ausgewertet.

{table}

**Ampel auf echten Smartphone-Fotos** (PAD-UFES-20, Brasilien, nie im Training; Schwellen aus der
Validierung unverändert übernommen):

{zhead}
{chr(10).join(zr)}

- Die AUROC sinkt von {f(test['clinical']['auroc'], 3)} (interne Kamerafotos) auf {f(ext['auroc'], 3)} (fremde Smartphone-Fotos) –
  das ist der erwartete Effekt einer anderen Klinik, Kamera und Bevölkerung, und genau deshalb gibt es den externen Test.
- „Nicht beurteilbar“: {p(scin.get('ood_rate'), 1)} der SCIN-Handyfotos (meist Ausschläge) werden abgewiesen,
  bei den Validierungsbildern ~1 % (per Konstruktion).
- Details, Experimente und Diagramme: Seite **So funktioniert’s** der App und [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).
"""
    return f"""## Results

Model `{M['run']}` (MobileNetV3-Large, {M['config']['image_size']} px, ONNX {f(M['onnx']['size_mb'], 1, False)} MB).
Configuration chosen on validation only; test and external test were evaluated **once** at the end.

{table}

**Traffic light on real smartphone photos** (PAD-UFES-20, Brazil, never seen in training; thresholds
taken unchanged from validation):

{zhead}
{chr(10).join(zr)}

- AUROC drops from {f(test['clinical']['auroc'], 3, False)} (internal camera photos) to {f(ext['auroc'], 3, False)} (foreign smartphone photos) –
  the expected effect of a different clinic, camera and population, which is why the external test exists.
- “Cannot be assessed”: {p(scin.get('ood_rate'), 1, False)} of SCIN phone photos (mostly rashes) are rejected, ~1% of validation images (by construction).
"""


def experiments() -> str:
    rows = ["| Run | Netz | Auflösung | Bildarten im Training | Val-AUROC Kamera | Val-AUROC 3D-TBP | Val-pAUC80 3D-TBP | Val-AUROC Dermoskopie |",
            "|---|---|---:|---|---:|---:|---:|---:|"]
    for e in M.get("experiments", []):
        doms = e["domains"] if isinstance(e["domains"], str) else " + ".join(k for k, v in e["domains"].items() if v > 0)
        star = " ★" if e["run"] == M["run"] else ""
        rows.append(f"| {e['run']}{star} | {e['backbone']} | {e['image_size']} | {doms} | {f(e['val_clinical_auroc'])} | "
                    f"{f(e['val_tbp_auroc'])} | {f(e['val_tbp_pauc80'])} | {f(e['val_dermoscopic_auroc'])} |")
    hist = M.get("history", [])
    h = ["| Epoche | Loss | Val-AUROC Kamera | Val-AUROC 3D-TBP | Val-AUROC Dermoskopie |", "|---:|---:|---:|---:|---:|"]
    for r in hist:
        h.append(f"| {r['epoch']} | {f(r['loss'])} | {f(r.get('clinical_auroc'))} | {f(r.get('tbp_auroc'))} | {f(r.get('dermoscopic_auroc'))} |")
    return ("## Läufe (nur Validierung, mit 4-facher TTA)\n\n" + "\n".join(rows)
            + f"\n\n★ = ausgewähltes Modell. Verlauf von `{M['run']}` (Validierung je Epoche, ohne TTA, "
              "SLICE-3D-Gutartige als 6 000er-Stichprobe):\n\n" + "\n".join(h))


if __name__ == "__main__":
    replace_block(ROOT / "README.md", "RESULTS", results(True))
    replace_block(ROOT / "README.en.md", "RESULTS", results(False))
    replace_block(ROOT / "docs/EXPERIMENTS.md", "EXPERIMENTS", experiments())
    print("README.md, README.en.md, docs/EXPERIMENTS.md aktualisiert")
