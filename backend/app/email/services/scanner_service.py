"""Gmail scanner orchestration — Phase 15 EMAIL-07.

APScheduler-driven per-credential polling. Pitfall 2 mitigated via Redis
distributed lock; Pitfall 6 mitigated via set_tenant_context_for_celery
inside the task body (lives in tasks/scanner_task.py).
"""
from __future__ import annotations

import logging
import os

import redis
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.compliance.services.scheduler import get_scheduler
from app.email.models.fetch_log import GmailFetchLog

logger = logging.getLogger(__name__)
_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
    return _redis


def schedule_gmail_scan(credential_id: int, cadence_minutes: int = 15) -> None:
    sched = get_scheduler()
    if sched is None:
        logger.warning(
            "APScheduler unavailable; gmail scan not scheduled for %s",
            credential_id,
        )
        return
    sched.add_job(
        func="app.email.tasks.scanner_task:run_scan",
        trigger=IntervalTrigger(minutes=cadence_minutes),
        args=[credential_id],
        id=f"gmail_scan_{credential_id}",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )


def acquire_scan_lock(credential_id: int) -> bool:
    r = _get_redis()
    return bool(
        r.set(f"gmail:scan_lock:{credential_id}", "1", nx=True, ex=300)
    )


def release_scan_lock(credential_id: int) -> None:
    r = _get_redis()
    r.delete(f"gmail:scan_lock:{credential_id}")


def record_fetch_outcome(
    db: Session,
    credential_id: int,
    status: str,
    messages_processed: int = 0,
    error_message: str | None = None,
) -> GmailFetchLog:
    log = GmailFetchLog(
        credential_id=credential_id,
        status=status,
        messages_processed=messages_processed,
        error_message=error_message[:500] if error_message else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    if status == GmailFetchLog.STATUS_FETCH_FAILED:
        recent = (
            db.query(GmailFetchLog)
            .filter(GmailFetchLog.credential_id == credential_id)
            .order_by(GmailFetchLog.started_at.desc())
            .limit(2)
            .all()
        )
        if (
            len(recent) == 2
            and all(r.status == GmailFetchLog.STATUS_FETCH_FAILED for r in recent)
        ):
            try:
                from app.compliance.services.alert_service import (
                    dispatch_non_notice_alert,
                    resolve_recipients,
                )
                from app.email.models.credential import GmailCredential

                cred = (
                    db.query(GmailCredential)
                    .filter(GmailCredential.id == credential_id)
                    .first()
                )
                if cred is not None:
                    recipients = resolve_recipients(
                        db,
                        client_id=cred.client_id,
                        recipient_roles=("compliance_head", "ca_consultant"),
                    )
                    dispatch_non_notice_alert(
                        db,
                        client_id=cred.client_id,
                        alert_type="gmail_fetch_repeated_failure",
                        channels=["email", "websocket"],
                        recipients=recipients,
                        payload={
                            "credential_id": credential_id,
                            "consecutive_failures": 2,
                        },
                    )
            except Exception as e:
                logger.warning(
                    "fetch.repeated_failure alert emit failed: %s",
                    e,
                )
    return log
