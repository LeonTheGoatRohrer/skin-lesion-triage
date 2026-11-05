#!/usr/bin/env bash
# Experiment-Warteschlange: wartet auf einen laufenden Prozess, dann der Reihe nach.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
WAIT_PID=${1:-}
if [ -n "$WAIT_PID" ]; then while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 20; done; fi
log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a artifacts/logs/queue.log; }
log "eval e1_mix (val)";  $PY -I -m skintriage.cli evaluate --run artifacts/runs/e1_mix --splits val > artifacts/logs/eval_e1.log 2>&1
log "baseline e0";        $PY -I -m skintriage.evaluation.baseline > artifacts/logs/e0.log 2>&1
log "train e2_no_derm";   $PY -I -m skintriage.cli train --config configs/e2_no_derm.json --out artifacts/runs/e2_no_derm > artifacts/logs/e2.log 2>&1
log "eval e2 (val)";      $PY -I -m skintriage.cli evaluate --run artifacts/runs/e2_no_derm --splits val > artifacts/logs/eval_e2.log 2>&1
log "train e3_res160";    $PY -I -m skintriage.cli train --config configs/e3_res160.json --out artifacts/runs/e3_res160 > artifacts/logs/e3.log 2>&1
log "eval e3 (val)";      $PY -I -m skintriage.cli evaluate --run artifacts/runs/e3_res160 --splits val > artifacts/logs/eval_e3.log 2>&1
log "queue done"
