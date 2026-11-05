// Hauptansicht: Foto -> Ausschnitt -> Analyse -> Ergebnis.

import { tr, getLang } from '../lib/i18n.js';
import { el, esc, icon, pct, fmtDate } from '../lib/dom.js';
import { loadBitmap, renderCrop, canvasToCHW, canvasToBlob } from '../lib/image.js';
import { loadMeta, loadModel, runModel, zoneOf, percentileOf, occlusionMap } from '../lib/model.js';
import { qualityFeatures, qualityChecks } from '../lib/quality.js';
import * as store from '../lib/store.js';
import { createCropper } from '../components/cropper.js';
import { ZONE_CLASS, zoneTitle, zoneAdvice, zoneIcon, zoneEvidence, redFlagsCard } from '../components/zones.js';
import { BODY_SITES, siteLabel } from '../components/sites.js';

const BASE = import.meta.env.BASE_URL;

export async function mount(root, { query }) {
  const spotId = query.get('spot');
  const spot = spotId ? await store.getSpot(spotId).catch(() => null) : null;
  let meta = null;
  let cropper = null;
  let bitmap = null;
  let example = null;
  let modelState = { ready: false, progress: 0, error: null };

  const statusLine = el('<p class="mt-3 flex items-center gap-2 text-xs text-muted" aria-live="polite"></p>');
  function paintStatus() {
    if (modelState.error) {
      statusLine.innerHTML = `${icon('alert', 'size-3.5 text-zone-red')} ${tr('Modell konnte nicht geladen werden', 'Model could not be loaded')}: ${esc(modelState.error)}`;
    } else if (modelState.ready) {
      statusLine.innerHTML = `${icon('checkCircle', 'size-3.5 text-zone-green')} ${tr('Modell bereit – läuft komplett auf deinem Gerät', 'Model ready – runs entirely on your device')}`;
    } else {
      statusLine.innerHTML = `<span class="spinner text-accent" style="width:.8rem;height:.8rem"></span> ${tr('Modell wird geladen', 'Loading model')} … ${pct(modelState.progress)}`;
    }
  }
  paintStatus();

  Promise.all([loadMeta(), loadModel((p) => { modelState.progress = p; paintStatus(); })])
    .then(([m]) => { meta = m; modelState.ready = true; paintStatus(); })
    .catch((e) => { modelState.error = e.message || String(e); paintStatus(); });

  // ---------- Schritt 1: Foto wählen --------------------------------------------------
  async function showStart() {
    cropper?.destroy();
    example = null;
    const examples = await fetch(`${BASE}examples/examples.json`).then((r) => r.json()).catch(() => []);
    const view = el(`<div class="fade-in space-y-6">
      <section class="grid gap-6 md:grid-cols-[1.15fr_1fr] md:items-start">
        <div data-left>
          ${spot ? `<p class="chip mb-3 bg-accent-soft text-accent">${icon('book', 'size-3.5')} ${tr('Neues Foto für', 'New photo for')}: ${esc(spot.name)}</p>` : ''}
          <h1 class="text-3xl font-bold tracking-tight md:text-4xl">${tr('Hautstelle prüfen', 'Check a skin spot')}</h1>
          <p class="mt-3 text-[15px] leading-relaxed text-muted">${tr(
            'Fotografiere ein Muttermal oder eine Hautstelle. Ein neuronales Netz, trainiert auf rund 48 000 Bildern aus dem öffentlichen ISIC-Archiv, schätzt ein, wie auffällig die Stelle aussieht – als Ampel und als Prozentzahl. Alles passiert in deinem Browser.',
            'Take a photo of a mole or skin spot. A neural network trained on about 48,000 images from the public ISIC archive estimates how conspicuous the spot looks – as a traffic light and a percentage. Everything happens in your browser.')}</p>
          <div class="mt-6 flex flex-wrap gap-3">
            <label class="btn btn-primary cursor-pointer">${icon('camera', 'size-5')} ${tr('Foto aufnehmen', 'Take photo')}
              <input type="file" accept="image/*" capture="environment" class="sr-only" data-input></label>
            <label class="btn btn-ghost cursor-pointer">${icon('image', 'size-5')} ${tr('Bild auswählen', 'Choose image')}
              <input type="file" accept="image/*" class="sr-only" data-input></label>
          </div>
        </div>
        <div class="card p-5">
          <h2 class="font-semibold">${tr('So gelingt das Foto', 'How to take a good photo')}</h2>
          <ul class="mt-3 space-y-2.5 text-sm text-muted">
            ${[
              ['sun', tr('Helles Tageslicht, kein Blitz, keine Schatten', 'Bright daylight, no flash, no shadows')],
              ['scan', tr('10–15 cm Abstand, auf die Stelle scharf stellen (antippen)', '10–15 cm away, tap to focus on the spot')],
              ['camera', tr('Handy parallel zur Haut halten, Stelle in die Bildmitte', 'Hold the phone parallel to the skin, spot in the center')],
              ['x', tr('Keine Filter, kein Zoom-Digitalbild, Haare möglichst zur Seite', 'No filters or digital zoom, move hair aside if possible')],
            ].map(([ic, t]) => `<li class="flex gap-3">${icon(ic, 'size-5 shrink-0 text-accent')}<span>${t}</span></li>`).join('')}
          </ul>
        </div>
      </section>
      ${examples.length ? `<section>
        <h2 class="text-sm font-semibold">${tr('Kein Foto zur Hand? Beispiel ausprobieren', 'No photo at hand? Try an example')}</h2>
        <p class="mt-1 text-xs text-muted">${tr('Zufällig ausgewählte Smartphone-Fotos aus PAD-UFES-20 (CC BY 4.0). Die echte Diagnose siehst du nach der Analyse.',
          'Randomly selected smartphone photos from PAD-UFES-20 (CC BY 4.0). You will see the real diagnosis after the analysis.')}</p>
        <div class="mt-3 grid grid-cols-4 gap-2 sm:gap-3 md:max-w-xl">
          ${examples.map((ex, i) => `<button class="group overflow-hidden rounded-xl border border-line" data-example="${i}" aria-label="${tr('Beispiel', 'Example')} ${i + 1}">
            <img src="${BASE}examples/${esc(ex.file)}" alt="" class="aspect-square w-full object-cover transition group-hover:scale-105" loading="lazy"></button>`).join('')}
        </div></section>` : ''}
      <section class="card flex gap-4 p-5 text-sm">
        ${icon('shield', 'size-6 shrink-0 text-accent')}
        <div><p class="font-semibold">${tr('Privat by Design', 'Private by design')}</p>
        <p class="mt-1 text-muted">${tr('Kein Upload, kein Konto, kein Tracking. Das Modell wird einmal geladen und rechnet danach lokal – auch offline. Gespeicherte Fotos liegen nur in deinem Browser. Tipp: Über „Zum Startbildschirm hinzufügen“ im Browser-Menü wird daraus eine App.',
          'No upload, no account, no tracking. The model is downloaded once and then computes locally – even offline. Saved photos stay in your browser only. Tip: use “Add to Home Screen” in your browser menu to install it as an app.')}</p></div>
      </section>
    </div>`);
    view.querySelector('[data-left]').append(statusLine);
    view.querySelectorAll('[data-input]').forEach((inp) => inp.addEventListener('change', async () => {
      const f = inp.files?.[0];
      if (f) await startCrop(f);
    }));
    view.querySelectorAll('[data-example]').forEach((b) => b.addEventListener('click', async () => {
      const ex = examples[Number(b.dataset.example)];
      const blob = await fetch(`${BASE}examples/${ex.file}`).then((r) => r.blob());
      await startCrop(blob, ex);
    }));
    root.replaceChildren(view);
  }

  // ---------- Schritt 2: Ausschnitt ---------------------------------------------------
  async function startCrop(fileOrBlob, ex = null) {
    example = ex;
    try {
      bitmap = await loadBitmap(fileOrBlob);
    } catch {
      alert(tr('Dieses Bild konnte nicht geöffnet werden.', 'This image could not be opened.'));
      return;
    }
    const view = el(`<div class="fade-in mx-auto max-w-md space-y-4">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">${tr('Ausschnitt wählen', 'Choose the area')}</h1>
        <p class="mt-1.5 text-sm text-muted">${tr('Schiebe die Hautstelle in die Mitte und zoome, bis sie ungefähr den gestrichelten Kreis ausfüllt. Etwas umgebende Haut soll sichtbar bleiben.',
          'Move the spot to the center and zoom until it roughly fills the dashed circle. Keep some surrounding skin visible.')}</p>
      </div>
      <div class="cropper aspect-square w-full shadow-lg" data-crop aria-label="${tr('Ausschnitt: ziehen zum Verschieben, Mausrad oder zwei Finger zum Zoomen', 'Crop: drag to move, scroll or pinch to zoom')}"></div>
      <div class="flex items-center gap-3">
        <button class="btn btn-ghost btn-sm" data-zoom="out" aria-label="${tr('Herauszoomen', 'Zoom out')}">${icon('zoomOut')}</button>
        <input type="range" min="0" max="1" step="0.001" class="flex-1" data-slider aria-label="Zoom">
        <button class="btn btn-ghost btn-sm" data-zoom="in" aria-label="${tr('Hineinzoomen', 'Zoom in')}">${icon('zoomIn')}</button>
      </div>
      <div class="flex gap-3">
        <button class="btn btn-ghost" data-back>${icon('arrowLeft')} ${tr('Anderes Foto', 'Other photo')}</button>
        <button class="btn btn-primary flex-1" data-go>${icon('sparkles')} ${tr('Analysieren', 'Analyze')}</button>
      </div>
    </div>`);
    root.replaceChildren(view);
    const slider = view.querySelector('[data-slider]');
    cropper?.destroy();
    cropper = createCropper(view.querySelector('[data-crop]'), bitmap, {
      onChange: () => { slider.value = String(cropper?.getZoom() ?? 0); },
    });
    if (ex?.crop) cropper.setZoom(ex.crop);
    slider.value = String(cropper.getZoom());
    slider.addEventListener('input', () => cropper.setZoom(Number(slider.value)));
    view.querySelector('[data-zoom="in"]').addEventListener('click', () => cropper.zoomBy(1.2));
    view.querySelector('[data-zoom="out"]').addEventListener('click', () => cropper.zoomBy(1 / 1.2));
    view.querySelector('[data-back]').addEventListener('click', showStart);
    view.querySelector('[data-go]').addEventListener('click', analyze);
    window.scrollTo(0, 0);
  }

  // ---------- Schritt 3: Analyse ------------------------------------------------------
  async function analyze() {
    const crop = cropper.getCrop();
    root.replaceChildren(el(`<div class="fade-in flex flex-col items-center gap-4 py-24 text-muted">
      <span class="spinner text-accent" style="width:2rem;height:2rem"></span>
      <p>${tr('Analysiere – auf deinem Gerät …', 'Analyzing – on your device …')}</p></div>`));
    try {
      await loadModel();
      meta = meta || await loadMeta();
      const size = meta.image_size;
      const input = renderCrop(bitmap, crop, size);
      const chw = canvasToCHW(input);
      const [res] = await runModel(chw, 1, size);
      const thumbCanvas = renderCrop(bitmap, crop, 320);
      const result = {
        ...res,
        zone: zoneOf(res.score, meta),
        percentile: percentileOf(res.score, meta),
        quality: qualityChecks(qualityFeatures(chw, size), meta.quality, res.ood, meta.ood_threshold),
        chw,
        thumbCanvas,
        date: new Date().toISOString(),
      };
      showResult(result);
    } catch (e) {
      console.error(e);
      root.replaceChildren(el(`<div class="card p-6"><p class="font-semibold">${tr('Analyse fehlgeschlagen', 'Analysis failed')}</p>
        <p class="mt-2 text-sm text-muted">${esc(e.message || e)}</p><button class="btn btn-ghost mt-4" data-back>${tr('Zurück', 'Back')}</button></div>`));
      root.querySelector('[data-back]').addEventListener('click', showStart);
    }
  }

  function qualityList(q) {
    const names = {
      sharpness: [tr('Schärfe', 'Sharpness'), tr('Foto wirkt unscharf – neu fokussieren oder ruhiger halten.', 'Photo looks blurry – refocus or hold steadier.')],
      exposure: [tr('Belichtung', 'Exposure'), tr('Zu dunkel oder überbelichtet – Tageslicht ohne Blitz nutzen.', 'Too dark or overexposed – use daylight without flash.')],
      familiar: [tr('Bildinhalt', 'Image content'), tr('Sieht nicht aus wie die Hautstellen-Fotos aus dem Training (z. B. kein Hautausschnitt, Ausschlag, Tattoo oder sehr ungewöhnliche Aufnahme).',
        'Does not look like the skin spot photos used in training (e.g. no skin close-up, a rash, a tattoo or a very unusual shot).')],
    };
    return q.map((c) => `<li class="flex items-start gap-2">
      ${c.ok ? icon('checkCircle', 'size-4 mt-0.5 shrink-0 text-zone-green') : icon('alert', 'size-4 mt-0.5 shrink-0 text-zone-yellow')}
      <span><span class="font-medium text-fg">${names[c.key][0]}</span>${c.ok ? '' : ` – ${names[c.key][1]}`}</span></li>`).join('');
  }

  function meter(result) {
    const pLow = percentileOf(meta.rule.t_low, meta);
    const pHigh = percentileOf(meta.rule.t_high, meta);
    const p = result.percentile;
    const shown = p >= 0.995 ? `> ${pct(0.99)}` : p <= 0.005 ? `< ${pct(0.01)}` : pct(p);
    return `<div class="mt-5">
      <div class="flex items-baseline justify-between">
        <span class="text-sm font-medium">${tr('Auffälligkeit', 'Conspicuousness')}</span>
        <span class="text-2xl font-bold tabular">${shown}</span>
      </div>
      <div class="relative mt-2 h-3 overflow-hidden rounded-full" role="img" aria-label="${tr('Auffälligkeit', 'Conspicuousness')} ${pct(p)}">
        <div class="absolute inset-y-0 left-0 bg-zone-green" style="width:${pLow * 100}%;opacity:.75"></div>
        <div class="absolute inset-y-0 bg-zone-yellow" style="left:${pLow * 100}%;width:${(pHigh - pLow) * 100}%;opacity:.75"></div>
        <div class="absolute inset-y-0 right-0 bg-zone-red" style="left:${pHigh * 100}%;opacity:.75"></div>
      </div>
      <div class="relative h-4"><div class="absolute -top-1 -translate-x-1/2 text-fg" style="left:${Math.min(98.5, Math.max(1.5, p * 100))}%">▲</div></div>
      <p class="text-sm text-muted">${tr(
        `Auffälliger als <strong class="text-fg">${shown}</strong> der gutartigen Vergleichsfotos aus dem Validierungs-Datensatz.`,
        `More conspicuous than <strong class="text-fg">${shown}</strong> of benign reference photos from the validation set.`)}
        <button class="underline decoration-dotted" data-why>${tr('Warum keine Krebs-Wahrscheinlichkeit?', 'Why no cancer probability?')}</button></p>
      <p class="mt-2 hidden rounded-lg bg-surface-2 p-3 text-xs leading-relaxed text-muted" data-why-text>${tr(
        'Eine „Krebs-Wahrscheinlichkeit“ hängt davon ab, wie häufig Krebs unter den fotografierten Stellen ist: In Hautkliniken ist jede zweite Stelle bösartig, unter allen Muttermalen im Alltag ist es ein winziger Bruchteil. Dieselbe Zahl wäre also je nach Situation falsch. Der Vergleich mit gutartigen Hautstellen bleibt dagegen in jeder Situation richtig.',
        'A “cancer probability” depends on how common cancer is among the spots being photographed: in skin clinics every second spot is malignant, among all everyday moles it is a tiny fraction. The same number would be wrong depending on the situation. The comparison with benign spots stays correct in every situation.')}</p>
    </div>`;
  }

  function groupBars(probs) {
    const lang = getLang();
    const order = probs.map((p, i) => [p, i]).sort((a, b) => b[0] - a[0]).slice(0, 3);
    return `<div class="card p-5">
      <h3 class="font-semibold">${tr('Ähnlichkeit zu Diagnose-Gruppen', 'Similarity to diagnosis groups')}</h3>
      <p class="mt-1 text-xs text-muted">${tr('Wem sieht das Foto am ähnlichsten? Das ist keine Diagnose und keine Wahrscheinlichkeit.', 'What does the photo resemble most? This is not a diagnosis or a probability.')}</p>
      <div class="mt-4 space-y-3">${order.map(([p, i]) => {
        const g = meta.groups[i];
        const color = g.kind === 'malignant' ? 'var(--c-red)' : g.kind === 'precursor' ? 'var(--c-yellow)' : 'var(--c-green)';
        return `<div><div class="flex justify-between text-sm"><span>${esc(g[lang] || g.de)}</span><span class="tabular text-muted">${pct(p)}</span></div>
          <div class="mt-1 h-2 rounded-full bg-surface-2"><div class="h-2 rounded-full" style="width:${Math.max(2, p * 100)}%;background:${color}"></div></div></div>`;
      }).join('')}</div>
    </div>`;
  }

  function showResult(result) {
    const unsure = result.quality.some((c) => !c.ok && c.key === 'familiar');
    const otherIssues = result.quality.some((c) => !c.ok && c.key !== 'familiar');
    const z = result.zone;
    const imgUrl = result.thumbCanvas.toDataURL('image/jpeg', 0.9);
    const exInfo = example ? `<div class="card p-5 text-sm">
        <p class="font-semibold">${tr('Auflösung zum Beispielbild', 'About this example')}</p>
        <p class="mt-1 text-muted">${tr('Tatsächliche Diagnose', 'Actual diagnosis')}: <strong class="text-fg">${esc(example[getLang()] || example.de)}</strong>
        (${esc(getLang() === 'en' ? example.confirm_en : example.confirm)}). ${tr('Quelle', 'Source')}: PAD-UFES-20, ${esc(example.isic_id)}, CC BY 4.0, ${esc(example.attribution)}.</p></div>` : '';
    const resultCard = `<div class="card overflow-hidden ${ZONE_CLASS[z]}">
        <div class="zone-bg flex items-center gap-3 px-5 py-4">${zoneIcon(z)}
          <div><p class="text-xs font-semibold uppercase tracking-wide opacity-80">${tr('Einschätzung', 'Assessment')}</p>
          <p class="text-xl font-bold">${zoneTitle(z)}</p></div></div>
        <div class="p-5">
          <p class="text-[15px] leading-relaxed prose-s">${zoneAdvice(z)}</p>
          ${meter(result)}
          <p class="mt-4 text-xs leading-relaxed text-muted">${zoneEvidence(z, meta.zone_stats)}</p>
        </div></div>`;
    const view = el(`<div class="fade-in space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h1 class="text-2xl font-bold tracking-tight">${tr('Ergebnis', 'Result')}</h1>
        <span class="text-xs text-muted">${fmtDate(result.date, true)} · ${tr('Modell', 'Model')} ${esc(meta.version)}</span>
      </div>
      <div class="grid gap-5 md:grid-cols-[minmax(0,320px)_1fr]">
        <div class="order-2 mx-auto w-full max-w-sm space-y-3 md:order-1 md:max-w-none">
          <div class="relative overflow-hidden rounded-2xl border border-line">
            <img src="${imgUrl}" alt="${tr('Analysierter Ausschnitt', 'Analyzed crop')}" class="block aspect-square w-full">
            <canvas class="pointer-events-none absolute inset-0 hidden size-full" data-heat></canvas>
          </div>
          <button class="btn btn-ghost btn-sm w-full" data-occ>${icon('eye')} ${tr('Wohin schaut das Modell?', 'Where does the model look?')}</button>
          <p class="hidden text-xs text-muted" data-occ-note>${tr('Rot markiert: Bereiche, deren Abdecken die Auffälligkeit am stärksten senkt.', 'Red: areas whose masking lowers the score the most.')}</p>
          <div class="card p-4"><p class="text-sm font-semibold">${tr('Bildprüfung', 'Image check')}</p>
            <ul class="mt-2 space-y-1.5 text-sm text-muted">${qualityList(result.quality)}</ul></div>
        </div>
        <div class="order-1 space-y-5 md:order-2">
          ${unsure ? `<div class="card zone-grey p-5"><div class="flex gap-3">${icon('alert', 'size-6 shrink-0 text-zone-yellow')}
            <div><p class="font-semibold">${tr('Foto nicht zuverlässig beurteilbar', 'Photo cannot be assessed reliably')}</p>
            <p class="mt-1 text-sm text-muted">${tr('Das Bild unterscheidet sich stark von den Trainingsbildern. Für Ausschläge, Tattoos, Narben oder Fotos ohne einzelne Hautstelle ist das Modell nicht gemacht. Versuche eine Nahaufnahme einer einzelnen Stelle.',
              'The image differs strongly from the training images. The model is not made for rashes, tattoos, scars or photos without a single spot. Try a close-up of a single spot.')}</p>
            <button class="btn btn-ghost btn-sm mt-3" data-show-anyway>${tr('Ergebnis trotzdem anzeigen', 'Show result anyway')}</button></div></div></div>` : ''}
          ${otherIssues && !unsure ? `<div class="card p-4 text-sm text-muted">${icon('alert', 'size-4 inline -mt-0.5 text-zone-yellow')} ${tr('Die Bildqualität ist eingeschränkt – das Ergebnis ist unsicherer. Am besten ein neues Foto machen.', 'Image quality is limited – the result is less reliable. Best take a new photo.')}</div>` : ''}
          <div data-result class="${unsure ? 'hidden' : ''} space-y-5">${resultCard}${groupBars(result.probs)}</div>
          ${exInfo}
          <div class="card p-5" data-save-box>
            <h3 class="flex items-center gap-2 font-semibold">${icon('book', 'size-5 text-accent')} ${tr('Im Tagebuch speichern', 'Save to diary')}</h3>
            <p class="mt-1 text-sm text-muted">${tr('Veränderung ist das wichtigste Warnzeichen. Speichere die Stelle und mach regelmäßig ein Vergleichsfoto – nur lokal auf diesem Gerät.',
              'Change is the most important warning sign. Save the spot and take a comparison photo regularly – stored only on this device.')}</p>
            <div class="mt-3" data-save-form></div>
          </div>
          <div class="flex flex-wrap gap-3">
            <button class="btn btn-ghost" data-again>${icon('camera')} ${tr('Neues Foto', 'New photo')}</button>
            <button class="btn btn-ghost" data-recrop>${icon('scan')} ${tr('Ausschnitt ändern', 'Change crop')}</button>
          </div>
          ${redFlagsCard()}
        </div>
      </div>
    </div>`);
    root.replaceChildren(view);
    window.scrollTo(0, 0);

    view.querySelector('[data-why]')?.addEventListener('click', () => view.querySelector('[data-why-text]').classList.toggle('hidden'));
    view.querySelector('[data-show-anyway]')?.addEventListener('click', (e) => {
      view.querySelector('[data-result]').classList.remove('hidden');
      e.currentTarget.remove();
    });
    view.querySelector('[data-again]').addEventListener('click', showStart);
    view.querySelector('[data-recrop]').addEventListener('click', () => startCropFromBitmap());
    view.querySelector('[data-occ]').addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner"></span> ${tr('Berechne …', 'Computing …')}`;
      const grid = 6;
      const map = await occlusionMap(result.chw, meta.image_size, result.score, grid,
        (p) => { btn.innerHTML = `<span class="spinner"></span> ${tr('Berechne …', 'Computing …')} ${pct(p)}`; });
      drawHeat(view.querySelector('[data-heat]'), map, grid);
      btn.innerHTML = `${icon('eye')} ${tr('Heatmap ein/aus', 'Toggle heatmap')}`;
      btn.disabled = false;
      view.querySelector('[data-occ-note]').classList.remove('hidden');
      btn.onclick = (ev) => { ev.stopImmediatePropagation(); view.querySelector('[data-heat]').classList.toggle('hidden'); };
    }, { once: true });
    renderSaveForm(view.querySelector('[data-save-form]'), result);
  }

  function drawHeat(canvas, map, grid) {
    const max = Math.max(1e-6, ...map);
    const S = 240;
    canvas.width = S;
    canvas.height = S;
    const g = canvas.getContext('2d');
    // kleines Bild mit grid×grid Pixeln, weich hochskaliert
    const small = document.createElement('canvas');
    small.width = grid;
    small.height = grid;
    const sg = small.getContext('2d');
    const img = sg.createImageData(grid, grid);
    for (let i = 0; i < grid * grid; i++) {
      const v = Math.max(0, map[i]) / max;
      img.data[i * 4] = 244;
      img.data[i * 4 + 1] = 63;
      img.data[i * 4 + 2] = 94;
      img.data[i * 4 + 3] = Math.round(200 * v);
    }
    sg.putImageData(img, 0, 0);
    g.imageSmoothingEnabled = true;
    g.imageSmoothingQuality = 'high';
    g.drawImage(small, 0, 0, S, S);
    canvas.classList.remove('hidden');
  }

  async function renderSaveForm(host, result) {
    const spots = await store.listSpots().catch(() => null);
    if (spots === null) {
      host.innerHTML = `<p class="text-sm text-muted">${tr('Speichern ist in diesem Browser-Modus nicht möglich (z. B. privates Fenster).', 'Saving is not possible in this browser mode (e.g. private window).')}</p>`;
      return;
    }
    const lang = getLang();
    const preselect = spot?.id || '';
    host.innerHTML = `<form class="grid gap-3 sm:grid-cols-2">
      <label class="text-sm sm:col-span-2">${tr('Hautstelle', 'Spot')}
        <select name="spot" class="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2">
          <option value="">${tr('+ Neue Hautstelle anlegen', '+ Create new spot')}</option>
          ${spots.map((s) => `<option value="${esc(s.id)}" ${s.id === preselect ? 'selected' : ''}>${esc(s.name)} (${esc(siteLabel(s.site, lang))})</option>`).join('')}
        </select></label>
      <label class="text-sm" data-new>${tr('Name', 'Name')}
        <input name="name" required maxlength="60" placeholder="${tr('z. B. Muttermal linke Schulter', 'e.g. mole left shoulder')}" class="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2"></label>
      <label class="text-sm" data-new>${tr('Körperstelle', 'Body site')}
        <select name="site" class="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2">
          ${BODY_SITES.map((s) => `<option value="${s.id}">${esc(s[lang])}</option>`).join('')}</select></label>
      <button class="btn btn-primary sm:col-span-2" type="submit">${icon('plus')} ${tr('Speichern', 'Save')}</button>
    </form>`;
    const form = host.querySelector('form');
    const toggle = () => {
      const isNew = !form.spot.value;
      form.querySelectorAll('[data-new]').forEach((n) => n.classList.toggle('hidden', !isNew));
      form.name.required = isNew;
    };
    form.spot.addEventListener('change', toggle);
    toggle();
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      let id = form.spot.value;
      if (!id) {
        id = store.uid();
        await store.putSpot({ id, name: form.name.value.trim(), site: form.site.value, createdAt: new Date().toISOString() });
      }
      const thumb = await canvasToBlob(result.thumbCanvas);
      await store.putCheck({
        id: store.uid(), spotId: id, date: result.date, thumb, score: result.score, percentile: result.percentile,
        zone: result.zone, probs: result.probs, ood: result.ood,
        quality: result.quality.map(({ key, ok }) => ({ key, ok })), modelVersion: meta.version,
      });
      host.innerHTML = `<p class="flex items-center gap-2 text-sm">${icon('checkCircle', 'size-5 text-zone-green')} ${tr('Gespeichert.', 'Saved.')}
        <a class="font-semibold text-accent underline" href="#/diary/${encodeURIComponent(id)}">${tr('Zum Tagebuch', 'Open diary')}</a></p>`;
    });
  }

  function startCropFromBitmap() {
    if (!bitmap) return showStart();
    const ex = example;
    // gleiches Bild erneut zuschneiden
    const c = document.createElement('canvas');
    c.width = bitmap.width;
    c.height = bitmap.height;
    c.getContext('2d').drawImage(bitmap, 0, 0);
    c.toBlob((b) => startCrop(b, ex), 'image/png');
  }

  await showStart();
  return { destroy() { cropper?.destroy(); } };
}
