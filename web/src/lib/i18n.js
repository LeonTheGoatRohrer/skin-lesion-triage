// Sprache: 'de' | 'en', gespeichert in localStorage. Standard: Deutsch.
// Texte stehen direkt im Code als tr(de, en); Views rufen tr() beim Rendern auf.
// setLang() setzt <html lang> und löst das window-Event 'langchange' aus.

const STORAGE_KEY = 'skin-lang';
const LANGS = ['de', 'en'];

function detect() {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (LANGS.includes(v)) return v;
  } catch { /* Speicher nicht verfügbar */ }
  return 'de';
}

let current = detect();
document.documentElement.lang = current;

export function getLang() {
  return current;
}

export function locale() {
  return current === 'en' ? 'en-US' : 'de-DE';
}

export function setLang(lang) {
  if (!LANGS.includes(lang) || lang === current) return;
  current = lang;
  try { window.localStorage.setItem(STORAGE_KEY, lang); } catch { /* egal */ }
  document.documentElement.lang = lang;
  window.dispatchEvent(new CustomEvent('langchange', { detail: { lang } }));
}

/** Deutsche oder englische Variante. */
export function tr(de, en) {
  return current === 'en' ? en : de;
}
