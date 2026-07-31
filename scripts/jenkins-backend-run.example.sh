#!/usr/bin/env bash
# Example campus/Jenkins runtime for Taxsync_Backend image (flat repo).
# Build succeeds in CI but nginx 502 means nothing is listening on host :8025.
#
# Common failures:
#   1. Container exits immediately — start.sh could not find SECRET_KEY/DATABASE_URL
#      (fix: --env-file .env OR use image with tracked .env + fixed start.sh)
#   2. Wrong port publish — app listens on 8000 inside; use -p 8025:8000 not 8025:8025
#   3. compose not restarted after autotrigger build — run deploy-prod.sh on 10.2.8.73
#
# On 10.2.8.73 prefer full stack:
#   cd Smart-Document-Management-System && ./deploy-prod.sh
set -euo pipefail

IMAGE="${1:-taxsync-backend:latest}"
ENV_FILE="${2:-.env}"

docker rm -f smartdocs-backend-jenkins 2>/dev/null || true

docker run -d --name smartdocs-backend-jenkins \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  -p 8025:8000 \
  "$IMAGE"

sleep 3
curl -fsS "http://127.0.0.1:8025/api/health/live" && echo " OK"
