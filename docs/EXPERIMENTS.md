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

## Verlauf der Entscheidungen

1. **E0 – lineare Probe** auf eingefrorenen ImageNet-Merkmalen: Untergrenze.
2. **E1 – alle drei Bildarten** (Kamerafoto, 3D-TBP, MILK10k-Dermoskopie), domänen-balanciert.
3. **Befund nach E1 (Validierung):** Insgesamt landeten 95 % der bösartigen Kamerafotos in
   Gelb/Rot, aber **28 % der Melanome in Grün** – Basalzellkarzinome dominieren die bösartigen
   Trainingsbilder (~70 %) und werden fast nie übersehen. Für eine Muttermal-App ist das die
   falsche Gewichtung. Konsequenzen:
   - Die Gelb-Schwelle muss **zusätzlich 90 % Melanom-Sensitivität** auf der Validierung
     erfüllen (gilt rückwirkend für alle Läufe; die AUROC ändert sich dadurch nicht).
   - Neue Kennzahlen: AUROC Melanom vs. Nävus, Anteil der Melanome in Grün.
   - **E4:** zusätzlich 15 400 Dermoskopie-Bilder aus dem ISIC-Archiv (u. a. 5 000 Melanome,
     5 000 Nävi; Splits von Patient/Läsion geerbt) und Diagnose-Balancierung im Sampler
     (Ziehgewicht ∝ Anzahl^−0,5 je Gruppe).
   - E3 (160 px) wurde dafür gestrichen – Melanome zu erkennen ist für den Zweck wichtiger.
4. **E2 – ohne Dermoskopie:** prüft, ob Dermoskopie den handyähnlichen Bildarten überhaupt hilft.

**Vorab festgelegtes Auswahlkriterium** (vor dem Ergebnis von E4 notiert): Gewählt wird der Lauf
mit der höchsten **Spezifität an der Gelb-Schwelle auf den Validierungs-Kamerafotos** – also dem
Anteil gutartiger Stellen, die in Grün bleiben dürfen, wenn 95 % aller bösartigen und 90 % der
Melanome erfasst werden. Das ist die Zahl, die im Alltag über unnötige Arztbesuche entscheidet.
Bei Gleichstand (< 0,01) entscheidet die AUROC Melanom vs. Nävus.

<!-- EXPERIMENTS:START -->
## Läufe (nur Validierung, mit 4-facher TTA; MobileNetV3-Large, 128 px)

| Run | Bildarten im Training | Val-AUROC Kamera | **Spez. an Gelb-Schwelle (Kamera)** | AUROC Melanom vs. Nävus (Kamera) | Val-AUROC 3D-TBP | Val-pAUC80 3D-TBP | Val-AUROC Dermoskopie |
|---|---|---:|---:|---:|---:|---:|---:|
| e0_linear_probe | alle | 0,853 | – | – | 0,809 | 0,071 | 0,770 |
| e1_mix | clinical + tbp + dermoscopic | 0,908 | 0,531 | 0,791 | 0,934 | 0,146 | 0,855 |
| e2_no_derm | clinical + tbp | 0,907 | 0,531 | 0,798 | 0,935 | 0,148 | 0,738 |
| e4_melanoma ★ | clinical + tbp + dermoscopic + ISIC-Dermoskopie (Melanom-Fokus), Diagnose-Balancierung 0.5 | 0,903 | 0,552 | 0,771 | 0,931 | 0,143 | 0,844 |

★ = ausgewähltes Modell. Verlauf von `e4_melanoma` (Validierung je Epoche, ohne TTA, SLICE-3D-Gutartige als 6 000er-Stichprobe):

| Epoche | Loss | Val-AUROC Kamera | Val-AUROC 3D-TBP | Val-AUROC Dermoskopie |
|---:|---:|---:|---:|---:|
| 1 | 1,338 | 0,796 | 0,764 | 0,694 |
| 2 | 1,179 | 0,873 | 0,877 | 0,785 |
| 3 | 1,107 | 0,886 | 0,913 | 0,816 |
| 4 | 1,069 | 0,891 | 0,917 | 0,828 |
| 5 | 1,011 | 0,894 | 0,915 | 0,832 |
| 6 | 0,969 | 0,896 | 0,916 | 0,834 |
| 7 | 0,922 | 0,898 | 0,915 | 0,838 |
| 8 | 0,885 | 0,898 | 0,915 | 0,838 |
| 9 | 0,859 | 0,896 | 0,915 | 0,838 |
| 10 | 0,847 | 0,895 | 0,914 | 0,838 |
<!-- EXPERIMENTS:END -->

## Entscheidung und ehrliche Einordnung

- **Gewählt: E4** nach dem vorab notierten Kriterium (Spezifität an der Gelb-Schwelle auf den
  Validierungs-Kamerafotos: 0,552 gegenüber 0,531 bei E1/E2). Der Vorsprung entspricht nur
  8 von 397 gutartigen Fotos und liegt im Rauschen. Die AUROC-Unterschiede zwischen E1, E2 und E4
  (0,903–0,908) liegen weit innerhalb der Konfidenzintervalle (±0,03).
- **Was die Zusatz-Dermoskopie gebracht hat:** auf Dermoskopie-Bildern bessere Melanom-Trennung
  (Melanom vs. Nävus 0,853 statt 0,79), auf Kamerafotos nicht (0,771 statt 0,79–0,80). Der Transfer
  von Dermoskopie auf normale Fotos ist schwach – das deckt sich mit E2, wo das Weglassen der
  Dermoskopie die Kamera-Kennzahlen nicht verschlechterte.
- **Nebenwirkung:** Die Prüfung „nicht beurteilbar“ weist bei E4 kaum noch SCIN-Fotos ab (0,5 %
  statt 6,5 % bei E1 und 28,5 % bei E2). Mit vielfältigeren Trainingsbildern liegen auch Ausschläge
  „näher“ an den Trainingsdaten. Das war nicht Teil des Kriteriums und wird offen berichtet.
- **Einmalige Auswertung** (Test + PAD-UFES-20) danach ohne weitere Änderungen; Zahlen in der
  README und auf der Seite „So funktioniert’s“.

## Nächste Schritte (nicht umgesetzt)

- Höhere Auflösung (160–224 px) und ein größeres Netz auf einer GPU; E3 (160 px) wurde gestrichen.
- Eigene Kalibrierung für Handyfotos: Die Rangfolge überträgt sich (AUROC 0,916 extern), die
  Schwellen nicht (nur 30 % der gutartigen PAD-Fotos bleiben grün). Mit einem *eigenen*
  Smartphone-Validierungsdatensatz ließen sich die Schwellen passend setzen – PAD-UFES-20 darf
  dafür nicht verwendet werden, solange es der externe Test ist.
- Bessere Erkennung von „nicht beurteilbar“: z. B. ein eigener Klassifikator „einzelne Hautstelle
  ja/nein“, trainiert mit Ausschlag-, Tattoo- und Alltagsfotos.
- Mehrere Fotos derselben Stelle mitteln (Unsicherheit durch Bildausschnitt und Licht verringern).
