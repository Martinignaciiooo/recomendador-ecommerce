#!/usr/bin/env bash
# Despliegue con verificación de salud y rollback automático.
# Lo ejecuta el pipeline CI/CD (vía SSH) o una persona en la instancia.
#
# 1. Construye la imagen con la versión actual del código (tag = commit)
# 2. Reemplaza el contenedor
# 3. Verifica /salud; si falla, vuelve a levantar la imagen anterior
set -euo pipefail
APP=/opt/reco/app
NAME=reco-api
cd "$APP"
TAG="$(git -c safe.directory="$APP" rev-parse --short HEAD)"
IMAGE="reco-api:${TAG}"

# Registro de modelos persistente: se siembra desde el repo solo la primera vez.
# Después lo administra retrain.sh, sin que un despliegue de código lo pise.
if [ ! -f /opt/reco/models/current ]; then
  echo ">> Sembrando el registro de modelos desde el repositorio"
  cp -r "$APP"/out/models/. /opt/reco/models/
fi

echo ">> Construyendo ${IMAGE}"
docker build -q -t "$IMAGE" "$APP"

PREV="$(docker inspect --format '{{.Config.Image}}' "$NAME" 2>/dev/null || true)"

LOGS=()
if [ -n "${AWSLOGS_GROUP:-}" ]; then   # opcional: enviar logs a CloudWatch
  LOGS=(--log-driver=awslogs --log-opt "awslogs-group=${AWSLOGS_GROUP}"
        --log-opt "awslogs-region=${AWS_REGION:-us-east-1}" --log-opt awslogs-create-group=true)
fi

run() {
  docker run -d --name "$NAME" --restart unless-stopped \
    -p 127.0.0.1:8000:8000 \
    -v /opt/reco/models:/app/models:ro -e MODEL_ROOT=/app/models \
    -v /opt/reco/data:/app/data \
    --env-file /opt/reco/.env "${LOGS[@]}" "$1" >/dev/null
}

healthy() {
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:8000/salud >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

docker rm -f "$NAME" >/dev/null 2>&1 || true
echo ">> Iniciando ${IMAGE}"
run "$IMAGE"

if healthy; then
  echo ">> OK: $(curl -fsS http://127.0.0.1:8000/salud)"
  docker image prune -f >/dev/null
else
  echo "!! La versión nueva no pasó el health check"
  docker logs --tail 40 "$NAME" || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  if [ -n "$PREV" ]; then
    echo ">> ROLLBACK a ${PREV}"
    run "$PREV" && healthy && echo ">> Rollback exitoso"
  fi
  exit 1
fi
