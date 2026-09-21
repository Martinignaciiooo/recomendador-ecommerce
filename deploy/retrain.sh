#!/usr/bin/env bash
# Reentrenamiento semanal (RF4). Programar con cron en la instancia:
#   0 3 * * 0  bash /opt/reco/app/deploy/retrain.sh >> /opt/reco/retrain.log 2>&1
#
# Incorpora los eventos que registró la API, entrena, y solo activa el modelo
# nuevo si no empeora al vigente (AD4). Luego reinicia la API para cargarlo.
set -euo pipefail
APP=/opt/reco/app
export MODEL_ROOT=/opt/reco/models EVENTS_DB=/opt/reco/data/eventos.db OPENBLAS_NUM_THREADS=1
cd "$APP"

if [ ! -f data/events.csv ]; then
  echo "Falta $APP/data/events.csv (copiarlo desde el ZIP del docente)"; exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi

echo "== $(date -Is) reentrenamiento =="
ANTES="$(cat /opt/reco/models/current)"
.venv/bin/python src/prepare_data.py
.venv/bin/python src/train_final.py
DESPUES="$(cat /opt/reco/models/current)"

if [ "$ANTES" != "$DESPUES" ]; then
  echo ">> Modelo nuevo activo ($DESPUES). Reiniciando API."
  docker restart reco-api >/dev/null
else
  echo ">> Se mantiene $ANTES"
fi
