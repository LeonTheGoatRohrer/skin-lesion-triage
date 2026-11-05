# Skin Spot Check – skin cancer triage from phone photos (ISIC)

[Deutsch](README.md) · **English**

Take a photo of a mole or skin spot → a small neural network estimates **directly in the browser**
how conspicuous it looks: as a **traffic light** (inconspicuous · keep an eye on it · have it
checked) and as a **percentage** (“more conspicuous than 87% of benign reference photos”). Plus a
**mole diary** that makes changes over time visible, and the **ABCDE rule** for self-checks. The
photo never leaves the device.

> Learning and portfolio project. **Not a medical device**, no diagnosis, does not replace a doctor.

![Result view: traffic light, conspicuousness, similarity to diagnosis groups, heatmap](docs/screenshots/check-result.png)

<!-- RESULTS:START -->
(results follow)
<!-- RESULTS:END -->

## Data

The large public collection of skin images is the **ISIC archive** (> 500,000 images). Because phone
photos look different from dermoscopy (contact microscope) images, the project mainly uses
**phone-like image types**: clinical camera photos (MILK10k, MSK) and crops from 3D total-body
photography (SLICE-3D / ISIC 2024). **PAD-UFES-20** (real smartphone photos from Brazil) is never
used for training or model selection – it is the external test. Google **SCIN** (crowdsourced phone
photos, mostly rashes) only tests the “cannot be assessed” check.

## Method

- Splits grouped by patient **or** lesion (union-find) – no leakage between train/val/test.
- Domain-balanced sampler (image type × malignant) so the network cannot learn “clinic photo =
  cancer”.
- 7 diagnosis groups with set-valued labels (if only “benign” is known, the sum of benign groups
  is maximized); triage score = log P(malignant) − log P(not malignant).
- MobileNetV3-Large, 128 × 128 px, AdamW + cosine + EMA, phone-realism augmentation, trained on a
  4-core CPU.
- Traffic light thresholds set on validation only (yellow at 95% sensitivity, red at 90%
  specificity); the percentage is a percentile among benign validation photos (prevalence-free).
- “Cannot be assessed”: PCA-Mahalanobis + reconstruction error on embeddings.
- One ONNX graph with normalization, 4× test-time augmentation, score and OOD distance; float16
  weights; parity tests PyTorch ↔ ONNX and Python ↔ JavaScript.

## Quick start

```bash
make install data preprocess baseline
make train CONFIG=configs/e1_mix.json RUN=artifacts/runs/e1_mix
make final RUN=…    # once: validation + test + external
make export RUN=…   # ONNX + meta.json + metrics.json -> web/public
make test web && node scripts/web_smoke.mjs
```

## License

Code: MIT. Data and trained model: see [DATA_LICENSE.md](DATA_LICENSE.md) (parts CC BY-NC →
model for non-commercial use only).
