#!/usr/bin/env bash
# Vuelve manualmente a una versión anterior del modelo (AD4).
#   bash rollback_modelo.sh            -> lista las versiones disponibles
#   bash rollback_modelo.sh v2026...   -> activa esa versión
set -euo pipefail
ROOT=/opt/reco/models
if [ $# -eq 0 ]; then
  echo "Vigente: $(cat $ROOT/current)"; echo "Disponibles:"; ls -1 "$ROOT" | grep '^v'; exit 0
fi
[ -d "$ROOT/$1" ] || { echo "No existe $ROOT/$1"; exit 1; }
echo "$1" > "$ROOT/current"
docker restart reco-api >/dev/null
sleep 3
curl -fsS http://127.0.0.1:8000/salud; echo
