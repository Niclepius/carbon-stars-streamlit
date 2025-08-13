#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

IMAGE_TAG="carbon-stars:$(git rev-parse --short HEAD 2>/dev/null || echo latest)"

echo "[1/3] Construyendo imagen -> $IMAGE_TAG"
docker build -t "$IMAGE_TAG" .

echo "[2/3] Matando contenedor previo (si existe)"
docker rm -f carbon-stars-app 2>/dev/null || true

echo "[3/3] Lanzando en http://localhost:8501"
docker run --name carbon-stars-app --rm -p 8501:8501 "$IMAGE_TAG"
