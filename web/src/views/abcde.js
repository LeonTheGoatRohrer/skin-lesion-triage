// ABCDE-Regel zur Selbstuntersuchung + interaktive Checkliste.

import { tr } from '../lib/i18n.js';
import { el, icon } from '../lib/dom.js';
import { ZONE_CLASS, zoneTitle } from '../components/zones.js';

const BROWN = '#8a5a3c';
const DARK = '#3b2417';

function pair(okSvg, badSvg) {
  const box = (svg, label, cls) => `<figure class="flex flex-col items-center gap-1">
    <svg viewBox="0 0 80 80" class="size-20 rounded-xl" style="background:#f3d9c4">${svg}</svg>
    <figcaption class="text-[11px] font-medium ${cls}">${label}</figcaption></figure>`;
  return `<div class="flex gap-4">${box(okSvg, tr('eher harmlos', 'usually harmless'), 'text-zone-green')}${box(badSvg, tr('auffällig', 'suspicious'), 'text-zone-red')}</div>`;
}

function items() {
  return [
    {
      key: 'A', title: tr('Asymmetrie', 'Asymmetry'),
      text: tr('Die beiden Hälften sehen unterschiedlich aus – die Form ist nicht rund oder oval.', 'The two halves look different – the shape is not round or oval.'),
      svg: pair(`<circle cx="40" cy="40" r="16" fill="${BROWN}"/>`,
        `<path d="M24 44c-4-12 6-22 16-20 6 1 9 6 15 5 8-1 10 9 4 15-5 5-9 12-18 11-9-1-14-4-17-11Z" fill="${BROWN}"/>`),
    },
    {
      key: 'B', title: tr('Begrenzung', 'Border'),
      text: tr('Der Rand ist unscharf, ausgefranst, gezackt oder läuft in die Haut aus.', 'The border is blurry, ragged, notched or fades into the skin.'),
      svg: pair(`<circle cx="40" cy="40" r="16" fill="${BROWN}"/>`,
        `<path d="M40 22l4 6 7-3 0 8 8 2-5 6 5 6-8 2 0 8-7-3-4 6-4-6-7 3 0-8-8-2 5-6-5-6 8-2 0-8 7 3Z" fill="${BROWN}"/>`),
    },
    {
      key: 'C', title: tr('Colour (Farbe)', 'Colour'),
      text: tr('Mehrere Farbtöne in einer Stelle: hell- und dunkelbraun, schwarz, rötlich, bläulich-grau oder weißlich.', 'Several shades in one spot: light and dark brown, black, reddish, bluish-grey or whitish.'),
      svg: pair(`<circle cx="40" cy="40" r="16" fill="${BROWN}"/>`,
        `<circle cx="40" cy="40" r="17" fill="${BROWN}"/><circle cx="34" cy="36" r="7" fill="${DARK}"/><circle cx="47" cy="45" r="5" fill="#b8475a"/><circle cx="44" cy="33" r="4" fill="#5b6b8a"/>`),
    },
    {
      key: 'D', title: tr('Durchmesser', 'Diameter'),
      text: tr('Größer als etwa 6 mm (Radiergummi am Bleistiftende). Auch kleinere Stellen können auffällig sein.', 'Larger than about 6 mm (a pencil eraser). Smaller spots can be suspicious too.'),
      svg: pair(`<circle cx="40" cy="40" r="7" fill="${BROWN}"/><path d="M20 62h40" stroke="#555" stroke-width="1.5"/><text x="40" y="74" font-size="9" text-anchor="middle" fill="#555">6 mm</text><path d="M33 58v8M47 58v8" stroke="#555"/>`,
        `<circle cx="40" cy="38" r="15" fill="${BROWN}"/><path d="M20 62h40" stroke="#555" stroke-width="1.5"/><text x="40" y="74" font-size="9" text-anchor="middle" fill="#555">6 mm</text><path d="M33 58v8M47 58v8" stroke="#555"/>`),
    },
    {
      key: 'E', title: tr('Entwicklung', 'Evolution'),
      text: tr('Die Stelle verändert sich: wächst, wird dunkler, erhaben, juckt oder blutet. Das ist das wichtigste Zeichen – genau dafür ist das Tagebuch da.',
        'The spot changes: grows, darkens, becomes raised, itches or bleeds. This is the most important sign – that is exactly what the diary is for.'),
      svg: pair(`<circle cx="26" cy="40" r="9" fill="${BROWN}"/><path d="M38 40h6" stroke="#555" stroke-width="2"/><circle cx="56" cy="40" r="9" fill="${BROWN}"/>`,
        `<circle cx="24" cy="40" r="8" fill="${BROWN}"/><path d="M35 40h6m-3-3 3 3-3 3" stroke="#555" stroke-width="2" fill="none"/><path d="M48 42c-2-9 5-14 11-12 7 2 9 9 5 14-4 6-13 6-16-2Z" fill="${DARK}"/>`),
    },
  ];
}

