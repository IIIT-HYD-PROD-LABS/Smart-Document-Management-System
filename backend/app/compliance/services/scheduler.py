"""APScheduler integration — Phase 11 D-01.

Lazy-initialized BackgroundScheduler with PostgreSQL JobStore. Jobs survive
worker restarts. Triggered from notice_service.transition_notice_status
when a notice gains a deadline OR the deadline changes.

Job IDs follow the convention `notice_{notice_id}_{alert_type}` so callers
can re-schedule (replace_existing=True) and cancellations are O(1).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, time, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    """Returns the singleton BackgroundScheduler, lazily started.

    Init failure resets `_scheduler` to None so the next caller can retry,
    rather than caching a half-dead instance that keeps returning the same
    error. Engine uses `pool_pre_ping=True` so the Supabase pooler killing
    idle connections does not poison the jobstore.
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler not installed — alert scheduling disabled")
        return None

    jobstore_url = os.environ.get("DATABASE_URL_RUNTIME") or os.environ.get(
        "DATABASE_URL"
    )
    # Bound libpq connect at 10s so an unreachable DB fails fast instead of
    # blocking the FastAPI lifespan indefinitely. pool_pre_ping recovers from
    # idle disconnects (Supabase pooler trims sessions aggressively).
    jobstore = SQLAlchemyJobStore(
        url=jobstore_url,
        tablename="apscheduler_jobs",
        engine_options={
            "pool_pre_ping": True,
            "connect_args": {"connect_timeout": 10},
        },
    )
    scheduler = BackgroundScheduler(jobstores={"default": jobstore})
    try:
        scheduler.start()
    except Exception:
        # `start()` raised — the worker thread already inside the jobstore
        # may be in a bad state. Reset the singleton so the next caller
        # retries with a fresh BackgroundScheduler instead of returning
        # this poisoned one.
        logger.exception("scheduler_start_failed; resetting singleton")
        _scheduler = None
        raise
    _scheduler = scheduler
    return scheduler


def _job_id(notice_id: int, alert_type: str) -> str:
    return f"notice_{notice_id}_{alert_type}"


def schedule_deadline_alerts(notice_id: int, deadline: Optional[datetime]) -> dict[str, str]:
    """Schedule T-7/T-3/T-1/overdue jobs for a notice's deadline.

    Returns map of alert_type → job_id (or 'skipped' status).
    """
    from app.compliance.calendar.adjust import adjust_deadline

    sched = get_scheduler()
    if sched is None:
        return {"status": "scheduler_unavailable"}
    if deadline is None:
        return {"status": "no_deadline"}

    if isinstance(deadline, datetime):
        deadline_dt = deadline
    else:
        # date-only — fire at 09:00 IST = 03:30 UTC
        deadline_dt = datetime.combine(deadline, time(3, 30, tzinfo=timezone.utc))

    # Hardening — naïve datetimes can slip through (e.g. caller passes a
    # datetime parsed without tz). Normalize to UTC-aware so all downstream
    # arithmetic uses comparable timezone-aware values.
    if deadline_dt.tzinfo is None:
        deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)

    # L1 — shift the SCHEDULING basis to the next working day so the
    # T-7/T-3/T-1/overdue offsets fire relative to the holiday-aware
    # deadline, not the raw one (the preview endpoint already did this but
    # scheduling silently used the raw date). The stored response_deadline
    # column is untouched; only the scheduling math sees the adjusted date.
    # state_code is unavailable in this signature, so central-only holidays
    # are applied (parity with the orchestrator's cross-tenant dispatch).
    adjusted_date = adjust_deadline(deadline_dt.date())
    if adjusted_date != deadline_dt.date():
        deadline_dt = deadline_dt.replace(
            year=adjusted_date.year,
            month=adjusted_date.month,
            day=adjusted_date.day,
        )

    now = datetime.now(timezone.utc)
    out: dict[str, str] = {}
    all_in_past = True
    for delta_days, alert_type in (
        (7, "deadline_t7"),
        (3, "deadline_t3"),
        (1, "deadline_t1"),
        (0, "overdue"),
    ):
        if alert_type == "overdue":
            run_at = deadline_dt + timedelta(days=1)
        else:
            run_at = deadline_dt - timedelta(days=delta_days)
        if run_at <= now:
            out[alert_type] = "in_past"
            continue
        all_in_past = False
        try:
            sched.add_job(
                func=_dispatch_scheduled_alert,
                trigger="date",
                run_date=run_at,
                args=[notice_id, alert_type],
                id=_job_id(notice_id, alert_type),
                replace_existing=True,
                misfire_grace_time=3600,
            )
            out[alert_type] = "scheduled"
        except Exception:
            logger.exception(
                "schedule_deadline_alerts failed for notice %d alert %s",
                notice_id, alert_type,
            )
            out[alert_type] = "error"

    # Hardening (H-I) — when a deadline is already in the past at scheduling
    # time (back-dated notice or late entry), the original logic flipped all
    # four jobs to "in_past" and silently dispatched nothing. Schedule a
    # near-future overdue alert so ops + assignee still get a notification.
    if all_in_past:
        try:
            sched.add_job(
                func=_dispatch_scheduled_alert,
                trigger="date",
                run_date=now + timedelta(minutes=5),
                args=[notice_id, "overdue"],
                id=_job_id(notice_id, "overdue"),
                replace_existing=True,
                misfire_grace_time=3600,
            )
            out["overdue"] = "scheduled_near_future"
        except Exception:
            logger.exception(
                "schedule_deadline_alerts: near-future overdue schedule "
                "failed for notice %d",
                notice_id,
            )
            out["overdue_near_future"] = "error"

    return out


