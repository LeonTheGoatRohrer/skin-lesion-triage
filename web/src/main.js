import '@fontsource-variable/inter';
import './style.css';

import { getLang, setLang, tr } from './lib/i18n.js';
import { getTheme, initTheme, setTheme } from './lib/theme.js';
import { el, icon, logoMark } from './lib/dom.js';

const ROUTES = {
  check: () => import('./views/check.js'),
  diary: () => import('./views/diary.js'),
  abcde: () => import('./views/abcde.js'),
  about: () => import('./views/about.js'),
};

function navItems() {
  return [
    { id: 'check', label: tr('Prüfen', 'Check'), icon: 'scan' },
    { id: 'diary', label: tr('Tagebuch', 'Diary'), icon: 'book' },
    { id: 'abcde', label: tr('ABCDE-Regel', 'ABCDE rule'), icon: 'list' },
    { id: 'about', label: tr('So funktioniert’s', 'How it works'), icon: 'layers' },
  ];
}

export function parseHash() {
  const h = (location.hash || '#/check').replace(/^#\/?/, '');
  const [path, query = ''] = h.split('?');
  const [route, ...rest] = path.split('/');
  return { route: ROUTES[route] ? route : 'check', params: rest, query: new URLSearchParams(query) };
}

function header(active) {
  const items = navItems().map((n) => `
    <a href="#/${n.id}" class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition
      ${n.id === active ? 'bg-accent-soft text-accent' : 'text-muted hover:text-fg hover:bg-surface-2'}"
      ${n.id === active ? 'aria-current="page"' : ''}>${icon(n.icon)}<span>${n.label}</span></a>`).join('');
  const theme = getTheme();
  const nextTheme = { system: 'light', light: 'dark', dark: 'system' }[theme];
  const themeIcon = { system: 'monitor', light: 'sun', dark: 'moon' }[theme];
  return el(`
    <header class="sticky top-0 z-30 border-b border-line backdrop-blur" style="background: var(--c-header)">
      <div class="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3">
        <a href="#/check" class="flex items-center gap-2.5 font-semibold tracking-tight" aria-label="${tr('Startseite', 'Home')}">
          ${logoMark('size-8')}
          <span class="leading-tight">${tr('Hautstellen-Check', 'Skin Spot Check')}
            <span class="block text-[11px] font-medium text-muted">${tr('Prototyp · kein Medizinprodukt', 'Prototype · not a medical device')}</span>
          </span>
        </a>
        <nav class="ml-auto hidden items-center gap-1 md:flex" aria-label="${tr('Hauptnavigation', 'Main navigation')}">${items}</nav>
        <div class="ml-auto flex items-center gap-1 md:ml-2">
          <button data-act="lang" class="btn btn-ghost btn-sm" aria-label="${tr('Sprache wechseln', 'Switch language')}">${getLang() === 'de' ? 'EN' : 'DE'}</button>
          <button data-act="theme" data-next="${nextTheme}" class="btn btn-ghost btn-sm" aria-label="${tr('Farbschema', 'Color scheme')}: ${theme}">${icon(themeIcon)}</button>
        </div>
      </div>
    </header>`);
}

function bottomNav(active) {
  const items = navItems().map((n) => `
    <a href="#/${n.id}" class="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium
      ${n.id === active ? 'text-accent' : 'text-muted'}" ${n.id === active ? 'aria-current="page"' : ''}>
      ${icon(n.icon, 'size-5')}<span>${n.label}</span></a>`).join('');
  return el(`<nav class="fixed inset-x-0 bottom-0 z-30 flex border-t border-line md:hidden"
    style="background: var(--c-header); backdrop-filter: blur(12px); padding-bottom: env(safe-area-inset-bottom)"
    aria-label="${tr('Navigation', 'Navigation')}">${items}</nav>`);
}

function footer() {
  return el(`
    <footer class="mx-auto max-w-5xl px-4 pb-28 pt-10 text-xs leading-relaxed text-muted md:pb-10">
      <div class="border-t border-line pt-5">
        <p><strong class="text-fg">${tr('Wichtig:', 'Important:')}</strong> ${tr(
          'Lern- und Portfolio-Projekt. Kein Medizinprodukt, keine Diagnose. Das Ergebnis ersetzt keine ärztliche Untersuchung – bei Sorge, Veränderung, Blutung oder Juckreiz bitte immer zur Hautärztin oder zum Hautarzt.',
          'Learning and portfolio project. Not a medical device, no diagnosis. The result does not replace a medical examination – if you are worried, or a spot changes, bleeds or itches, always see a dermatologist.')}</p>
        <p class="mt-2">${icon('lock', 'size-3.5 inline -mt-0.5')} ${tr(
          'Fotos werden ausschließlich auf deinem Gerät verarbeitet und gespeichert.',
          'Photos are processed and stored on your device only.')}
          · ${tr('Bilddaten', 'Images')}: ISIC Archive – ${tr('Training', 'training')} MILK10k, SLICE-3D/ISIC 2024, MSK, ${tr('ISIC-Dermoskopie', 'ISIC dermoscopy')}; ${tr('externer Test', 'external test')} PAD-UFES-20.
          · <a class="underline" href="#/about">${tr('Details & Lizenzen', 'Details & licenses')}</a></p>
      </div>
    </footer>`);
}

let currentView = null;

async function render() {
  const { route, params, query } = parseHash();
  const app = document.getElementById('app');
  const main = el('<main id="main" class="mx-auto max-w-5xl px-4 pt-6" tabindex="-1"></main>');
  app.replaceChildren(header(route), main, footer(), bottomNav(route));
  app.querySelector('[data-act="lang"]').addEventListener('click', () => setLang(getLang() === 'de' ? 'en' : 'de'));
  app.querySelector('[data-act="theme"]').addEventListener('click', (e) => setTheme(e.currentTarget.dataset.next));
  currentView?.destroy?.();
  currentView = null;
  try {
    const mod = await ROUTES[route]();
    currentView = await mod.mount(main, { params, query }) || null;
  } catch (err) {
    console.error(err);
    main.replaceChildren(el(`<div class="card p-6"><p class="font-semibold">${tr('Diese Ansicht konnte nicht geladen werden.', 'This view could not be loaded.')}</p>
      <p class="mt-2 text-sm text-muted">${String(err?.message || err)}</p></div>`));
  }
  document.title = `${navItems().find((n) => n.id === route).label} · ${tr('Hautstellen-Check', 'Skin Spot Check')}`;
}

initTheme();
window.addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
window.addEventListener('langchange', render);
window.addEventListener('themechange', render);
window.addEventListener('themepreference', render);
render();

// Service Worker (offline) erst registrieren, wenn das Modell geladen ist – sonst laden Seite
// und Service Worker die 9 MB gleichzeitig. Ohne Prüfen-Seite: kurz nach dem Laden.
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  let done = false;
  const reg = () => {
    if (done) return;
    done = true;
    navigator.serviceWorker.register('./sw.js').catch(() => { /* offline-Modus optional */ });
  };
  window.addEventListener('modelready', reg, { once: true });
  window.addEventListener('load', () => setTimeout(reg, 15000));
}
