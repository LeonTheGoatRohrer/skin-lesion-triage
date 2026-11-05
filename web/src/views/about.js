// "So funktioniert's": Pipeline, Daten, ehrliche Ergebnisse, Grenzen, Lizenzen.

import { tr, getLang } from '../lib/i18n.js';
import { el, esc, icon, fmt, pct, fmtDate } from '../lib/dom.js';
import { rocChart, stackedBars, hBars, lineChart } from '../components/charts.js';

const BASE = import.meta.env.BASE_URL;
const DOM_COLOR = {
  clinical: 'var(--c-dom-clinical)', tbp: 'var(--c-dom-tbp)', dermoscopic: 'var(--c-dom-dermoscopic)', external: 'var(--c-dom-external)',
};

function domName(d) {
  return {
    clinical: tr('Kamerafotos (Klinik)', 'Camera photos (clinic)'),
    tbp: tr('3D-Ganzkörper-Ausschnitte', '3D total-body crops'),
    dermoscopic: tr('Dermoskopie', 'Dermoscopy'),
    external: tr('Smartphone-Fotos, extern (PAD-UFES-20)', 'Smartphone photos, external (PAD-UFES-20)'),
  }[d] || d;
}

function sourceName(s) {
  return { milk10k: 'MILK10k', slice3d: 'SLICE-3D (ISIC 2024)', pad_ufes_20: 'PAD-UFES-20', msk: 'MSK', anonymous: tr('Anonym', 'Anonymous'), hiba: 'HIBA',
    isic_derm: tr('ISIC-Archiv, Dermoskopie (Melanom-Schwerpunkt)', 'ISIC archive, dermoscopy (melanoma focus)') }[s] || s;
}

function ci(b) {
  return b?.auroc_ci ? ` <span class="text-muted">[${fmt(b.auroc_ci[0], 3)}–${fmt(b.auroc_ci[1], 3)}]</span>` : '';
}

function tile(value, label, note = '') {
  return `<div class="card p-4"><p class="text-2xl font-bold tabular">${value}</p><p class="mt-1 text-sm font-medium">${label}</p>
    ${note ? `<p class="mt-1 text-xs text-muted">${note}</p>` : ''}</div>`;
}

function section(title, body, id = '') {
  return `<section class="space-y-4" ${id ? `id="${id}"` : ''}><h2 class="text-xl font-bold tracking-tight">${title}</h2>${body}</section>`;
}

function pipeline() {
  const steps = [
    ['camera', tr('Foto', 'Photo'), tr('Handykamera oder Galerie; bleibt auf dem Gerät', 'Phone camera or gallery; stays on the device')],
    ['scan', tr('Ausschnitt', 'Crop'), tr('Quadrat um die Hautstelle → 128 × 128 Pixel', 'Square around the spot → 128 × 128 pixels')],
    ['checkCircle', tr('Bildprüfung', 'Image check'), tr('Schärfe, Belichtung, „kennt das Modell so etwas?“', 'Sharpness, exposure, “has the model seen anything like this?”')],
    ['layers', 'MobileNetV3', tr('4 Ansichten (gespiegelt/gedreht), 7 Diagnose-Gruppen', '4 views (flipped/rotated), 7 diagnosis groups')],
    ['sparkles', tr('Ampel & Prozent', 'Traffic light & percent'), tr('Score → Schwellen aus Validierungsdaten', 'Score → thresholds from validation data')],
  ];
  return `<ol class="grid gap-3 sm:grid-cols-5">${steps.map(([ic, t, d], i) => `<li class="card relative p-4">
    <span class="absolute right-3 top-3 text-xs font-semibold text-muted">${i + 1}</span>
    <div class="flex size-9 items-center justify-center rounded-xl bg-accent-soft text-accent">${icon(ic, 'size-5')}</div>
    <p class="mt-3 font-semibold">${t}</p><p class="mt-1 text-xs text-muted">${d}</p></li>`).join('')}</ol>`;
}

