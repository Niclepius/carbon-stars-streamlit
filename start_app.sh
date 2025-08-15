#!/usr/bin/env bash
set -euo pipefail

APP_NAME="carbon-stars"
IMAGE_TAG="${APP_NAME}:obs"
CONTAINER_NAME="${APP_NAME}_run"
PORT="8501"

echo ">> Parando contenedor previo (${CONTAINER_NAME}) si existe..."
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

echo ">> Construyendo imagen (${IMAGE_TAG})..."
docker build -t "${IMAGE_TAG}" .

echo ">> Ejecutando contenedor en http://localhost:${PORT} ..."
docker run -d --name "${CONTAINER_NAME}" -p ${PORT}:8501 "${IMAGE_TAG}"

echo ">> Para ver logs: docker logs -f ${CONTAINER_NAME}"
