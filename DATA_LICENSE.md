# Daten-Lizenz / Data License

*Deutsch · [English](#english)*

Der **Code** in diesem Repository steht unter der MIT-Lizenz (siehe [`LICENSE`](LICENSE)).
Die **Bilddaten** gehören nicht dazu und liegen nicht im Repository; `make data` lädt sie aus dem
öffentlichen ISIC-Archiv (S3) und dem SCIN-Bucket (Google Cloud Storage).

## Verwendete Datensätze

| Datensatz | Verwendung | Lizenz | Quelle / Zitat |
|---|---|---|---|
| **ISIC-Archiv, Metadaten-Snapshot** | Labels, Patient/Läsion, Bildtyp für alle Bilder | je Bild (s. u.) | International Skin Imaging Collaboration, <https://www.isic-archive.com> |
| **MILK10k** (Kamerafotos + Dermoskopie) | Training / Validierung / Test | CC BY-NC 4.0 | MILK study team, ISIC Archive, doi:10.34970/648456 |
| **SLICE-3D** (ISIC 2024, 3D-TBP-Ausschnitte) | Training / Validierung / Test (Stichprobe) | je Bild CC BY, CC BY-NC oder CC0 | Kurtansky N. R. et al. *The SLICE-3D dataset: 400,000 skin lesion image crops extracted from 3D TBP for skin cancer detection.* Scientific Data 11, 884 (2024). doi:10.1038/s41597-024-03743-w |
| **MSK-Kamerafotos** (ISIC-Archiv) | Training / Validierung / Test | CC BY / CC0 | Memorial Sloan Kettering Cancer Center, ISIC Archive |
| **PAD-UFES-20** (Smartphone-Fotos) | nur externer Test, Beispielbilder der Web-App | CC BY 4.0 | Pacheco A. G. C. et al. *PAD-UFES-20: A skin lesion dataset composed of patient data and clinical images collected from smartphones.* Data in Brief 32, 106221 (2020). doi:10.1016/j.dib.2020.106221 |
| **SCIN** (Google, crowdsourced) | nur Auswertung „nicht beurteilbar“; Bilder werden nicht gezeigt oder weitergegeben | SCIN Data Use License | Ward A. et al. *Creating an Empirical Dermatology Dataset Through Crowdsourcing With Web Search Advertisements.* JAMA Network Open (2024). <https://github.com/google-research-datasets/scin> |

## Abgeleitete Artefakte

- **Trainiertes Modell** (`web/public/model/model.onnx`): Teile der Trainingsdaten stehen unter
  CC BY-NC. Das Modell wird deshalb nur **nicht-kommerziell** bereitgestellt (Lern-/Portfolio-Zweck).
- **Beispielbilder** (`web/public/examples/`): vier Fotos aus PAD-UFES-20, CC BY 4.0,
  © Federal University of Espírito Santo (UFES), Zuordnung in `examples.json`.
- **Kennzahlen** (`web/public/data/metrics.json`) sind aus den oben genannten Daten abgeleitet;
  es gilt dieselbe Quellenangabe.

## Kein Medizinprodukt

Das Projekt ist ein Lern- und Portfolio-Projekt. Es stellt keine Diagnose und ersetzt keine
ärztliche Untersuchung. Eine Software, die Menschen eine Empfehlung zum Arztbesuch gibt, wäre in
der EU ein Medizinprodukt (MDR, Regel 11, mindestens Klasse IIa).

---

## English

The **code** is MIT-licensed. The **image data** is not part of the repository; `make data`
downloads it from the public ISIC archive (S3) and the SCIN bucket. Datasets, licenses and
citations are listed in the table above. Because parts of the training data are CC BY-NC, the
trained model is provided for **non-commercial** use only. The four example images are from
PAD-UFES-20 (CC BY 4.0). SCIN images are used for evaluation only and are never displayed or
redistributed. This is a learning/portfolio project and **not a medical device**.
