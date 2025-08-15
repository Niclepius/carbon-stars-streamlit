#!/usr/bin/env bash
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/Niclepius/carbon-stars-streamlit.git}"
TEST_DIR="${TEST_DIR:-/tmp/carbon-stars-streamlit-test}"
IMAGE_TAG="${IMAGE_TAG:-carbon-stars:obs}"
PORT="${PORT:-8501}"
WAIT_SECS="${WAIT_SECS:-60}"
PAUSE="${PAUSE:-1}"

log(){ echo "[$(date +%H:%M:%S)] $*"; }
fail(){ echo -e "\n❌ $*"; [ "$PAUSE" = "1" ] && read -p "Enter para salir..."; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || fail "Falta '$1'"; }
need git; need docker; need curl
docker info >/dev/null 2>&1 || fail "Docker no responde."

log "Clonando en limpio -> $TEST_DIR"
rm -rf "$TEST_DIR"
git clone "$REPO_URL" "$TEST_DIR"
cd "$TEST_DIR"

log "Normalizando permisos"
sed -i 's/\r$//' start_app.sh || true
chmod +x start_app.sh || true

log "Construyendo imagen -> $IMAGE_TAG"
docker build -t "$IMAGE_TAG" .

log "Lanzando contenedor"
docker rm -f carbon-stars-app >/dev/null 2>&1 || true
docker run -d --name carbon-stars-app -p "${PORT}:8501" "$IMAGE_TAG" >/dev/null

log "Chequeando salud en http://localhost:${PORT}"
for i in $(seq 1 "$WAIT_SECS"); do
  if curl -fsS "http://127.0.0.1:${PORT}" >/dev/null; then
    echo "✅ App OK en http://localhost:${PORT}"
    echo "Detener: docker rm -f carbon-stars-app"
    [ "$PAUSE" = "1" ] && read -p "Enter para salir..."
    exit 0
  fi; sleep 1
done

echo "Logs del contenedor:"
docker logs --tail=200 carbon-stars-app || true
fail "No respondió a tiempo."

