#!/usr/bin/env bash
# campus-start-backend.sh — Run ON 10.2.8.73 when nginx shows 502 and
# `docker ps` has no smartdocs-backend container.
#
# Jenkins / autotrigger Stage_Taxsync_BE only BUILDS the image. It does NOT
# create or start smartdocs-backend. Someone must run this script (or
# ./deploy-prod.sh) after each backend deploy.
#
# Usage (on campus host):
#   cd ~/Smart-Document-Management-System
#   git pull origin main
#   ./scripts/campus-start-backend.sh
#
# Expected container name: smartdocs-backend (port publish 8025:8000)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=""

echo "=== TaxSync: start missing backend container (host 10.2.8.73) ==="

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: Run from Smart-Document-Management-System repo root."
  echo "  Expected: $COMPOSE_FILE"
  exit 1
fi

if [[ -f ".env.prod" ]]; then
  ENV_FILE=".env.prod"
elif [[ -f "backend/.env" ]]; then
  ENV_FILE="backend/.env"
  echo "NOTE: using backend/.env (no .env.prod on host)."
else
  echo "ERROR: Need secrets in .env.prod or backend/.env before starting backend."
  exit 1
fi

COMPOSE_ENV=(--env-file "$ENV_FILE")
if [[ -f "backend/.env" && "$ENV_FILE" != "backend/.env" ]]; then
  COMPOSE_ENV+=(--env-file backend/.env)
fi

echo ""
echo "[1/4] Current containers (looking for smartdocs-backend):"
if docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|smartdocs-|taxsync-frontend' || true; then
  :
fi
if docker ps -a --format '{{.Names}}' | grep -qx 'smartdocs-backend'; then
  echo "  smartdocs-backend exists but may be stopped — will recreate via compose."
else
  echo "  smartdocs-backend is MISSING (this is why canvas API returns 502)."
fi

echo ""
echo "[2/4] Pull latest backend export (optional but recommended)..."
if git remote get-url gh-backend &>/dev/null; then
  git pull gh-backend staging || echo "  WARN: gh-backend pull failed; continuing with local tree."
else
  echo "  SKIP: no gh-backend remote; use git pull origin main if needed."
fi

if [[ ! -f backend/.env ]]; then
  echo "ERROR: backend/.env missing. After gh-backend pull it should exist in private repo."
  exit 1
fi

echo ""
echo "[3/4] Start Redis + backend + workers (creates smartdocs-backend)..."
docker compose -f "$COMPOSE_FILE" "${COMPOSE_ENV[@]}" up -d --build \
  redis backend celery_worker compliance_worker

echo ""
echo "[4/4] Health check on host :8025 ..."
sleep 4
if curl -fsS --max-time 15 "http://127.0.0.1:8025/api/health/live" >/dev/null; then
  echo "  OK: backend listening on http://127.0.0.1:8025"
else
  echo "  FAIL: nothing on :8025 yet. Logs:"
  docker compose -f "$COMPOSE_FILE" logs backend --tail 40
  echo ""
  echo "Common fixes:"
  echo "  - Container exited: docker compose -f $COMPOSE_FILE ps -a"
  echo "  - Wrong port map: must be 8025:8000 (see docker-compose.prod.yml)"
  echo "  - Old image without start.sh fix: git pull && rebuild (staging commit 0b41577+)"
  exit 1
fi

echo ""
echo "=== Done ==="
echo "Public check:"
echo "  curl -fsS https://canvas.iiit.ac.in/taxsyncbestage/api/health/live"
echo "Google OAuth redirect URI (Google Cloud console):"
echo "  https://canvas.iiit.ac.in/taxsyncbestage/api/auth/callback/google"
echo ""
echo "Full stack (includes frontend rebuild): ./deploy-prod.sh"