function datasetTable(m) {
  const rows = m.dataset.rows;
  const agg = new Map();
  for (const r of rows) {
    const key = `${r.source}|${r.domain}`;
    const a = agg.get(key) || { source: r.source, domain: r.domain, images: 0, malignant: 0, benign: 0, precursor: 0, splits: new Set() };
    a.images += r.images; a.malignant += r.malignant; a.benign += r.benign; a.precursor += r.precursor; a.splits.add(r.split);
    agg.set(key, a);
  }
  const lic = { milk10k: 'CC BY-NC 4.0', slice3d: 'CC BY / CC BY-NC / CC0', pad_ufes_20: 'CC BY 4.0', msk: 'CC BY / CC0', anonymous: 'CC0', hiba: 'CC BY', isic_derm: 'CC BY / CC BY-NC / CC0' };
  const body = [...agg.values()].sort((a, b) => b.images - a.images).map((a) => `<tr class="border-t border-line">
    <td class="py-2 pr-3 font-medium">${esc(sourceName(a.source))}</td>
    <td class="py-2 pr-3">${esc(domName(a.domain))}</td>
    <td class="py-2 pr-3 text-right tabular">${fmt(a.images)}</td>
    <td class="py-2 pr-3 text-right tabular">${fmt(a.malignant)}</td>
    <td class="py-2 pr-3 text-right tabular">${fmt(a.benign)}</td>
    <td class="py-2 pr-3 text-right tabular">${fmt(a.precursor)}</td>
    <td class="py-2 pr-3">${a.splits.has('external') ? tr('nur Test (extern)', 'test only (external)') : 'Train / Val / Test'}</td>
    <td class="py-2 text-xs text-muted">${lic[a.source] || ''}</td></tr>`).join('');
  return `<div class="card overflow-x-auto p-4"><table class="w-full min-w-[640px] text-sm">
    <thead class="text-left text-xs text-muted"><tr><th class="pb-2 pr-3">${tr('Quelle', 'Source')}</th><th class="pr-3">${tr('Bildart', 'Image type')}</th>
      <th class="pr-3 text-right">${tr('Bilder', 'Images')}</th><th class="pr-3 text-right">${tr('bösartig', 'malignant')}</th><th class="pr-3 text-right">${tr('gutartig', 'benign')}</th>
      <th class="pr-3 text-right">${tr('Vorstufe', 'precursor')}</th><th class="pr-3">${tr('Verwendung', 'Use')}</th><th>${tr('Lizenz', 'License')}</th></tr></thead>
    <tbody>${body}</tbody></table>
    <p class="mt-3 text-xs text-muted">${tr(
      'SLICE-3D enthält rund 400 000 gutartige Ausschnitte; verwendet wird eine Zufallsstichprobe, jedes Bild zählt in der Auswertung mit dem Kehrwert seiner Ziehungswahrscheinlichkeit. Bilder derselben Person oder derselben Hautstelle liegen immer im selben Split.',
      'SLICE-3D contains about 400,000 benign crops; a random sample is used and each image is weighted by the inverse of its sampling probability in the evaluation. Images of the same person or the same lesion always fall into the same split.')}</p></div>`;
}

function zoneParts(z) {
  return [
    { value: z.green, color: 'var(--c-green)', label: tr('Grün', 'Green') },
    { value: z.yellow, color: 'var(--c-yellow)', label: tr('Gelb', 'Yellow') },
    { value: z.red, color: 'var(--c-red)', label: tr('Rot', 'Red') },
  ];
}

