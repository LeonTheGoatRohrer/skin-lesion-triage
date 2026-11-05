# Experiment-Protokoll

Regeln (wie im EKG-Projekt):

1. **Modellauswahl nur auf dem Validierungs-Split.** Test und externer Test (PAD-UFES-20) werden
   erst angefasst, wenn die Konfiguration eingefroren ist – und dann genau einmal.
2. **Splits nach Gruppe:** Bilder, die Patient oder Läsion teilen, liegen im selben Split.
3. **Hauptmetrik:** AUROC je Bildart (bösartig vs. gutartig; aktinische Keratosen werden getrennt
   berichtet). Dazu pAUC oberhalb 80 % Sensitivität (ISIC-2024-Metrik, Maximum 0,2).
4. **Rechenbudget:** eine CPU mit 4 Kernen, keine GPU. Ein Lauf mit 10 Epochen à 16 000 Bildern
   dauert ~45 Minuten.

## Daten-Split (Bilder)

| Split | Kamerafotos (bösartig / gutartig / AK) | 3D-TBP (bösartig / gutartig*) | Dermoskopie (bösartig / gutartig / AK) |
|---|---|---|---|
| Train | 2 593 / 1 884 / 93 | 289 / 40 000 | 2 542 / 1 067 / 93 |
| Val | 553 / 397 / 14 | 62 / 12 000 | 545 / 230 / 14 |
| Test | 552 / 436 / 16 | 42 / 20 000 | 547 / 186 / 16 |
| Extern (PAD-UFES-20, Smartphone) | 1 089 / 479 / 730 | – | – |

\* Stichprobe aus ~400 000; Gewicht 1/p in allen Kennzahlen.

<!-- EXPERIMENTS:START -->
(wird nach den Läufen ergänzt)
<!-- EXPERIMENTS:END -->
