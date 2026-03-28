#!/bin/bash
# Start script for Render deployment (runs both Celery worker and Uvicorn in one container)
# For Docker Compose, the services are split into separate containers

if [ "$RENDER" = "true" ] || [ "$COMBINED_MODE" = "true" ]; then
    echo "Starting in combined mode (Celery + Uvicorn)..."
    celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1 --pool=prefork --max-memory-per-child=256000 &
    CELERY_PID=$!
    echo "Celery worker started (PID: $CELERY_PID)"
fi

echo "Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
