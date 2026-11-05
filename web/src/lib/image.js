// Bild laden (mit EXIF-Drehung), Ausschnitt rendern, in Modell-Eingang umwandeln.

/** Datei -> ImageBitmap (berücksichtigt die EXIF-Ausrichtung von Handyfotos). */
export async function loadBitmap(fileOrBlob) {
  try {
    return await createImageBitmap(fileOrBlob, { imageOrientation: 'from-image' });
  } catch {
    // Fallback für ältere Browser: über <img>
    const url = URL.createObjectURL(fileOrBlob);
    try {
      const img = new Image();
      img.decoding = 'async';
      img.src = url;
      await img.decode();
      return await createImageBitmap(img);
    } finally {
      URL.revokeObjectURL(url);
    }
  }
}

/**
 * Quadratischen Ausschnitt (x, y, side in Bildpixeln) auf ein size×size-Canvas zeichnen.
 * Große Verkleinerungen erfolgen in Halbierungsschritten (wie Antialiasing beim Training).
 */
export function renderCrop(bitmap, crop, size) {
  let src = bitmap;
  let sx = crop.x;
  let sy = crop.y;
  let side = crop.side;
  // stufenweise halbieren, bis höchstens Faktor 2 übrig ist
  while (side / size > 2) {
    const half = Math.max(size, Math.round(side / 2));
    const c = document.createElement('canvas');
    c.width = half;
    c.height = half;
    const g = c.getContext('2d');
    g.imageSmoothingEnabled = true;
    g.imageSmoothingQuality = 'high';
    g.fillStyle = '#000';
    g.fillRect(0, 0, half, half);
    g.drawImage(src, sx, sy, side, side, 0, 0, half, half);
    src = c;
    sx = 0;
    sy = 0;
    side = half;
  }
  const out = document.createElement('canvas');
  out.width = size;
  out.height = size;
  const g = out.getContext('2d', { willReadFrequently: true });
  g.imageSmoothingEnabled = true;
  g.imageSmoothingQuality = 'high';
  g.fillStyle = '#000';
  g.fillRect(0, 0, size, size);
  g.drawImage(src, sx, sy, side, side, 0, 0, size, size);
  return out;
}

/** Canvas -> Float32Array im CHW-Format, Werte in [0,1]. */
export function canvasToCHW(canvas) {
  const { width: w, height: h } = canvas;
  const data = canvas.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const plane = w * h;
  const out = new Float32Array(3 * plane);
  for (let i = 0; i < plane; i++) {
    out[i] = data[i * 4] / 255;
    out[plane + i] = data[i * 4 + 1] / 255;
    out[2 * plane + i] = data[i * 4 + 2] / 255;
  }
  return out;
}

export function canvasToBlob(canvas, type = 'image/jpeg', quality = 0.88) {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
}

export function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(blob);
  });
}

export async function dataURLToBlob(url) {
  return (await fetch(url)).blob();
}
