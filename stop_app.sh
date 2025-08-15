#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="carbon-stars_run"

echo ">> Deteniendo contenedor (${CONTAINER_NAME})..."
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
echo ">> Contenedor detenido y eliminado."
