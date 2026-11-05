# Hautstellen-Triage – Entwickler-Kommandos (aus dem Repo-Root ausführen)

PY     ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
NPM    ?= npm
RUN    ?= artifacts/runs/e4_melanoma
CONFIG ?= configs/e4_melanoma.json

.PHONY: help install data preprocess extra baseline train evaluate final export examples test web dev smoke docs all

help:
	@echo "make install | data | preprocess | extra | baseline | train [CONFIG=…] | evaluate [RUN=…] | final [RUN=…] | export [RUN=…] | docs | examples | test | web | smoke | dev"

install:      ## Python-venv + Paket + Web-Abhängigkeiten
	test -x $(PY) || python3 -m venv .venv
	$(PY) -m pip install -c constraints.txt -e '.[dev]'
	cd web && $(NPM) ci

data:         ## ISIC-Archiv (S3) + SCIN laden, ~3 GB
	$(PY) -I -m skintriage.cli download

preprocess:   ## Katalog, Splits (nach Patient/Läsion) und 160-px-Memmap (~6,6 GB)
	$(PY) -I -m skintriage.cli preprocess

extra:        ## Zusatz-Dermoskopie mit Melanom-Schwerpunkt für E4 (~15 400 Bilder, 1,2 GB)
	$(PY) -I -m skintriage.data.extra

baseline:     ## E0: ImageNet-Merkmale + logistische Regression
	$(PY) -I -m skintriage.evaluation.baseline

train:        ## Modell trainieren (nur Train, Val je Epoche)
	$(PY) -I -m skintriage.cli train --config $(CONFIG) --out $(RUN)

evaluate:     ## Auswertung nur auf Val (Modellauswahl)
	$(PY) -I -m skintriage.cli evaluate --run $(RUN) --splits val

final:        ## EINMALIG nach Einfrieren der Konfiguration: Val + Test + extern (PAD-UFES-20)
	$(PY) -I -m skintriage.cli evaluate --run $(RUN) --splits val,test,external

export:       ## ONNX + meta.json + metrics.json nach web/public
	$(PY) -I -m skintriage.cli export --run $(RUN)

docs:         ## Ergebnis-Blöcke in README/EXPERIMENTS aus metrics.json neu schreiben
	$(PY) -I scripts/update_docs.py

examples:     ## Beispielbilder (PAD-UFES-20, CC BY) für die Web-App
	$(PY) -I scripts/make_examples.py

test:         ## Python-Tests
	$(PYTEST) -q

web:          ## Web-App bauen (web/dist)
	cd web && $(NPM) run build

smoke:        ## Ende-zu-Ende-Test im Browser + Screenshots (nach make web)
	node scripts/web_smoke.mjs

dev:          ## Web-App lokal entwickeln
	cd web && $(NPM) run dev

all: test web
