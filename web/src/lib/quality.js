// Bildqualität – gleiche Rechnung wie src/skintriage/export/quality.py, auf dem Modell-Eingang.
// Grenzwerte stammen aus model/meta.json (aus den Validierungsfotos abgeleitet).

export function qualityFeatures(chw, size) {
  const plane = size * size;
  const y = new Float32Array(plane);
  let sum = 0;
  let over = 0;
  for (let i = 0; i < plane; i++) {
    const v = 0.299 * chw[i] + 0.587 * chw[plane + i] + 0.114 * chw[2 * plane + i];
    y[i] = v;
    sum += v;
    if (v > 0.97) over++;
  }
  let n = 0;
  let m = 0;
  let m2 = 0;
  for (let r = 1; r < size - 1; r++) {
    for (let c = 1; c < size - 1; c++) {
      const i = r * size + c;
      const lap = y[i - size] + y[i + size] + y[i - 1] + y[i + 1] - 4 * y[i];
      n++;
      const d = lap - m;
      m += d / n;
      m2 += d * (lap - m);
    }
  }
  return { brightness: sum / plane, overexposed: over / plane, sharpness: m2 / n };
}

/** Liste von Prüfungen: { key, ok, value }. */
export function qualityChecks(f, limits, ood, oodThreshold) {
  return [
    { key: 'sharpness', ok: f.sharpness >= limits.sharpness_min, value: f.sharpness },
    { key: 'exposure', ok: f.brightness >= limits.brightness_min && f.brightness <= limits.brightness_max
      && f.overexposed <= limits.overexposed_max, value: f.brightness },
    { key: 'familiar', ok: ood <= oodThreshold, value: ood },
  ];
}
