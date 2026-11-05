// Muttermal-Tagebuch: alles bleibt lokal im Browser (IndexedDB). Kein Server, kein Konto.
//
// spots:  { id, name, site, createdAt }
// checks: { id, spotId, date, thumb (Blob JPEG), score, percentile, zone, probs, quality, ood, modelVersion }

const DB_NAME = 'skin-diary';
const DB_VERSION = 1;
let dbPromise = null;

function open() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains('spots')) db.createObjectStore('spots', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('checks')) {
          const s = db.createObjectStore('checks', { keyPath: 'id' });
          s.createIndex('spotId', 'spotId');
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  return dbPromise;
}

function tx(store, mode, fn) {
  return open().then((db) => new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const s = t.objectStore(store);
    const out = fn(s);
    t.oncomplete = () => resolve(out && 'result' in out ? out.result : out);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  }));
}

export function uid() {
  return (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);
}

export async function available() {
  try { await open(); return true; } catch { return false; }
}

export const listSpots = () => tx('spots', 'readonly', (s) => s.getAll());
export const getSpot = (id) => tx('spots', 'readonly', (s) => s.get(id));
export const putSpot = (spot) => tx('spots', 'readwrite', (s) => s.put(spot));
export const putCheck = (check) => tx('checks', 'readwrite', (s) => s.put(check));
export const listChecks = () => tx('checks', 'readonly', (s) => s.getAll());

export function checksFor(spotId) {
  return tx('checks', 'readonly', (s) => s.index('spotId').getAll(spotId))
    .then((arr) => arr.sort((a, b) => a.date.localeCompare(b.date)));
}

export async function deleteSpot(id) {
  const checks = await checksFor(id);
  await tx('checks', 'readwrite', (s) => { checks.forEach((c) => s.delete(c.id)); });
  await tx('spots', 'readwrite', (s) => s.delete(id));
}

export const deleteCheck = (id) => tx('checks', 'readwrite', (s) => s.delete(id));

/** Alles als JSON (Bilder als data-URL) – zum Sichern auf dem eigenen Gerät. */
export async function exportAll(blobToDataURL) {
  const spots = await listSpots();
  const checks = await listChecks();
  const out = [];
  for (const c of checks) out.push({ ...c, thumb: c.thumb ? await blobToDataURL(c.thumb) : null });
  return { app: 'skin-lesion-triage', version: 1, exportedAt: new Date().toISOString(), spots, checks: out };
}

export async function importAll(data, dataURLToBlob) {
  if (data?.app !== 'skin-lesion-triage' || !Array.isArray(data.spots) || !Array.isArray(data.checks)) {
    throw new Error('Unbekanntes Dateiformat');
  }
  for (const s of data.spots) await putSpot(s);
  for (const c of data.checks) await putCheck({ ...c, thumb: c.thumb ? await dataURLToBlob(c.thumb) : null });
  return { spots: data.spots.length, checks: data.checks.length };
}
