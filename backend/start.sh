#!/bin/bash
set -euo pipefail

# Start script for deployment (runs both Celery worker and Uvicorn in one container)
# For Docker Compose, the services are split into separate containers

if [ "${RENDER:-}" = "true" ] || [ "${COMBINED_MODE:-}" = "true" ]; then
    echo "Starting in combined mode (Celery + Uvicorn)..."
    celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1 --pool=prefork --max-memory-per-child=256000 &
    CELERY_PID=$!
    echo "Celery worker started (PID: $CELERY_PID)"

    # Trap signals to gracefully shut down Celery when the container stops
    cleanup() {
        echo "Shutting down Celery worker (PID: $CELERY_PID)..."
        kill -TERM "$CELERY_PID" 2>/dev/null
        wait "$CELERY_PID" 2>/dev/null
        echo "Celery worker stopped."
    }
    trap cleanup SIGTERM SIGINT EXIT
fi

echo "Starting Uvicorn..."
uvicorn app.main:app --host 0.0.0.0 --port 8000
