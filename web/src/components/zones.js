// Texte und Darstellung der Ampel-Zonen.

import { tr } from '../lib/i18n.js';
import { icon, pct } from '../lib/dom.js';

export const ZONE_CLASS = ['zone-green', 'zone-yellow', 'zone-red'];

export function zoneTitle(z) {
  return [
    tr('Unauffällig', 'Inconspicuous'),
    tr('Beobachten', 'Keep an eye on it'),
    tr('Ärztlich abklären lassen', 'Have it checked by a doctor'),
  ][z];
}

export function zoneShort(z) {
  return [tr('Grün', 'Green'), tr('Gelb', 'Yellow'), tr('Rot', 'Red')][z];
}

export function zoneAdvice(z) {
  return [
    tr('Das Modell findet an diesem Foto wenig Auffälliges. Das ist <strong>keine Entwarnung</strong>: Beobachte die Stelle weiter (z. B. alle 3 Monate ein Foto im Tagebuch) und lass sie ansehen, wenn sie sich verändert.',
      'The model finds little that stands out in this photo. This is <strong>not an all-clear</strong>: keep watching the spot (e.g. a diary photo every 3 months) and have it checked if it changes.'),
    tr('Das Foto ähnelt teilweise behandlungsbedürftigen Hautveränderungen. Beobachte die Stelle genau, mach in einigen Wochen ein Vergleichsfoto und lass sie bei Veränderung oder Unsicherheit ärztlich ansehen.',
      'The photo partly resembles lesions that need treatment. Watch the spot closely, take a comparison photo in a few weeks and see a doctor if it changes or you are unsure.'),
    tr('Das Foto ähnelt deutlich Hautveränderungen, die ärztlich abgeklärt werden sollten. Bitte vereinbare zeitnah einen Termin bei einer Hautärztin oder einem Hautarzt. Viele rot eingestufte Stellen sind am Ende harmlos – aber das kann nur eine Untersuchung klären.',
      'The photo clearly resembles lesions that should be checked by a doctor. Please book an appointment with a dermatologist soon. Many spots flagged red turn out to be harmless – but only an examination can tell.'),
  ][z];
}

export function zoneIcon(z) {
  return icon(['checkCircle', 'eye', 'stethoscope'][z], 'size-6');
}

/** Satz zu den Testergebnissen für diese Zone (aus meta.zone_stats). */
export function zoneEvidence(z, stats) {
  const s = stats?.external_pad_ufes;
  if (!s?.malignant || !s?.benign) return '';
  const key = ['green', 'yellow', 'red'][z];
  const mal = pct(s.malignant[key]);
  const ben = pct(s.benign[key]);
  const mel = s.melanoma ? pct(s.melanoma[key]) : null;
  const melNote = mel == null ? '' : z === 0
    ? tr(` Achtung: Auch ${mel} der Melanome landeten in Grün – Grün ist keine Garantie.`, ` Note: ${mel} of melanomas also ended up green – green is no guarantee.`)
    : tr(` Von den Melanomen landeten ${mel} in dieser Farbe.`, ` Of the melanomas, ${mel} ended up in this color.`);
  const intro = tr('Im Test mit echten Smartphone-Fotos aus Brasilien (PAD-UFES-20, im Training nie gesehen)',
    'In our test on real smartphone photos from Brazil (PAD-UFES-20, never seen in training)');
  return zoneEvidenceBase(z, intro, mal, ben) + melNote;
}

function zoneEvidenceBase(z, intro, mal, ben) {
  return [
    tr(`${intro} landeten <strong>${mal}</strong> der bösartigen und ${ben} der gutartigen Hautstellen in Grün.`,
      `${intro}, <strong>${mal}</strong> of malignant and ${ben} of benign lesions ended up green.`),
    tr(`${intro} landeten ${mal} der bösartigen und ${ben} der gutartigen Hautstellen in Gelb.`,
      `${intro}, ${mal} of malignant and ${ben} of benign lesions ended up yellow.`),
    tr(`${intro} landeten <strong>${mal}</strong> der bösartigen und ${ben} der gutartigen Hautstellen in Rot.`,
      `${intro}, <strong>${mal}</strong> of malignant and ${ben} of benign lesions ended up red.`),
  ][z];
}

export function zoneBadge(z, extra = '') {
  return `<span class="chip zone-bg ${ZONE_CLASS[z]}"><span class="size-2 rounded-full zone-dot"></span>${zoneShort(z)}${extra}</span>`;
}

/** Warnzeichen, bei denen man unabhängig vom Ergebnis zum Arzt gehen sollte. */
export function redFlagsCard() {
  const items = [
    tr('neu aufgetreten (v. a. ab etwa 30 Jahren) oder sichtbar verändert in Größe, Form oder Farbe',
      'new (especially from about age 30) or visibly changing in size, shape or color'),
    tr('blutet, nässt, juckt, schmerzt oder heilt nicht ab', 'bleeds, oozes, itches, hurts or does not heal'),
    tr('sieht anders aus als alle anderen Muttermale („hässliches Entlein“)', 'looks different from all your other moles (“ugly duckling”)'),
    tr('mehrere Farben, unscharfe Ränder oder größer als ca. 6 mm', 'several colors, blurry borders or larger than about 6 mm'),
  ];
  return `<div class="card p-5">
    <h3 class="flex items-center gap-2 font-semibold">${icon('alert', 'size-5 text-zone-red')}
      ${tr('Unabhängig vom Ergebnis: ab zum Hautarzt, wenn die Stelle …', 'Regardless of the result: see a dermatologist if the spot …')}</h3>
    <ul class="mt-3 space-y-1.5 text-sm text-muted">${items.map((i) => `<li class="flex gap-2"><span class="mt-2 size-1.5 shrink-0 rounded-full bg-zone-red"></span><span>${i}</span></li>`).join('')}</ul>
  </div>`;
}
