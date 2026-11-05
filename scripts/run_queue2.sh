#!/usr/bin/env bash
# Warteschlange Teil 2: E2 (ohne Dermoskopie), dann E4 (Melanom-Fokus), jeweils mit Val-Auswertung.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
WAIT_PID=${1:-}
if [ -n "$WAIT_PID" ]; then while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 15; done; fi
log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a artifacts/logs/queue.log; }
log "train e2_no_derm";   $PY -I -m skintriage.cli train --config configs/e2_no_derm.json --out artifacts/runs/e2_no_derm > artifacts/logs/e2.log 2>&1
log "eval e2 (val)";      $PY -I -m skintriage.cli evaluate --run artifacts/runs/e2_no_derm --splits val > artifacts/logs/eval_e2.log 2>&1
while [ ! -f data/processed/extra.ok ] || [ ! -f configs/e4_melanoma.json ]; do sleep 30; done
log "train e4_melanoma";  $PY -I -m skintriage.cli train --config configs/e4_melanoma.json --out artifacts/runs/e4_melanoma > artifacts/logs/e4.log 2>&1
log "eval e4 (val)";      $PY -I -m skintriage.cli evaluate --run artifacts/runs/e4_melanoma --splits val > artifacts/logs/eval_e4.log 2>&1
log "queue2 done"
