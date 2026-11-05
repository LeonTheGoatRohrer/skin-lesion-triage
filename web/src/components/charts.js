// Schlanke SVG-Diagramme (keine Chart-Bibliothek). Farben kommen aus CSS-Variablen.

import { esc, fmt, pct } from '../lib/dom.js';

/** ROC-Kurven: series = [{ label, color, fpr[], tpr[], auc }] */
export function rocChart(series, { xLabel = 'FPR', yLabel = 'TPR', title = '' } = {}) {
  const W = 360;
  const H = 300;
  const P = { l: 40, r: 12, t: 12, b: 36 };
  const x = (v) => P.l + v * (W - P.l - P.r);
  const y = (v) => P.t + (1 - v) * (H - P.t - P.b);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const grid = ticks.map((v) => `
    <line x1="${x(v)}" x2="${x(v)}" y1="${y(0)}" y2="${y(1)}" stroke="var(--c-grid)"/>
    <line x1="${x(0)}" x2="${x(1)}" y1="${y(v)}" y2="${y(v)}" stroke="var(--c-grid)"/>
    <text x="${x(v)}" y="${H - P.b + 14}" font-size="10" text-anchor="middle" fill="var(--c-muted)">${fmt(v, 2)}</text>
    <text x="${P.l - 6}" y="${y(v) + 3}" font-size="10" text-anchor="end" fill="var(--c-muted)">${fmt(v, 2)}</text>`).join('');
  const lines = series.map((s) => {
    const d = s.fpr.map((f, i) => `${i ? 'L' : 'M'}${x(f).toFixed(1)},${y(s.tpr[i]).toFixed(1)}`).join('');
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.2" stroke-linejoin="round"><title>${esc(s.label)}</title></path>`;
  }).join('');
  const legend = series.map((s) => `<li class="flex items-center gap-2"><span class="h-0.5 w-4 rounded" style="background:${s.color}"></span>
    <span>${esc(s.label)}</span><span class="ml-auto tabular text-muted">${s.auc != null ? fmt(s.auc, 3) : ''}</span></li>`).join('');
  return `<figure>
    <svg viewBox="0 0 ${W} ${H}" class="w-full max-w-md" role="img" aria-label="${esc(title || 'ROC')}">
      ${grid}
      <line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="var(--c-muted)" stroke-dasharray="4 4" opacity=".6"/>
      ${lines}
      <text x="${(P.l + W - P.r) / 2}" y="${H - 4}" font-size="11" text-anchor="middle" fill="var(--c-muted)">${esc(xLabel)}</text>
      <text transform="translate(11 ${(P.t + H - P.b) / 2}) rotate(-90)" font-size="11" text-anchor="middle" fill="var(--c-muted)">${esc(yLabel)}</text>
    </svg>
    <ul class="mt-2 max-w-md space-y-1 text-xs">${legend}</ul>
  </figure>`;
}

/** Gestapelte Balken je Zeile: rows = [{ label, n, parts: [{ value 0..1, color, label }] }] */
export function stackedBars(rows) {
  return `<div class="space-y-3">${rows.map((r) => `
    <div>
      <div class="flex justify-between text-xs"><span class="font-medium">${esc(r.label)}</span><span class="text-muted">n = ${fmt(r.n)}</span></div>
      <div class="mt-1 flex h-6 overflow-hidden rounded-lg" role="img" aria-label="${esc(r.label)}: ${r.parts.map((p) => `${p.label} ${pct(p.value)}`).join(', ')}">
        ${r.parts.map((p) => `<div class="flex items-center justify-center text-[10px] font-semibold text-white"
          style="width:${p.value * 100}%;background:${p.color}" title="${esc(p.label)} ${pct(p.value, 1)}">${p.value >= 0.08 ? pct(p.value) : ''}</div>`).join('')}
      </div></div>`).join('')}</div>`;
}

/** Horizontale Balken: rows = [{ label, value 0..1, note, color }] */
export function hBars(rows, { max = 1, format = (v) => pct(v) } = {}) {
  return `<div class="space-y-2.5">${rows.map((r) => `
    <div class="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-xs">
      <span class="truncate" title="${esc(r.label)}">${esc(r.label)}</span>
      <div class="h-2.5 rounded-full bg-surface-2"><div class="h-2.5 rounded-full" style="width:${Math.max(1, (r.value ?? 0) / max * 100)}%;background:${r.color || 'var(--c-accent)'}"></div></div>
      <span class="tabular text-muted">${r.value == null ? '–' : format(r.value)}${r.note ? ` <span class="opacity-70">${esc(r.note)}</span>` : ''}</span>
    </div>`).join('')}</div>`;
}

/** Linien über Epochen: series = [{ label, color, values[] }] */
export function lineChart(series, { yMin = 0.5, yMax = 1, xLabel = '', yLabel = '' } = {}) {
  const W = 420;
  const H = 220;
  const P = { l: 40, r: 12, t: 10, b: 32 };
  const n = Math.max(...series.map((s) => s.values.length));
  const x = (i) => P.l + (n <= 1 ? 0.5 : i / (n - 1)) * (W - P.l - P.r);
  const y = (v) => P.t + (1 - (v - yMin) / (yMax - yMin)) * (H - P.t - P.b);
  const ticks = [];
  for (let v = yMin; v <= yMax + 1e-9; v += (yMax - yMin) / 4) ticks.push(v);
  const grid = ticks.map((v) => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--c-grid)"/>
    <text x="${P.l - 6}" y="${y(v) + 3}" font-size="10" text-anchor="end" fill="var(--c-muted)">${fmt(v, 2)}</text>`).join('');
  const xt = Array.from({ length: n }, (_, i) => `<text x="${x(i)}" y="${H - P.b + 14}" font-size="10" text-anchor="middle" fill="var(--c-muted)">${i + 1}</text>`).join('');
  const lines = series.map((s) => `<path d="${s.values.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join('')}" fill="none" stroke="${s.color}" stroke-width="2"/>
    ${s.values.map((v, i) => `<circle cx="${x(i)}" cy="${y(v)}" r="2.5" fill="${s.color}"><title>${esc(s.label)} ${fmt(v, 3)}</title></circle>`).join('')}`).join('');
  return `<figure><svg viewBox="0 0 ${W} ${H}" class="w-full max-w-lg" role="img" aria-label="${esc(yLabel)}">${grid}${xt}${lines}
    <text x="${(P.l + W - P.r) / 2}" y="${H - 3}" font-size="11" text-anchor="middle" fill="var(--c-muted)">${esc(xLabel)}</text></svg>
    <ul class="mt-1 flex flex-wrap gap-4 text-xs">${series.map((s) => `<li class="flex items-center gap-2"><span class="h-0.5 w-4" style="background:${s.color}"></span>${esc(s.label)}</li>`).join('')}</ul></figure>`;
}
