# Fragen und Antworten

Kurze Erklärungen zu den Entscheidungen in diesem Projekt – auch für Leserinnen und Leser ohne
Machine-Learning-Hintergrund.

### Gibt es eine „MIT-Datenbank“ für Hautkrebs, wie beim EKG-Projekt?

Nein. Die MIT-BIH-Datenbank auf PhysioNet enthält nur Signale (EKG, EEG …). Die große öffentliche
Sammlung für Hautbilder ist das **ISIC-Archiv** (International Skin Imaging Collaboration) mit über
500 000 Bildern. Es spielt hier dieselbe Rolle wie MIT-BIH im EKG-Projekt.

### Warum nicht einfach die bekannten Dermoskopie-Datensätze (HAM10000, ISIC 2019/2020)?

Dermoskopie-Bilder entstehen mit einem Auflichtmikroskop, das direkt auf die Haut gedrückt wird:
gleichmäßiges Licht, keine Spiegelung, starke Vergrößerung. Ein Handyfoto sieht völlig anders aus.
Ein Modell, das nur Dermoskopie kennt, ist auf Handyfotos oft deutlich schlechter.
Dieses Projekt trainiert deshalb vor allem auf Bildarten, die einem Handyfoto ähneln:

- **Kamerafotos aus Hautkliniken** (MILK10k, MSK) – normale Digitalkamera, aus der Nähe
- **Ausschnitte aus 3D-Ganzkörperfotos** (SLICE-3D / ISIC 2024) – laut Datensatz-Paper in der
  Auflösung mit Smartphone-Fotos vergleichbar

Dermoskopie ist als dritte Bildart dabei (die zu den MILK10k-Fotos gehörenden Aufnahmen).
Experiment E2 prüft, ob sie überhaupt hilft.

### Was ist der externe Test, und warum ist er so wichtig?

**PAD-UFES-20** sind 2 298 echte Smartphone-Fotos aus Brasilien – andere Klinik, anderes Land,
andere Kameras. Sie kamen im Training und bei der Modellauswahl **nie** vor. Erst ganz am Ende wird
einmal gemessen, wie gut das Modell dort ist. Diese Zahl ist die ehrlichste Schätzung dafür, was
im Alltag passieren würde – und sie ist schlechter als die interne Zahl. Genau das ist der Punkt.

### Warum zeigt die App keine „Krebs-Wahrscheinlichkeit“?

Weil sie vom Publikum abhängt. In MILK10k (Hautklinik) sind ~70 % der Fotos bösartig, in SLICE-3D
(alle Hautstellen von Patienten im Screening) etwa 0,1 %. Ein und dasselbe Foto bekäme je nach
Annahme eine völlig andere „Wahrscheinlichkeit“. Stattdessen zeigt die App:

1. **Ampel**: Die Schwellen wurden auf Validierungsdaten so gesetzt, dass ~95 % der bösartigen
   Stellen Gelb oder Rot bekommen und höchstens ~10 % der gutartigen Rot.
2. **Auffälligkeit in Prozent**: „Auffälliger als 87 % der gutartigen Vergleichsfotos“ – das ist
   unabhängig davon, wie häufig Krebs in einer Gruppe ist.
3. **Was die Farbe im Test bedeutet hat**: z. B. wie viele bösartige Handyfotos im externen Test in
   Grün gelandet sind.

### Was bedeutet AUROC?

Nimm zufällig eine bösartige und eine gutartige Hautstelle. Die AUROC ist die Wahrscheinlichkeit,
dass das Modell der bösartigen den höheren Score gibt. 0,5 = Raten, 1,0 = perfekt. Sie ist
unabhängig von einer Schwelle und von der Häufigkeit der Klassen – deshalb die Hauptzahl.
Accuracy wäre irreführend: In SLICE-3D läge „immer gutartig“ bei 99,9 %.

### Warum MobileNetV3 und nicht ein größeres Netz?

Das Modell soll **im Browser auf dem Handy** laufen, offline und ohne Server. MobileNetV3 ist
dafür gebaut: 4,2 Mio. Parameter, ~17 MB, eine Analyse dauert auf dem Handy Sekundenbruchteile.
Größere Netze wären auf Dermoskopie-Benchmarks besser, aber hier zählen Größe, Tempo und
Privatsphäre. Außerdem lief das ganze Training auf einer CPU ohne GPU.

### Was macht der „domänen-balancierte Sampler“?

In MILK10k sind 70 % der Fotos bösartig, in SLICE-3D 0,1 %. Ohne Gegenmaßnahme lernt ein Netz
„Klinikfoto → Krebs, Scanner-Ausschnitt → harmlos“ – also die Bildquelle statt der Hautstelle.
Der Sampler stellt jeden Batch so zusammen, dass in jeder Bildart bösartige und nicht bösartige
Bilder in festen Anteilen vorkommen. Die Bildquelle verrät dann nichts mehr über das Label.

### Was sind „Mengen-Labels“?

Das Netz unterscheidet 7 Diagnose-Gruppen (Melanom, Basalzellkarzinom, Plattenepithelkarzinom,
aktinische Keratose, Muttermal, gutartige Keratose, andere gutartige). Bei 400 000 SLICE-3D-Bildern
steht aber nur „gutartig“. Statt diese Bilder wegzuwerfen, wird für sie die **Summe** der drei
gutartigen Wahrscheinlichkeiten maximiert. Für vollständig annotierte Bilder ist das genau die
übliche Kreuzentropie.

### Warum werden Bilder nach Patient bzw. Läsion getrennt?

Wenn Fotos derselben Person (oder Kamerafoto und Dermoskopie derselben Stelle) in Training und Test
landen, erkennt das Modell im Test teils nur Wiedergesehenes. Das treibt die Zahlen künstlich hoch –
dasselbe Problem wie „intra-patient“ beim EKG. Hier hängen Bilder über Patient **oder** Läsion
zusammen (Union-Find), und jede so entstandene Gruppe liegt komplett in einem Split. Ein Test
prüft das automatisch.

### Was heißt „nicht beurteilbar“?

Das Modell vergleicht die interne Darstellung (Embedding) eines Fotos mit denen der Trainingsbilder
(PCA + Mahalanobis-Abstand + Rekonstruktionsfehler). Liegt ein Foto weiter weg als 99 % der
Validierungsbilder, sagt die App „nicht zuverlässig beurteilbar“ – z. B. bei Ausschlägen, Tattoos
oder Fotos ohne einzelne Hautstelle. Das ist eine Heuristik, kein Garant.

### Wohin schaut das Modell?

Die App deckt nacheinander 36 Bereiche des Fotos mit der mittleren Hautfarbe ab und misst, wie stark
der Score jeweils sinkt (Verdeckungsanalyse). Bereiche, deren Abdecken den Score am meisten senkt,
werden rot markiert. Liegt die Markierung neben der Hautstelle (z. B. auf einer Stiftmarkierung),
ist das ein Warnsignal für eine Abkürzung im Modell.

### Darf man so eine App veröffentlichen?

Als Lern- und Portfolio-Projekt mit klarem Hinweis: ja. Als Werkzeug, das Menschen sagt, ob sie zum
Arzt sollen: nur als zugelassenes Medizinprodukt (EU-MDR, Regel 11, mindestens Klasse IIa) mit
klinischer Bewertung. Der Datenschutz ist hier einfach gelöst: Das Foto verlässt das Gerät nie.