export async function mount(root) {
  const extra = [
    ['bleed', tr('blutet, nässt, juckt oder heilt nicht ab', 'bleeds, oozes, itches or does not heal')],
    ['duckling', tr('sieht anders aus als alle anderen Muttermale („hässliches Entlein“)', 'looks unlike all your other moles (“ugly duckling”)')],
    ['white', tr('glänzendes, perlartiges Knötchen oder raue, schuppige Stelle auf sonnenbelasteter Haut', 'shiny, pearly bump or rough, scaly patch on sun-exposed skin')],
  ];
  const view = el(`<div class="fade-in space-y-6">
    <div><h1 class="text-3xl font-bold tracking-tight">${tr('Die ABCDE-Regel', 'The ABCDE rule')}</h1>
      <p class="mt-2 max-w-2xl text-sm leading-relaxed text-muted">${tr(
        'Mit dieser Faustregel schauen auch Hautärztinnen und Hautärzte auf pigmentierte Stellen. Sie hilft bei der monatlichen Selbstuntersuchung – idealerweise vor einem Spiegel, mit Hilfe für den Rücken.',
        'Dermatologists use this rule of thumb for pigmented spots too. It helps with a monthly self-examination – ideally in front of a mirror, with help for your back.')}</p></div>
    <div class="grid gap-4 md:grid-cols-2">
      ${items().map((it) => `<div class="card flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <div class="flex-1"><div class="flex items-center gap-3"><span class="flex size-9 items-center justify-center rounded-xl bg-accent text-lg font-bold text-on-accent">${it.key}</span>
          <h2 class="text-lg font-semibold">${it.title}</h2></div>
          <p class="mt-2 text-sm text-muted">${it.text}</p></div>
        ${it.svg}</div>`).join('')}
      <div class="card p-5"><h2 class="text-lg font-semibold">${tr('Weißer Hautkrebs sieht anders aus', 'Non-melanoma skin cancer looks different')}</h2>
        <p class="mt-2 text-sm text-muted">${tr(
          'Basalzell- und Plattenepithelkarzinome sind viel häufiger als Melanome und oft nicht braun: glasig-glänzende Knötchen mit kleinen Äderchen, schuppige oder krustige Stellen, Wunden, die nicht abheilen – meist im Gesicht, an Ohren, Händen oder auf der Kopfhaut.',
          'Basal and squamous cell carcinomas are much more common than melanoma and often not brown: glassy, shiny bumps with tiny vessels, scaly or crusty patches, sores that do not heal – mostly on the face, ears, hands or scalp.')}</p></div>
    </div>

    <section class="card p-5 md:p-6">
      <h2 class="text-lg font-semibold">${tr('Selbst-Check für eine Hautstelle', 'Self-check for one spot')}</h2>
      <p class="mt-1 text-sm text-muted">${tr('Kreuze an, was zutrifft. Das ersetzt keine Untersuchung, hilft aber bei der Entscheidung.', 'Tick what applies. This does not replace an examination but helps you decide.')}</p>
      <form class="mt-4 grid gap-2 sm:grid-cols-2" data-form>
        ${items().map((it) => `<label class="flex items-start gap-3 rounded-xl border border-line p-3 text-sm hover:bg-surface-2">
          <input type="checkbox" name="${it.key}" class="mt-0.5 size-4 accent-[var(--c-accent)]"><span><strong>${it.key} – ${it.title}</strong></span></label>`).join('')}
        ${extra.map(([k, t]) => `<label class="flex items-start gap-3 rounded-xl border border-line p-3 text-sm hover:bg-surface-2">
          <input type="checkbox" name="${k}" class="mt-0.5 size-4 accent-[var(--c-accent)]"><span>${t}</span></label>`).join('')}
      </form>
      <div class="mt-4" data-out aria-live="polite"></div>
    </section>

    <section class="card p-5 text-sm leading-relaxed text-muted">
      <h2 class="text-lg font-semibold text-fg">${tr('Vorsorge', 'Prevention')}</h2>
      <ul class="mt-2 list-disc space-y-1 pl-5">
        <li>${tr('Sonnenbrand vermeiden: Schatten, Kleidung, Sonnencreme (LSF 30–50), keine Solarien.', 'Avoid sunburn: shade, clothing, sunscreen (SPF 30–50), no tanning beds.')}</li>
        <li>${tr('Einmal im Monat die eigene Haut ansehen – mit ABCDE und dem Tagebuch.', 'Look at your skin once a month – with ABCDE and the diary.')}</li>
        <li>${tr('In Deutschland zahlen die gesetzlichen Kassen ab 35 alle zwei Jahre ein Hautkrebs-Screening. Bei Risikofaktoren (viele oder auffällige Muttermale, helle Haut, frühere Sonnenbrände, Hautkrebs in der Familie) regelmäßige hautärztliche Kontrollen besprechen – auch in Österreich und der Schweiz.',
          'In Germany, statutory health insurance covers a skin cancer screening every two years from age 35. With risk factors (many or unusual moles, fair skin, past sunburns, skin cancer in the family) discuss regular dermatology check-ups.')}</li>
      </ul>
    </section>
  </div>`);
  root.replaceChildren(view);
  const form = view.querySelector('[data-form]');
  const out = view.querySelector('[data-out]');
  const update = () => {
    const f = Object.fromEntries([...form.querySelectorAll('input')].map((i) => [i.name, i.checked]));
    const abcd = ['A', 'B', 'C', 'D'].filter((k) => f[k]).length;
    let z = 0;
    if (f.E || f.bleed || f.duckling || f.white || abcd >= 2) z = 2;
    else if (abcd === 1) z = 1;
    const text = [
      tr('Keine Warnzeichen angekreuzt. Weiter beobachten – am besten mit regelmäßigen Fotos im Tagebuch.', 'No warning signs ticked. Keep watching – ideally with regular diary photos.'),
      tr('Ein Merkmal trifft zu. Das ist häufig harmlos – beobachte die Stelle genau und mach ein Vergleichsfoto in einigen Wochen.', 'One feature applies. This is often harmless – watch the spot closely and take a comparison photo in a few weeks.'),
      tr('Mehrere Merkmale oder ein wichtiges Warnzeichen treffen zu. Bitte lass die Stelle ärztlich ansehen.', 'Several features or an important warning sign apply. Please have the spot examined by a doctor.'),
    ][z];
    out.innerHTML = `<div class="card ${ZONE_CLASS[z]} zone-bg flex gap-3 p-4">${icon(z === 2 ? 'stethoscope' : z === 1 ? 'eye' : 'checkCircle', 'size-5 shrink-0')}
      <div><p class="font-semibold">${zoneTitle(z)}</p><p class="mt-0.5 text-sm text-fg">${text}</p></div></div>`;
  };
  form.addEventListener('change', update);
  update();
  return null;
}
