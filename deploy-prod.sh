#!/bin/bash
# deploy-prod.sh — Deploy full TaxSync production stack on 10.2.8.73.
# Run from: ~/Smart-Document-Management-System
#
# Deploys: Redis, Backend, Celery workers, Frontend — all as Docker services.
# Secrets load only from server-local `.env.prod` (never committed).
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
FRONTEND_DIR="../taxsync-frontend"
ENV_FILE=".env.prod"

echo "=== TaxSync Production Deploy ==="

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE is missing."
  echo "  Copy the template and fill real secrets on this host only:"
  echo "    cp .env.prod.example .env.prod && chmod 600 .env.prod && \$EDITOR .env.prod"
  echo "  See docs/security/SECRET_ROTATION_2026-07-16.md"
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: $COMPOSE_FILE not found (run from repo root)."
  exit 1
fi

# Refuse to deploy if compose still has high-confidence embedded secrets
if grep -nE 'AIza[0-9A-Za-z_-]{20,}|re_[A-Za-z0-9]{20,}|SECRET_KEY:\s*[A-Za-z0-9_=-]{32,}' \
    "$COMPOSE_FILE" >/dev/null 2>&1; then
  echo "ERROR: $COMPOSE_FILE appears to contain hardcoded secrets."
  echo "  Secrets must live only in $ENV_FILE. Aborting."
  exit 1
fi

chmod 600 "$ENV_FILE" 2>/dev/null || true

echo "[1/6] Pulling latest backend code from gh-backend staging..."
git pull gh-backend staging

echo "[2/6] Pulling latest frontend code..."
if [[ -d "$FRONTEND_DIR/.git" ]]; then
  (
    cd "$FRONTEND_DIR"
    git pull origin staging
  )
else
  echo "  WARN: $FRONTEND_DIR is not a git checkout; skipping frontend pull."
fi

echo "[3/6] Building + starting full stack (Redis, Backend, Celery, Frontend)..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

echo "[4/6] Running database migrations..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm celery_worker alembic upgrade head

echo "[5/6] Disabling any old bare-metal backend unit (backend now runs in Docker)..."
if systemctl list-unit-files 2>/dev/null | grep -q '^taxsync-backend\.service'; then
  sudo systemctl disable --now taxsync-backend 2>/dev/null || true
  echo "  Stopped + disabled taxsync-backend systemd unit (freed host :8025 for the container)."
else
  echo "  No taxsync-backend systemd unit installed; nothing to disable."
fi

echo "[6/6] Quick health probes..."
sleep 3
if curl -fsS --max-time 10 "http://127.0.0.1:8025/api/health/live" >/dev/null 2>&1; then
  echo "  Backend live: OK (http://127.0.0.1:8025/api/health/live)"
else
  echo "  WARN: backend health not ready yet — check: docker compose -f $COMPOSE_FILE logs backend --tail 50"
fi

echo ""
echo "=== Deploy complete ==="
echo "Verify:"
echo "  docker compose -f $COMPOSE_FILE ps"
echo "  curl https://canvas.iiit.ac.in/taxsyncbestage/api/health/"
echo "  curl -I https://canvas.iiit.ac.in/taxsyncfestage/  # expect 200"
echo ""
echo "Check logs:"
echo "  docker compose -f $COMPOSE_FILE logs celery_worker --tail 20"
echo "  docker compose -f $COMPOSE_FILE logs compliance_worker --tail 20"
echo "  docker compose -f $COMPOSE_FILE logs frontend --tail 20"
echo "  # If Google sign-in fails, verify backend is running:"
echo "  curl http://10.2.8.73:8025/api/health/live"
