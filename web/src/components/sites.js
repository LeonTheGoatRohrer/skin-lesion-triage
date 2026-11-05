export const BODY_SITES = [
  { id: 'head', de: 'Kopf / Gesicht', en: 'Head / face' },
  { id: 'neck', de: 'Hals', en: 'Neck' },
  { id: 'chest', de: 'Brust', en: 'Chest' },
  { id: 'abdomen', de: 'Bauch', en: 'Abdomen' },
  { id: 'back', de: 'Rücken', en: 'Back' },
  { id: 'arm_l', de: 'Arm links', en: 'Left arm' },
  { id: 'arm_r', de: 'Arm rechts', en: 'Right arm' },
  { id: 'hand', de: 'Hand', en: 'Hand' },
  { id: 'leg_l', de: 'Bein links', en: 'Left leg' },
  { id: 'leg_r', de: 'Bein rechts', en: 'Right leg' },
  { id: 'foot', de: 'Fuß', en: 'Foot' },
  { id: 'other', de: 'Andere Stelle', en: 'Other' },
];

export function siteLabel(id, lang = 'de') {
  const s = BODY_SITES.find((x) => x.id === id);
  return s ? s[lang] || s.de : id || '–';
}
