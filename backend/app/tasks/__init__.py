"""Celery application configuration."""

from celery import Celery
from app.config import settings

celery_app = Celery(
    "smart_docs",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.document_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    worker_max_memory_per_child=512000,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    broker_pool_limit=10,
    redis_max_connections=20,
    # Default safety timeouts for any task that doesn't set its own.
    # Prevents new tasks from hanging forever if a developer forgets to set limits.
    task_time_limit=900,           # hard kill after 15 min
    task_soft_time_limit=840,      # raise SoftTimeLimitExceeded at 14 min
    task_annotations={
        "app.tasks.document_tasks.process_document_task": {"rate_limit": "20/m"},
    },
)