def cancel_deadline_alerts(notice_id: int) -> int:
    """Cancel all scheduled alerts for a notice. Used on transition to
    submitted/resolved/dismissed.

    Hardening (H-E second pass): JobLookupError is the expected state
    during cancellation idempotency. Any OTHER exception (JobStore
    connection drop, serialization failure) now gets logged.
    """
    try:
        from apscheduler.jobstores.base import JobLookupError
    except ImportError:
        JobLookupError = Exception  # type: ignore[assignment,misc]

    sched = get_scheduler()
    if sched is None:
        return 0
    cancelled = 0
    for alert_type in ("deadline_t7", "deadline_t3", "deadline_t1", "overdue"):
        try:
            sched.remove_job(_job_id(notice_id, alert_type))
            cancelled += 1
        except JobLookupError:
            continue
        except Exception:
            logger.exception(
                "cancel_deadline_alerts: unexpected error removing %s for notice %d",
                alert_type, notice_id,
            )
    return cancelled


def _dispatch_scheduled_alert(notice_id: int, alert_type: str) -> None:
    """Triggered by APScheduler. Loads notice + dispatches via alert_service.

    Hardening (CRIT-2 second pass): the first-pass hardening fix #1 patched
    Celery tasks to call set_tenant_context_for_celery so RLS sees a tenant
    context. APScheduler runs in the FastAPI process and was MISSED in
    that pass — empty ContextVars meant RLS fail-closed and every scheduled
    deadline alert silently no-opped. Mirror the alert_tasks.py pattern:
    cross_mode for the initial lookup, then narrow to the notice's tenant
    once we have notice.client_id.
    """
    from app.compliance.middleware.tenant_context import (
        set_tenant_context_for_celery,
    )
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.alert_service import (
        dispatch_alert,
        resolve_recipients,
    )
    from app.database import SessionLocal

    set_tenant_context_for_celery(client_id=None, user_id=None, cross_mode=True)

    db = SessionLocal()
    try:
        notice = db.get(ComplianceNotice, notice_id)
        if notice is None:
            logger.warning("scheduled alert: notice %d not found — skipping", notice_id)
            return

        set_tenant_context_for_celery(
            client_id=notice.client_id, user_id=None, cross_mode=False
        )
        if notice.status in ("resolved", "dismissed", "submitted"):
            logger.info(
                "scheduled alert: notice %d in terminal status %s — skipping",
                notice_id, notice.status,
            )
            return
        recipients = resolve_recipients(
            db,
            client_id=notice.client_id,
            recipient_roles=("compliance_head", "ca_consultant", "staff"),
        )
        if not recipients:
            logger.warning(
                "scheduled alert: no recipients for notice %d — skipping",
                notice_id,
            )
            return
        result = dispatch_alert(
            db,
            notice=notice,
            alert_type=alert_type,
            channels=["email", "websocket"],
            recipients=recipients,
        )
        logger.info(
            "scheduled alert dispatched: notice=%d alert=%s result=%s",
            notice_id, alert_type, result,
        )
    finally:
        db.close()
