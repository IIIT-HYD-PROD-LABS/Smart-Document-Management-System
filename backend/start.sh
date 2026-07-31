#!/bin/bash
set -euo pipefail

# Loads .env from the working directory (baked into image via COPY . or --env-file).

load_dotenv_into_shell() {
  local env_file="${1:-.env}"
  [[ -f "$env_file" ]] || return 0
  eval "$(ENV_FILE="$env_file" python - <<'PY'
import os, shlex
from pathlib import Path
from dotenv import dotenv_values

path = Path(os.environ["ENV_FILE"])
for key, val in (dotenv_values(path) or {}).items():
    if not val:
        continue
    if os.environ.get(key):
        continue
    print(f"export {key}={shlex.quote(val)}")
PY
)"
}

for candidate in "${ENV_FILE:-}" "/app/.env" ".env"; do
  if [[ -n "$candidate" && -f "$candidate" ]]; then
    load_dotenv_into_shell "$candidate"
  fi
done

required_vars=(SECRET_KEY DATABASE_URL)
for v in "${required_vars[@]}"; do
  if [[ -z "${!v:-}" ]]; then
    echo "ERROR: $v is not set." >&2
    echo "  Ensure Taxsync_Backend staging .env has SECRET_KEY and DATABASE_URL." >&2
    ls -la /app/.env .env 2>/dev/null || true
    exit 1
  fi
done

echo "TaxSync backend boot:"
echo "  FRONTEND_URL=${FRONTEND_URL:-<unset>}"
echo "  BACKEND_URL=${BACKEND_URL:-<unset>}"
echo "  GOOGLE_OAUTH=$([[ -n "${GOOGLE_CLIENT_ID:-}" ]] && echo configured || echo missing)"
echo "  DATABASE_URL host=$(python - <<'PY'
import os, urllib.parse
u = os.environ.get("DATABASE_URL", "")
print(urllib.parse.urlparse(u).hostname or "?")
PY
)"

if [ "${RENDER:-}" = "true" ] || [ "${COMBINED_MODE:-}" = "true" ]; then
    echo "Starting in combined mode (Celery + Uvicorn)..."
    celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1 --pool=prefork --max-memory-per-child=256000 &
    CELERY_PID=$!
    echo "Celery worker started (PID: $CELERY_PID)"

    cleanup() {
        echo "Shutting down Celery worker (PID: $CELERY_PID)..."
        kill -TERM "$CELERY_PID" 2>/dev/null
        wait "$CELERY_PID" 2>/dev/null
        echo "Celery worker stopped."
    }
    trap cleanup SIGTERM SIGINT EXIT
fi

UVICORN_PORT="${PORT:-8000}"
echo "Starting Uvicorn on 0.0.0.0:${UVICORN_PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${UVICORN_PORT}"
