#!/usr/bin/env bash
# Run on 10.2.8.73 when Jenkins starts a container without --env-file (SECRET_KEY error).
#
# Usage:
#   ./scripts/docker-run-taxsync-backend.sh [IMAGE] [ENV_FILE]
#
# Examples:
#   ./scripts/docker-run-taxsync-backend.sh tt0docker/stage_taxsync_be:latest /home/product-labs/Taxsync_Backend/.env
#   ./scripts/docker-run-taxsync-backend.sh smartdocs-backend:latest backend/.env
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${1:-smartdocs-backend:latest}"
ENV_FILE="${2:-}"

if [[ -z "$ENV_FILE" ]]; then
  for f in "$ROOT/backend/.env" "$ROOT/.env" "./.env" "/home/product-labs/Taxsync_Backend/.env"; do
    if [[ -f "$f" ]]; then
      ENV_FILE="$f"
      break
    fi
  done
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: No env file found. Pass path as 2nd argument (must contain SECRET_KEY, DATABASE_URL)."
  exit 1
fi

chmod 600 "$ENV_FILE" 2>/dev/null || true

echo "Stopping any old backend on :8025..."
docker rm -f smartdocs-backend 2>/dev/null || true

echo "Starting smartdocs-backend from $IMAGE with --env-file $ENV_FILE"
docker run -d \
  --name smartdocs-backend \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  -p 8025:8000 \
  "$IMAGE"

sleep 4
if curl -fsS --max-time 15 "http://127.0.0.1:8025/api/health/live" >/dev/null; then
  echo "OK: http://127.0.0.1:8025/api/health/live"
  curl -fsS "https://canvas.iiit.ac.in/taxsyncbestage/api/health/live" && echo " (public OK)" || echo "WARN: public URL not ready yet"
else
  echo "FAIL — logs:"
  docker logs smartdocs-backend --tail 40
  exit 1
fi