function sourceTable(m) {
  const rows = [];
  for (const [split, label] of [['test', tr('Interner Test', 'Internal test')], ['external', tr('Extern', 'External')]]) {
    const src = m.splits[split]?.sources || {};
    for (const [k, b] of Object.entries(src)) {
      if (b.auroc == null) continue;
      rows.push(`<tr class="border-t border-line"><td class="py-2 pr-3">${label}</td><td class="py-2 pr-3 font-medium">${esc(sourceName(k))}</td>
        <td class="py-2 pr-3 text-right tabular">${fmt(b.n_malignant)} / ${fmt(b.n_benign)}</td>
        <td class="py-2 pr-3 text-right tabular">${fmt(b.auroc, 3)}</td>
        <td class="py-2 pr-3 text-right tabular">${b.melanoma?.auroc_vs_nevus != null ? fmt(b.melanoma.auroc_vs_nevus, 3) : '–'}
          <span class="text-muted">${b.melanoma ? `(${b.melanoma.n}/${b.melanoma.n_nevus ?? 0})` : ''}</span></td>
        <td class="py-2 text-right tabular">${b.melanoma ? pct(b.melanoma.green, 0) : '–'}</td></tr>`);
    }
  }
  if (!rows.length) return '';
  return `<div class="card overflow-x-auto p-4"><h3 class="font-semibold">${tr('Kamerafotos je Quelle – und Melanome', 'Camera photos per source – and melanomas')}</h3>
    <p class="mt-1 text-xs text-muted">${tr(
      'Die AUROC über alle Kamerafotos mischt Quellen mit sehr unterschiedlichem Krebsanteil; innerhalb einer Quelle ist sie die strengere Zahl. Melanom gegen Nävus ist die Kernfrage bei Muttermalen.',
      'AUROC over all camera photos mixes sources with very different cancer rates; within one source it is the stricter number. Melanoma vs. nevus is the key question for moles.')}</p>
    <table class="mt-3 w-full min-w-[600px] text-sm"><thead class="text-left text-xs text-muted"><tr><th class="pb-2">Split</th><th>${tr('Quelle', 'Source')}</th>
      <th class="text-right">${tr('bösartig / gutartig', 'malignant / benign')}</th><th class="text-right">AUROC</th>
      <th class="text-right">${tr('Melanom vs. Nävus', 'Melanoma vs. nevus')}</th><th class="text-right">${tr('Melanome in Grün', 'Melanomas green')}</th></tr></thead>
    <tbody>${rows.join('')}</tbody></table></div>`;
}

