#!/usr/bin/env bash
# Prepara una instancia EC2 (Amazon Linux 2023) para el sistema de recomendación.
# Ejecutar UNA vez, como ec2-user:   bash bootstrap_ec2.sh <URL_DEL_REPO> <DOMINIO>
# Ejemplo:  bash bootstrap_ec2.sh https://github.com/equipo/reco.git reco-equipo3.duckdns.org
set -euo pipefail
REPO_URL="${1:?Falta la URL del repositorio}"
DOMINIO="${2:?Falta el dominio (ver GUIA_DESPLIEGUE_AWS.md, paso 3)}"

echo ">> Instalando Docker y Git"
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo ">> Creando estructura en /opt/reco"
sudo mkdir -p /opt/reco/{app,models,data}
sudo chown -R "$USER":"$USER" /opt/reco
# el contenedor corre con uid 1000: debe poder escribir la base de eventos
sudo chown -R 1000:1000 /opt/reco/data

echo ">> Clonando el repositorio"
git clone "$REPO_URL" /opt/reco/app

echo ">> Generando token de API y configuración"
if [ ! -f /opt/reco/.env ]; then
  echo "RECO_API_TOKEN=$(openssl rand -hex 24)" > /opt/reco/.env
  chmod 600 /opt/reco/.env
fi
sed "s/__DOMINIO__/${DOMINIO}/" /opt/reco/app/deploy/Caddyfile > /opt/reco/Caddyfile

echo ">> Levantando proxy HTTPS (Caddy, certificado automático de Let's Encrypt)"
sudo docker run -d --name caddy --restart unless-stopped --network host \
  -v /opt/reco/Caddyfile:/etc/caddy/Caddyfile:ro -v caddy_data:/data caddy:2

echo ">> Primer despliegue de la API"
sudo bash /opt/reco/app/deploy/deploy.sh

echo
echo "Listo. Tu token de API (guárdalo, lo pide el dashboard y los clientes):"
sudo cat /opt/reco/.env
echo "Panel: https://${DOMINIO}/dashboard"
