// Service Worker: App, Modell und WebAssembly-Laufzeit werden nach dem ersten Besuch
// gecacht – danach funktioniert die App offline. Fotos werden nie übertragen.
const CACHE = 'skin-triage-v1';
const CORE = ['./', './index.html', './manifest.webmanifest', './model/model.onnx', './model/meta.json',
  './icons/icon.svg'];
// Gebündelte Dateien (JS, CSS, WebAssembly) haben Hash-Namen und werden beim ersten Abruf gecacht.

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;
  // Netzwerk zuerst für HTML/JSON (Aktualisierungen), Cache zuerst für große, versionierte Dateien
  const networkFirst = e.request.mode === 'navigate' || url.pathname.endsWith('.json');
  if (networkFirst) {
    e.respondWith(fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match(e.request).then((r) => r || caches.match('./index.html'))));
  } else {
    e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    })));
  }
});
