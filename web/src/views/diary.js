// Muttermal-Tagebuch: Hautstellen mit Fotoverlauf, Vergleich und Erinnerung – nur lokal.

import { tr, getLang } from '../lib/i18n.js';
import { el, esc, icon, pct, fmtDate } from '../lib/dom.js';
import * as store from '../lib/store.js';
import { blobToDataURL, dataURLToBlob } from '../lib/image.js';
import { zoneBadge, ZONE_CLASS } from '../components/zones.js';
import { siteLabel } from '../components/sites.js';

const RECHECK_DAYS = 90;

function daysSince(iso) {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
}

function sparkline(checks) {
  if (checks.length < 2) return '';
  const W = 120;
  const H = 32;
  const xs = checks.map((_, i) => (i / (checks.length - 1)) * (W - 8) + 4);
  const ys = checks.map((c) => H - 4 - c.percentile * (H - 8));
  const d = xs.map((x, i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join('');
  const dots = checks.map((c, i) => `<circle cx="${xs[i]}" cy="${ys[i]}" r="2.6" class="${ZONE_CLASS[c.zone]}" fill="var(--z)"/>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" class="h-8 w-28" aria-hidden="true"><path d="${d}" fill="none" stroke="var(--c-muted)" stroke-width="1.5"/>${dots}</svg>`;
}

export async function mount(root, { params }) {
  const urls = [];
  const urlOf = (blob) => {
    if (!blob) return '';
    const u = URL.createObjectURL(blob);
    urls.push(u);
    return u;
  };

  if (!(await store.available())) {
    root.replaceChildren(el(`<div class="card p-6"><p class="font-semibold">${tr('Tagebuch nicht verfügbar', 'Diary not available')}</p>
      <p class="mt-2 text-sm text-muted">${tr('Dein Browser erlaubt hier keinen lokalen Speicher (z. B. privates Fenster).', 'Your browser does not allow local storage here (e.g. private window).')}</p></div>`));
    return null;
  }

  if (params[0]) await renderSpot(decodeURIComponent(params[0]));
  else await renderList();

  async function renderList() {
    const spots = await store.listSpots();
    const all = await store.listChecks();
    const bySpot = new Map(spots.map((s) => [s.id, []]));
    all.forEach((c) => bySpot.get(c.spotId)?.push(c));
    bySpot.forEach((arr) => arr.sort((a, b) => a.date.localeCompare(b.date)));
    const lang = getLang();
    const due = spots.filter((s) => {
      const arr = bySpot.get(s.id);
      return arr.length && daysSince(arr[arr.length - 1].date) >= RECHECK_DAYS;
    });
    const cards = spots.sort((a, b) => a.name.localeCompare(b.name)).map((s) => {
      const arr = bySpot.get(s.id);
      const last = arr[arr.length - 1];
      const overdue = last && daysSince(last.date) >= RECHECK_DAYS;
      return `<a href="#/diary/${encodeURIComponent(s.id)}" class="card flex items-center gap-4 p-3 transition hover:border-accent">
        ${last ? `<img src="${urlOf(last.thumb)}" alt="" class="size-16 rounded-xl object-cover">` : `<div class="size-16 rounded-xl bg-surface-2"></div>`}
        <div class="min-w-0 flex-1">
          <p class="truncate font-semibold">${esc(s.name)}</p>
          <p class="text-xs text-muted">${esc(siteLabel(s.site, lang))} · ${arr.length} ${arr.length === 1 ? tr('Foto', 'photo') : tr('Fotos', 'photos')}
            ${last ? ` · ${tr('zuletzt', 'last')} ${fmtDate(last.date)}` : ''}</p>
          <div class="mt-1.5 flex flex-wrap items-center gap-2">${last ? zoneBadge(last.zone) : ''}
            ${overdue ? `<span class="chip bg-accent-soft text-accent">${icon('calendar', 'size-3')} ${tr('Kontrolle fällig', 'Check due')}</span>` : ''}</div>
        </div>
        <div class="hidden sm:block">${sparkline(arr)}</div>
      </a>`;
    }).join('');

    const view = el(`<div class="fade-in space-y-5">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div><h1 class="text-3xl font-bold tracking-tight">${tr('Muttermal-Tagebuch', 'Mole diary')}</h1>
        <p class="mt-1.5 max-w-2xl text-sm text-muted">${tr(
          'Hautärzte achten vor allem auf <strong>Veränderung</strong>. Lege deine Hautstellen an und mach etwa alle 3 Monate ein Foto unter ähnlichen Bedingungen. Alles bleibt auf diesem Gerät.',
          'Dermatologists look above all for <strong>change</strong>. Add your spots and take a photo about every 3 months under similar conditions. Everything stays on this device.')}</p></div>
        <a href="#/check" class="btn btn-primary">${icon('plus')} ${tr('Neue Hautstelle', 'New spot')}</a>
      </div>
      ${due.length ? `<div class="card flex items-center gap-3 p-4 text-sm">${icon('calendar', 'size-5 text-accent')}
        <span>${tr(`${due.length} Hautstelle(n) seit über ${RECHECK_DAYS} Tagen nicht fotografiert – Zeit für ein Vergleichsfoto.`,
          `${due.length} spot(s) not photographed for over ${RECHECK_DAYS} days – time for a comparison photo.`)}</span></div>` : ''}
      ${spots.length ? `<div class="grid gap-3 md:grid-cols-2">${cards}</div>` : `<div class="card p-8 text-center">
        <div class="mx-auto flex size-12 items-center justify-center rounded-full bg-accent-soft text-accent">${icon('book', 'size-6')}</div>
        <p class="mt-3 font-semibold">${tr('Noch keine Hautstellen gespeichert', 'No spots saved yet')}</p>
        <p class="mt-1 text-sm text-muted">${tr('Prüfe eine Hautstelle und speichere das Ergebnis – dann erscheint sie hier.', 'Check a spot and save the result – it will appear here.')}</p>
        <a href="#/check" class="btn btn-primary mt-4">${icon('camera')} ${tr('Erste Hautstelle prüfen', 'Check your first spot')}</a></div>`}
      <div class="card p-5 text-sm">
        <p class="font-semibold">${tr('Sicherung', 'Backup')}</p>
        <p class="mt-1 text-muted">${tr('Browserdaten können verloren gehen (z. B. beim Löschen des Verlaufs). Exportiere das Tagebuch gelegentlich als Datei.',
          'Browser data can be lost (e.g. when clearing history). Export the diary to a file now and then.')}</p>
        <div class="mt-3 flex flex-wrap gap-2">
          <button class="btn btn-ghost btn-sm" data-export>${icon('download')} ${tr('Exportieren', 'Export')}</button>
          <label class="btn btn-ghost btn-sm cursor-pointer">${icon('upload')} ${tr('Importieren', 'Import')}<input type="file" accept="application/json" class="sr-only" data-import></label>
        </div>
        <p class="mt-2 text-xs text-muted" data-io-msg></p>
      </div>
    </div>`);
    root.replaceChildren(view);
    view.querySelector('[data-export]').addEventListener('click', async () => {
      const data = await store.exportAll(blobToDataURL);
      const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `hautstellen-tagebuch-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });
    view.querySelector('[data-import]').addEventListener('change', async (e) => {
      const f = e.target.files?.[0];
      if (!f) return;
      const msg = view.querySelector('[data-io-msg]');
      try {
        const r = await store.importAll(JSON.parse(await f.text()), dataURLToBlob);
        msg.textContent = tr(`${r.spots} Hautstellen und ${r.checks} Fotos importiert.`, `Imported ${r.spots} spots and ${r.checks} photos.`);
        setTimeout(renderList, 800);
      } catch (err) {
        msg.textContent = tr('Import fehlgeschlagen: ', 'Import failed: ') + (err.message || err);
      }
    });
  }

  async function renderSpot(id) {
    const s = await store.getSpot(id);
    if (!s) { location.hash = '#/diary'; return; }
    const checks = await store.checksFor(id);
    const lang = getLang();
    const first = checks[0];
    const last = checks[checks.length - 1];
    let a = first;
    let b = last;

    const compare = () => (checks.length >= 2 ? `<div class="card p-5">
      <h2 class="font-semibold">${tr('Vergleich', 'Comparison')}</h2>
      <p class="mt-1 text-xs text-muted">${tr('Gleiche Bedingungen (Licht, Abstand, Winkel) machen Fotos vergleichbar. Achte auf Größe, Form und Farbe.',
        'Similar conditions (light, distance, angle) make photos comparable. Look at size, shape and color.')}</p>
      <div class="mt-4 grid grid-cols-2 gap-3">
        ${[['a', a], ['b', b]].map(([k, c]) => `<div>
          <select data-pick="${k}" class="mb-2 w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-sm">
            ${checks.map((x) => `<option value="${x.id}" ${x.id === c.id ? 'selected' : ''}>${fmtDate(x.date)}</option>`).join('')}</select>
          <img src="${urlOf(c.thumb)}" alt="" class="aspect-square w-full rounded-xl object-cover">
          <div class="mt-2 flex items-center justify-between text-sm">${zoneBadge(c.zone)}<span class="tabular text-muted">${pct(c.percentile)}</span></div>
        </div>`).join('')}
      </div>
      <div class="mt-5">
        <p class="text-sm font-medium">${tr('Überblenden', 'Blend')}</p>
        <div class="relative mt-2 overflow-hidden rounded-xl sm:max-w-xs">
          <img src="${urlOf(a.thumb)}" alt="" class="block aspect-square w-full object-cover">
          <img src="${urlOf(b.thumb)}" alt="" class="absolute inset-0 aspect-square w-full object-cover" style="opacity:.5" data-blend-img>
        </div>
        <input type="range" min="0" max="1" step="0.01" value="0.5" class="mt-2 w-full sm:max-w-xs" data-blend aria-label="${tr('Überblenden', 'Blend')}">
        <div class="flex justify-between text-xs text-muted sm:max-w-xs"><span>${fmtDate(a.date)}</span><span>${fmtDate(b.date)}</span></div>
      </div>
    </div>` : '');

    const timeline = checks.slice().reverse().map((c) => `<li class="flex items-center gap-3 py-2.5">
      <img src="${urlOf(c.thumb)}" alt="" class="size-12 rounded-lg object-cover">
      <div class="flex-1 text-sm"><p class="font-medium">${fmtDate(c.date, true)}</p>
        <p class="text-xs text-muted">${tr('Auffälligkeit', 'Conspicuousness')} ${pct(c.percentile)} · ${tr('Modell', 'model')} ${esc(c.modelVersion || '–')}
        ${c.quality?.some((q) => !q.ok) ? ` · ${icon('alert', 'size-3 inline -mt-0.5 text-zone-yellow')} ${tr('Bildqualität eingeschränkt', 'limited image quality')}` : ''}</p></div>
      ${zoneBadge(c.zone)}
      <button class="btn btn-ghost btn-sm" data-del-check="${c.id}" aria-label="${tr('Foto löschen', 'Delete photo')}">${icon('trash')}</button>
    </li>`).join('');

    const change = checks.length >= 2 ? last.percentile - first.percentile : 0;
    const view = el(`<div class="fade-in space-y-5">
      <a href="#/diary" class="inline-flex items-center gap-1 text-sm text-muted hover:text-fg">${icon('arrowLeft')} ${tr('Alle Hautstellen', 'All spots')}</a>
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div><h1 class="text-2xl font-bold tracking-tight">${esc(s.name)}</h1>
        <p class="text-sm text-muted">${esc(siteLabel(s.site, lang))} · ${tr('angelegt', 'created')} ${fmtDate(s.createdAt)}</p></div>
        <a class="btn btn-primary" href="#/check?spot=${encodeURIComponent(id)}">${icon('camera')} ${tr('Neues Foto', 'New photo')}</a>
      </div>
      ${checks.length >= 2 && change > 0.15 ? `<div class="card zone-yellow flex gap-3 p-4 text-sm">${icon('alert', 'size-5 shrink-0 zone-fg')}
        <span>${tr(`Die Auffälligkeit ist seit dem ersten Foto um ${Math.round(change * 100)} Prozentpunkte gestiegen. Das kann an unterschiedlichen Fotos liegen – oder an einer echten Veränderung. Im Zweifel ärztlich ansehen lassen.`,
          `Conspicuousness has risen by ${Math.round(change * 100)} percentage points since the first photo. This can be due to different photos – or a real change. If in doubt, have it checked.`)}</span></div>` : ''}
      ${compare()}
      <div class="card p-5"><h2 class="font-semibold">${tr('Verlauf', 'History')}</h2>
        ${checks.length >= 2 ? `<div class="mt-3">${trendChart(checks)}</div>` : ''}
        <ul class="mt-2 divide-y divide-[var(--c-border)]">${timeline || `<li class="py-3 text-sm text-muted">${tr('Noch keine Fotos.', 'No photos yet.')}</li>`}</ul></div>
      <button class="btn btn-ghost btn-sm text-zone-red" data-del-spot>${icon('trash')} ${tr('Hautstelle löschen', 'Delete spot')}</button>
    </div>`);
    root.replaceChildren(view);

    view.querySelectorAll('[data-pick]').forEach((sel) => sel.addEventListener('change', () => {
      const c = checks.find((x) => x.id === sel.value);
      if (sel.dataset.pick === 'a') a = c; else b = c;
      renderSpotKeep();
    }));
    view.querySelectorAll('[data-del-check]').forEach((btn) => btn.addEventListener('click', async () => {
      if (!confirm(tr('Dieses Foto löschen?', 'Delete this photo?'))) return;
      await store.deleteCheck(btn.dataset.delCheck);
      renderSpot(id);
    }));
    view.querySelector('[data-del-spot]').addEventListener('click', async () => {
      if (!confirm(tr(`„${s.name}“ mit allen Fotos löschen?`, `Delete “${s.name}” with all photos?`))) return;
      await store.deleteSpot(id);
      location.hash = '#/diary';
    });

    wireCompare(view);

    function wireCompare(scope) {
      scope.querySelector('[data-blend]')?.addEventListener('input', (e) => {
        scope.querySelector('[data-blend-img]').style.opacity = e.target.value;
      });
    }

    function renderSpotKeep() {
      const old = [...view.querySelectorAll('.card')].find((c) => c.querySelector('[data-pick]'));
      const fresh = el(compare());
      if (!old || !fresh) return;
      old.replaceWith(fresh);
      wireCompare(fresh);
      fresh.querySelectorAll('[data-pick]').forEach((sel) => sel.addEventListener('change', () => {
        const c = checks.find((x) => x.id === sel.value);
        if (sel.dataset.pick === 'a') a = c; else b = c;
        renderSpotKeep();
      }));
    }
  }

  function trendChart(checks) {
    const W = 600;
    const H = 140;
    const P = { l: 36, r: 10, t: 10, b: 22 };
    const t0 = new Date(checks[0].date).getTime();
    const t1 = Math.max(t0 + 1, new Date(checks[checks.length - 1].date).getTime());
    const x = (c) => P.l + ((new Date(c.date).getTime() - t0) / (t1 - t0)) * (W - P.l - P.r);
    const y = (v) => P.t + (1 - v) * (H - P.t - P.b);
    const path = checks.map((c, i) => `${i ? 'L' : 'M'}${x(c).toFixed(1)},${y(c.percentile).toFixed(1)}`).join('');
    const grid = [0, 0.5, 1].map((v) => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--c-grid)"/>
      <text x="${P.l - 6}" y="${y(v) + 4}" text-anchor="end" font-size="10" fill="var(--c-muted)">${Math.round(v * 100)}</text>`).join('');
    const dots = checks.map((c) => `<circle cx="${x(c)}" cy="${y(c.percentile)}" r="4.5" class="${ZONE_CLASS[c.zone]}" fill="var(--z)" stroke="var(--c-surface)" stroke-width="1.5"><title>${fmtDate(c.date)} · ${pct(c.percentile)}</title></circle>`).join('');
    return `<svg viewBox="0 0 ${W} ${H}" class="w-full" role="img" aria-label="${tr('Verlauf der Auffälligkeit', 'Conspicuousness over time')}">
      ${grid}<path d="${path}" fill="none" stroke="var(--c-accent)" stroke-width="2"/>${dots}
      <text x="${P.l}" y="${H - 4}" font-size="10" fill="var(--c-muted)">${fmtDate(checks[0].date)}</text>
      <text x="${W - P.r}" y="${H - 4}" font-size="10" text-anchor="end" fill="var(--c-muted)">${fmtDate(checks[checks.length - 1].date)}</text></svg>`;
  }

  return { destroy() { urls.forEach((u) => URL.revokeObjectURL(u)); } };
}
