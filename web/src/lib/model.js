// Modell im Browser (onnxruntime-web, WebAssembly). Das Foto verlässt das Gerät nie.
// Die .wasm-Datei bündelt Vite als Asset mit (kein CDN).
//
// Das ONNX-Netz erwartet RGB-Werte in [0,1], Form [N,3,S,S]; Normalisierung und
// Test-Time-Augmentation stecken bereits im Modell (siehe src/skintriage/export/onnx_export.py).

import * as ort from 'onnxruntime-web/wasm';

const BASE = import.meta.env.BASE_URL;
let sessionPromise = null;
let metaPromise = null;

export function loadMeta() {
  if (!metaPromise) {
    metaPromise = fetch(`${BASE}model/meta.json`).then((r) => {
      if (!r.ok) throw new Error(`meta.json: HTTP ${r.status}`);
      return r.json();
    });
  }
  return metaPromise;
}

/** Lädt das Modell einmalig; onProgress(0..1) für den Download. */
export function loadModel(onProgress) {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      ort.env.wasm.numThreads = self.crossOriginIsolated ? Math.min(4, navigator.hardwareConcurrency || 1) : 1;
      let res;
      try {
        res = await fetch(`${BASE}model/model.onnx`);
      } catch {
        // seltener Cache-Konflikt (z. B. Service Worker lädt parallel): einmal ohne HTTP-Cache wiederholen
        res = await fetch(`${BASE}model/model.onnx`, { cache: 'no-store' });
      }
      if (!res.ok) throw new Error(`model.onnx: HTTP ${res.status}`);
      const total = Number(res.headers.get('content-length')) || 0;
      let buf;
      if (res.body && total && onProgress) {
        const reader = res.body.getReader();
        const chunks = [];
        let got = 0;
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          chunks.push(value);
          got += value.length;
          onProgress(got / total);
        }
        buf = new Uint8Array(got);
        let o = 0;
        for (const c of chunks) { buf.set(c, o); o += c.length; }
      } else {
        buf = new Uint8Array(await res.arrayBuffer());
      }
      onProgress?.(1);
      const session = await ort.InferenceSession.create(buf, { executionProviders: ['wasm'], graphOptimizationLevel: 'all' });
      window.dispatchEvent(new Event('modelready'));
      return session;
    })().catch((e) => { sessionPromise = null; throw e; });
  }
  return sessionPromise;
}

/**
 * Bewertet N Bilder. `pixels` ist Float32Array der Länge N*3*S*S (CHW, [0,1]).
 * Rückgabe: Array von { probs: number[7], score, ood }.
 */
export async function runModel(pixels, n, size) {
  const session = await loadModel();
  const input = new ort.Tensor('float32', pixels, [n, 3, size, size]);
  const out = await session.run({ image: input });
  const probs = out.probs.data;
  const k = probs.length / n;
  const res = [];
  for (let i = 0; i < n; i++) {
    res.push({
      probs: Array.from(probs.slice(i * k, (i + 1) * k)),
      score: out.score.data[i],
      ood: out.ood.data[i],
    });
  }
  return res;
}

/** Ampel-Zone: 0 grün, 1 gelb, 2 rot. */
export function zoneOf(score, meta) {
  if (score >= meta.rule.t_high) return 2;
  if (score >= meta.rule.t_low) return 1;
  return 0;
}

/** Anteil der gutartigen Referenzbilder mit niedrigerem Score (0..1). */
export function percentileOf(score, meta) {
  const ref = meta.rule.reference_benign;
  let lo = 0;
  let hi = ref.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (ref[mid] <= score) lo = mid + 1; else hi = mid;
  }
  return lo / ref.length;
}

/**
 * Wohin schaut das Modell? Verdeckungs-Analyse: Jedes Feld eines grid×grid-Rasters wird
 * nacheinander mit der mittleren Hautfarbe übermalt; wie stark sinkt dabei der Score?
 * Rückgabe: Float32Array grid*grid (positiv = Region erhöht die Auffälligkeit).
 */
export async function occlusionMap(chw, size, baseScore, grid = 6, onProgress) {
  const plane = size * size;
  const mean = [0, 1, 2].map((c) => {
    let s = 0;
    for (let i = 0; i < plane; i++) s += chw[c * plane + i];
    return s / plane;
  });
  const patch = Math.ceil(size / grid) * 1.5;
  const step = size / grid;
  const out = new Float32Array(grid * grid);
  const batch = 6;
  const cells = [];
  for (let gy = 0; gy < grid; gy++) for (let gx = 0; gx < grid; gx++) cells.push([gx, gy]);
  for (let b = 0; b < cells.length; b += batch) {
    const part = cells.slice(b, b + batch);
    const buf = new Float32Array(part.length * 3 * plane);
    part.forEach(([gx, gy], j) => {
      buf.set(chw, j * 3 * plane);
      const cx = (gx + 0.5) * step;
      const cy = (gy + 0.5) * step;
      const x0 = Math.max(0, Math.round(cx - patch / 2));
      const x1 = Math.min(size, Math.round(cx + patch / 2));
      const y0 = Math.max(0, Math.round(cy - patch / 2));
      const y1 = Math.min(size, Math.round(cy + patch / 2));
      for (let c = 0; c < 3; c++) {
        const off = j * 3 * plane + c * plane;
        for (let y = y0; y < y1; y++) buf.fill(mean[c], off + y * size + x0, off + y * size + x1);
      }
    });
    const res = await runModel(buf, part.length, size);
    part.forEach(([gx, gy], j) => { out[gy * grid + gx] = baseScore - res[j].score; });
    onProgress?.(Math.min(1, (b + batch) / cells.length));
  }
  return out;
}