export async function mount(root) {
  let m;
  try {
    m = await fetch(`${BASE}data/metrics.json`).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  } catch {
    root.replaceChildren(el(`<div class="card p-6">${tr('Kennzahlen noch nicht exportiert.', 'Metrics not exported yet.')}</div>`));
    return null;
  }
  const lang = getLang();
  const test = m.splits.test?.domains || {};
  const ext = m.splits.external?.domains?.clinical || {};
  const extZones = ext.zones || {};
  const flagged = extZones.malignant ? extZones.malignant.yellow + extZones.malignant.red : null;

  const rocSeries = [
    ...['clinical', 'tbp', 'dermoscopic'].filter((d) => test[d]?.roc).map((d) => ({
      label: `${tr('Interner Test', 'Internal test')}: ${domName(d)}`, color: DOM_COLOR[d], fpr: test[d].roc.fpr, tpr: test[d].roc.tpr, auc: test[d].auroc })),
    ...(ext.roc ? [{ label: domName('external'), color: DOM_COLOR.external, fpr: ext.roc.fpr, tpr: ext.roc.tpr, auc: ext.auroc }] : []),
  ];

  const metricRows = [
    ...['clinical', 'tbp', 'dermoscopic'].filter((d) => test[d]).map((d) => [`${tr('Test', 'Test')} · ${domName(d)}`, test[d]]),
    ...(ext.auroc != null ? [[domName('external'), ext]] : []),
  ];
  const metricTable = `<div class="card overflow-x-auto p-4"><table class="w-full min-w-[620px] text-sm">
    <thead class="text-left text-xs text-muted"><tr><th class="pb-2">${tr('Datensatz', 'Dataset')}</th><th class="text-right">${tr('bösartig / gutartig', 'malignant / benign')}</th>
      <th class="text-right">AUROC [95 %-KI]</th><th class="text-right">pAUC80</th>
      <th class="text-right">${tr('Sens. Gelb+Rot', 'Sens. yellow+red')}</th><th class="text-right">${tr('Spez. (nicht Rot)', 'Spec. (not red)')}</th></tr></thead>
    <tbody>${metricRows.map(([name, b]) => `<tr class="border-t border-line">
      <td class="py-2 pr-3 font-medium">${esc(name)}</td>
      <td class="py-2 pr-3 text-right tabular">${fmt(b.n_malignant)} / ${fmt(b.n_benign)}</td>
      <td class="py-2 pr-3 text-right tabular">${fmt(b.auroc, 3)}${ci(b)}</td>
      <td class="py-2 pr-3 text-right tabular">${fmt(b.pauc80, 3)}</td>
      <td class="py-2 pr-3 text-right tabular">${pct(b.at_t_low?.sensitivity, 1)}</td>
      <td class="py-2 text-right tabular">${pct(b.at_t_high?.specificity, 1)}</td></tr>`).join('')}</tbody></table>
    <p class="mt-3 text-xs text-muted">${tr(
      'AUROC: Wahrscheinlichkeit, dass eine zufällige bösartige Stelle einen höheren Score bekommt als eine zufällige gutartige (0,5 = Raten, 1 = perfekt). pAUC80: Fläche unter der ROC-Kurve bei mindestens 80 % Sensitivität (Metrik der ISIC-2024-Challenge, Maximum 0,2). Konfidenzintervalle per Bootstrap über Patienten bzw. Hautstellen.',
      'AUROC: probability that a random malignant spot scores higher than a random benign one (0.5 = guessing, 1 = perfect). pAUC80: area under the ROC curve at ≥ 80% sensitivity (ISIC 2024 challenge metric, max 0.2). Confidence intervals by bootstrapping over patients or lesions.')}</p></div>`;

  const zoneRows = [];
  if (test.clinical?.zones) {
    const z = test.clinical.zones;
    if (z.malignant) zoneRows.push({ label: `${tr('Interner Test, bösartig', 'Internal test, malignant')}`, n: z.malignant.n, parts: zoneParts(z.malignant) });
    if (z.benign) zoneRows.push({ label: `${tr('Interner Test, gutartig', 'Internal test, benign')}`, n: z.benign.n, parts: zoneParts(z.benign) });
  }
  if (test.clinical?.melanoma) zoneRows.push({ label: tr('Interner Test, nur Melanome', 'Internal test, melanomas only'), n: test.clinical.melanoma.n, parts: zoneParts(test.clinical.melanoma) });
  if (extZones.malignant) zoneRows.push({ label: tr('PAD-UFES-20 (Handy), bösartig', 'PAD-UFES-20 (phone), malignant'), n: extZones.malignant.n, parts: zoneParts(extZones.malignant) });
  if (ext.melanoma) zoneRows.push({ label: tr('PAD-UFES-20, nur Melanome', 'PAD-UFES-20, melanomas only'), n: ext.melanoma.n, parts: zoneParts(ext.melanoma) });
  if (extZones.precursor) zoneRows.push({ label: tr('PAD-UFES-20, aktinische Keratose (Vorstufe)', 'PAD-UFES-20, actinic keratosis (precursor)'), n: extZones.precursor.n, parts: zoneParts(extZones.precursor) });
  if (extZones.benign) zoneRows.push({ label: tr('PAD-UFES-20 (Handy), gutartig', 'PAD-UFES-20 (phone), benign'), n: extZones.benign.n, parts: zoneParts(extZones.benign) });

  const fz = m.splits.external?.fitzpatrick || {};
  const fzRows = Object.entries(fz).map(([k, b]) => ({ label: `Fitzpatrick ${k}`, value: b.auroc, note: `(${b.n_malignant}/${b.n_benign})`, color: 'var(--c-dom-external)' }));
  const groups = m.splits.external?.groups;
  const groupNames = lang === 'en' ? m.groups_en : m.groups;
  const groupRows = groups ? groups.recall.map((r, i) => (r == null ? null : {
    label: groupNames[i], value: r, note: `(n=${groups.confusion[i].reduce((a, b) => a + b, 0)})`,
    color: i <= 2 ? 'var(--c-red)' : i === 3 ? 'var(--c-yellow)' : 'var(--c-green)' })).filter(Boolean) : [];

  const hist = m.history || [];
  const histChart = hist.length ? lineChart(['clinical', 'tbp', 'dermoscopic'].filter((d) => hist[0][`${d}_auroc`] != null).map((d) => ({
    label: domName(d), color: DOM_COLOR[d], values: hist.map((h) => h[`${d}_auroc`]) })), { yMin: 0.6, yMax: 1, xLabel: tr('Epoche', 'Epoch') }) : '';

  const exps = (m.experiments || []).map((e) => `<tr class="border-t border-line ${e.run === m.run ? 'font-semibold' : ''}">
    <td class="py-2 pr-3">${esc(e.run)}${e.run === m.run ? ' ★' : ''}</td><td class="py-2 pr-3">${esc(e.backbone)} @ ${e.image_size}px</td>
    <td class="py-2 pr-3 text-xs">${esc(typeof e.domains === 'string' ? e.domains : Object.entries(e.domains).filter(([, v]) => v > 0).map(([k]) => k).join(' + '))}</td>
    <td class="py-2 pr-3 text-right tabular">${fmt(e.val_clinical_auroc, 3)}</td><td class="py-2 pr-3 text-right tabular">${fmt(e.val_tbp_auroc, 3)}</td>
    <td class="py-2 text-right tabular">${fmt(e.val_dermoscopic_auroc, 3)}</td></tr>`).join('');

  const view = el(`<div class="fade-in space-y-10">
    <header><h1 class="text-3xl font-bold tracking-tight">${tr('So funktioniert’s', 'How it works')}</h1>
      <p class="mt-2 max-w-3xl text-[15px] leading-relaxed text-muted">${tr(
        'Ein kleines neuronales Netz (MobileNetV3, 4,2 Mio. Parameter) wurde auf Bildern aus dem öffentlichen ISIC-Archiv trainiert und läuft per WebAssembly direkt im Browser. Hier steht ehrlich, wie gut es ist – und wo nicht.',
        'A small neural network (MobileNetV3, 4.2M parameters) was trained on images from the public ISIC archive and runs directly in the browser via WebAssembly. Here is an honest account of how good it is – and where it is not.')}</p>
      <p class="mt-2 text-xs text-muted">${tr('Modell', 'Model')} ${esc(m.run)} · ${tr('exportiert', 'exported')} ${fmtDate(m.generated_at)} · ONNX ${fmt(m.onnx.size_mb, 1)} MB</p></header>

    ${section(tr('Von Foto zu Ampel', 'From photo to traffic light'), pipeline())}

    ${section(tr('Die wichtigsten Zahlen', 'Key numbers'), `<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      ${tile(fmt(test.clinical?.auroc, 3), tr('AUROC interner Test, Kamerafotos', 'AUROC internal test, camera photos'), tr('Patienten/Läsionen nie im Training', 'patients/lesions never in training'))}
      ${tile(fmt(ext.auroc, 3), tr('AUROC echte Handyfotos (extern)', 'AUROC real phone photos (external)'), tr('PAD-UFES-20, Brasilien – komplett ungesehen', 'PAD-UFES-20, Brazil – completely unseen'))}
      ${tile(pct(flagged), tr('bösartige Handyfotos in Gelb oder Rot', 'malignant phone photos in yellow or red'), tr('Ziel aus der Validierung: 95 %', 'target from validation: 95%'))}
      ${tile(ext.melanoma ? pct(ext.melanoma.yellow + ext.melanoma.red) : '–', tr('Melanome (Handy) in Gelb oder Rot', 'melanomas (phone) in yellow or red'), tr(`n = ${ext.melanoma?.n ?? '–'}; Ziel aus der Validierung: 90 %`, `n = ${ext.melanoma?.n ?? '–'}; target from validation: 90%`))}
      ${tile(pct(extZones.benign?.red), tr('gutartige Handyfotos fälschlich Rot', 'benign phone photos wrongly red'), tr('Ziel aus der Validierung: ≤ 10 %', 'target from validation: ≤ 10%'))}
    </div>`)}

    ${section(tr('Daten', 'Data'), `<p class="max-w-3xl text-sm leading-relaxed text-muted">${tr(
      'Statt nur Dermoskopie-Bildern (Aufnahmen mit Auflichtmikroskop) nutzt das Projekt bewusst Bildarten, die einem Handyfoto ähneln: Kamerafotos aus Hautkliniken (MILK10k, MSK) und Ausschnitte aus 3D-Ganzkörperfotos (SLICE-3D, „vergleichbar mit Smartphone-Auflösung“). Die echten Smartphone-Fotos von PAD-UFES-20 bleiben komplett draußen und dienen nur als externer Test.',
      'Instead of only dermoscopy images (taken with a contact microscope), the project deliberately uses image types that resemble a phone photo: camera photos from skin clinics (MILK10k, MSK) and crops from 3D total-body photos (SLICE-3D, “comparable to smartphone resolution”). The real smartphone photos of PAD-UFES-20 are kept out entirely and serve only as an external test.')}</p>
      ${datasetTable(m)}`)}

    ${section(tr('Ergebnisse', 'Results'), `
      <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div class="card p-5"><h3 class="font-semibold">ROC</h3><p class="mt-1 text-xs text-muted">${tr('Jeder Punkt der Kurve ist eine mögliche Schwelle.', 'Each point on the curve is a possible threshold.')}</p>
          <div class="mt-3">${rocChart(rocSeries, { xLabel: tr('Fehlalarmrate (1 − Spezifität)', 'False alarm rate (1 − specificity)'), yLabel: tr('Sensitivität', 'Sensitivity') })}</div></div>
        <div class="card p-5"><h3 class="font-semibold">${tr('Wo landen die Fotos in der Ampel?', 'Where do photos land in the traffic light?')}</h3>
          <p class="mt-1 text-xs text-muted">${tr('Schwellen nur auf Validierungsdaten festgelegt, dann unverändert angewendet.', 'Thresholds set on validation data only, then applied unchanged.')}</p>
          <div class="mt-4">${stackedBars(zoneRows)}</div></div>
      </div>
      ${metricTable}
      ${sourceTable(m)}
      <div class="grid gap-6 lg:grid-cols-2">
        ${fzRows.length ? `<div class="card p-5"><h3 class="font-semibold">${tr('Hauttyp (PAD-UFES-20)', 'Skin type (PAD-UFES-20)')}</h3>
          <p class="mt-1 text-xs text-muted">${tr('AUROC je Fitzpatrick-Gruppe (bösartig/gutartig). Dunkle Hauttypen sind in allen Daten selten – dort ist das Modell kaum geprüft.', 'AUROC per Fitzpatrick group (malignant/benign). Dark skin types are rare in all data – the model is barely tested there.')}</p>
          <div class="mt-4">${hBars(fzRows, { format: (v) => fmt(v, 3) })}</div></div>` : ''}
        ${groupRows.length ? `<div class="card p-5"><h3 class="font-semibold">${tr('Diagnose-Gruppen (PAD-UFES-20)', 'Diagnosis groups (PAD-UFES-20)')}</h3>
          <p class="mt-1 text-xs text-muted">${tr('Anteil, bei dem die ähnlichste Gruppe die richtige ist. Balanced Accuracy', 'Share where the most similar group is the correct one. Balanced accuracy')}: ${fmt(groups.balanced_accuracy, 3)}</p>
          <div class="mt-4">${hBars(groupRows)}</div></div>` : ''}
      </div>
      ${m.scin ? `<div class="card p-5 text-sm"><h3 class="font-semibold">${tr('Realitätscheck: Ausschläge & Co. (Google SCIN)', 'Reality check: rashes etc. (Google SCIN)')}</h3>
        <p class="mt-1 text-muted">${tr(
          `Von ${fmt(m.scin.n)} Handyfotos aus den USA – überwiegend Ekzeme, Kontaktallergien, Insektenstiche – wurden <strong>${pct(m.scin.ood_rate)}</strong> als „nicht beurteilbar“ erkannt (bei normalen Validierungsbildern: ~1 %). Der Rest wird trotzdem bewertet – das Modell kennt keine Ausschläge und ist dafür nicht gedacht.`,
          `Of ${fmt(m.scin.n)} phone photos from the US – mostly eczema, contact allergies, insect bites – <strong>${pct(m.scin.ood_rate)}</strong> were recognized as “cannot be assessed” (normal validation images: ~1%). The rest is still scored – the model does not know rashes and is not meant for them.`)}</p></div>` : ''}
    `)}

    ${section(tr('Training', 'Training'), `<div class="grid gap-6 lg:grid-cols-2">
      <div class="card p-5"><h3 class="font-semibold">${tr('Validierungs-AUROC je Epoche', 'Validation AUROC per epoch')}</h3><div class="mt-3">${histChart}</div></div>
      <div class="card p-5 text-sm leading-relaxed text-muted"><h3 class="font-semibold text-fg">${tr('Rezept', 'Recipe')}</h3>
        <ul class="mt-2 list-disc space-y-1 pl-5">
          <li>${tr('ImageNet-vortrainiertes MobileNetV3, komplett nachtrainiert (AdamW, Cosinus-Lernrate, EMA der Gewichte)', 'ImageNet-pretrained MobileNetV3, fully fine-tuned (AdamW, cosine learning rate, EMA of weights)')}</li>
          <li>${tr('Jeder Batch ist nach Bildart × bösartig/gutartig ausbalanciert – sonst lernt das Netz „Klinikfoto = Krebs“ statt auf die Hautstelle zu schauen', 'Every batch is balanced by image type × malignant/benign – otherwise the network learns “clinic photo = cancer” instead of looking at the spot')}</li>
          <li>${tr('7 Diagnose-Gruppen mit Mengen-Labels: Ist nur „gutartig“ bekannt, zählt die Summe aller gutartigen Gruppen', '7 diagnosis groups with set labels: if only “benign” is known, the sum of all benign groups counts')}</li>
          <li>${tr('Augmentierung für Handy-Realismus: Drehung, Zoom, Weißabgleich, Belichtung, Unschärfe, Rauschen, geringe Auflösung', 'Augmentation for phone realism: rotation, zoom, white balance, exposure, blur, noise, low resolution')}</li>
          <li>${tr('Auswahl nur per Validierung; Test und externer Test wurden einmal am Ende ausgewertet', 'Selection on validation only; test and external test were evaluated once at the end')}</li>
        </ul></div></div>
      ${exps ? `<div class="card overflow-x-auto p-4"><h3 class="mb-2 font-semibold">${tr('Experimente (nur Validierung)', 'Experiments (validation only)')}</h3>
        <table class="w-full min-w-[560px] text-sm"><thead class="text-left text-xs text-muted"><tr><th class="pb-2">Run</th><th>${tr('Netz', 'Network')}</th><th>${tr('Bildarten', 'Image types')}</th>
        <th class="text-right">${tr('Kamera', 'Camera')}</th><th class="text-right">3D-TBP</th><th class="text-right">${tr('Dermoskopie', 'Dermoscopy')}</th></tr></thead><tbody>${exps}</tbody></table></div>` : ''}`)}

    ${section(tr('Grenzen – bitte lesen', 'Limitations – please read'), `<div class="card p-5 text-sm leading-relaxed text-muted"><ul class="list-disc space-y-1.5 pl-5">
      <li>${tr('<strong class="text-fg">Kein Medizinprodukt.</strong> Eine App, die Menschen sagt, ob sie zum Arzt sollen, wäre in der EU ein Medizinprodukt (MDR, mindestens Klasse IIa) und bräuchte eine klinische Prüfung.', '<strong class="text-fg">Not a medical device.</strong> An app telling people whether to see a doctor would be a medical device in the EU (MDR, at least class IIa) and would need clinical evaluation.')}</li>
      <li>${tr('Die Trainingsbilder stammen aus Hautkliniken und Screening-Programmen – nicht von Laien mit dem Handy. Bildausschnitt, Licht und Kamera weichen im Alltag ab.', 'Training images come from skin clinics and screening programs – not from laypeople with phones. Framing, lighting and camera differ in everyday use.')}</li>
      <li>${tr('Viele Labels sind histologisch gesichert, aber nicht alle (z. B. MSK-Fotos: klinische Einschätzung). Seltene Tumoren fehlen fast völlig.', 'Many labels are confirmed by histology, but not all (e.g. MSK photos: clinical assessment). Rare tumors are almost entirely missing.')}</li>
      <li>${tr('Dunkle Hauttypen sind stark unterrepräsentiert. Ergebnisse für Fitzpatrick V–VI sind kaum belastbar.', 'Dark skin types are heavily underrepresented. Results for Fitzpatrick V–VI are hardly reliable.')}</li>
      <li>${tr('Bekannte Abkürzungen der Daten: Stiftmarkierungen, Lineale oder Dermoskop-Ränder treten bei bösartigen Fällen häufiger auf; das Netz kann solche Hinweise mitlernen.', 'Known shortcuts in the data: pen marks, rulers or dermoscope borders occur more often in malignant cases; the network may learn such cues.')}</li>
      <li>${tr('Ein einzelnes Foto zeigt keine Veränderung über die Zeit, kein Tastbefund, keine Vorgeschichte – das, worauf Ärztinnen und Ärzte am meisten achten.', 'A single photo shows no change over time, no palpation, no history – what doctors pay most attention to.')}</li>
    </ul></div>`)}

    ${section(tr('Quellen & Lizenzen', 'Sources & licenses'), `<div class="card p-5 text-xs leading-relaxed text-muted space-y-2">
      <p>ISIC Archive – International Skin Imaging Collaboration, <a class="underline" href="https://www.isic-archive.com" rel="noopener">isic-archive.com</a>.</p>
      <p>MILK10k: MILK study team, ISIC Archive, doi:10.34970/648456, CC BY-NC 4.0. · SLICE-3D / ISIC 2024: Kurtansky et al., <em>Scientific Data</em> 11, 884 (2024), doi:10.1038/s41597-024-03743-w, CC BY / CC BY-NC / CC0 ${tr("je Bild", "per image")}.</p>
      <p>PAD-UFES-20: Pacheco et al., <em>Data in Brief</em> 32, 106221 (2020), CC BY 4.0. · SCIN: Ward et al. (2024), Google Research, SCIN Data Use License (${tr('nur zur Auswertung, Bilder werden nicht angezeigt', 'evaluation only, images are not displayed')}).</p>
      <p>${tr('Weil Teile der Trainingsdaten nur nicht-kommerziell genutzt werden dürfen, gilt das auch für das trainierte Modell. Der Code steht unter MIT-Lizenz.', 'Because parts of the training data may only be used non-commercially, the same applies to the trained model. The code is MIT-licensed.')}</p>
    </div>`)}
  </div>`);
  root.replaceChildren(view);
  return null;
}
