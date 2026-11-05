# Hautstellen-Triage – Entwickler-Kommandos (aus dem Repo-Root ausführen)

PY     ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
NPM    ?= npm
RUN    ?= artifacts/runs/e3_final
CONFIG ?= configs/e3_final.json

.PHONY: help install data preprocess baseline train evaluate final export examples test web dev all

help:
	@echo "make install | data | preprocess | baseline | train [CONFIG=…] | evaluate [RUN=…] | final [RUN=…] | export [RUN=…] | examples | test | web | dev"

install:      ## Python-venv + Paket + Web-Abhängigkeiten
	test -x $(PY) || python3 -m venv .venv
	$(PY) -m pip install -c constraints.txt -e '.[dev]'
	cd web && $(NPM) ci

data:         ## ISIC-Archiv (S3) + SCIN laden, ~3 GB
	$(PY) -I -m skintriage.cli download

preprocess:   ## Katalog, Splits (nach Patient/Läsion) und 160-px-Memmap (~6,6 GB)
	$(PY) -I -m skintriage.cli preprocess

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

examples:     ## Beispielbilder (PAD-UFES-20, CC BY) für die Web-App
	$(PY) -I scripts/make_examples.py

test:         ## Python-Tests
	$(PYTEST) -q

web:          ## Web-App bauen (web/dist)
	cd web && $(NPM) run build

dev:          ## Web-App lokal entwickeln
	cd web && $(NPM) run dev

all: test web
