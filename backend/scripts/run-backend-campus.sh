#!/usr/bin/env bash
# Taxsync_Backend — start API container on campus (10.2.8.73).
# Usage: ./scripts/run-backend-campus.sh [IMAGE]
# Example: ./scripts/run-backend-campus.sh tt0docker/stage_taxsync_be:12
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
IMAGE="${1:-}"

if [[ -z "$IMAGE" ]]; then
  echo "Usage: $0 <jenkins-image>   e.g. tt0docker/stage_taxsync_be:12"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "ERROR: $ROOT/.env missing. Use staging branch (tracked in private repo)."
  exit 1
fi

chmod 600 .env 2>/dev/null || true

docker rm -f smartdocs-backend 2>/dev/null || true

echo "Starting smartdocs-backend: $IMAGE (env: $ROOT/.env, ports 8025:8000)"
docker run -d \
  --name smartdocs-backend \
  --restart unless-stopped \
  --env-file "$ROOT/.env" \
  -p 8025:8000 \
  "$IMAGE"

sleep 4
if curl -fsS --max-time 15 "http://127.0.0.1:8025/api/health/live" >/dev/null; then
  echo "OK: http://127.0.0.1:8025/api/health/live"
else
  docker logs smartdocs-backend --tail 50
  exit 1
fi
