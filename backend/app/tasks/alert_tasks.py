"""Phase 11 alert Celery tasks — runs on the compliance queue.

Wired from Phase 10 escalation.escalate(): when a Critical-tier notice is
escalated, this task fires the multi-channel alert pipeline. Direct
escalation hook avoids the cost of polling the audit log.
"""
from __future__ import annotations

import logging

from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.alert_tasks.dispatch_notice_alert",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="compliance",
)
def dispatch_notice_alert(
    self,
    notice_id: int,
    alert_type: str,
    channels: list,
    recipient_roles: list,
) -> dict:
    """Dispatch an alert across configured channels for a notice.

    Args:
        notice_id: ComplianceNotice.id.
        alert_type: one of model_alert.VALID_ALERT_TYPES.
        channels: subset of ('email', 'sms', 'websocket').
        recipient_roles: list of compliance roles (e.g. ['compliance_head', 'cfo']).

    Returns: counters dict from alert_service.dispatch_alert.
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

    # CRITICAL hardening (#1) — start in cross-client mode for the initial
    # notice lookup, then narrow to the notice's tenant for the dispatch
    # work. Defence in depth: even if BYPASSRLS were misdeployed, queries
    # observe the intended tenant boundary.
    set_tenant_context_for_celery(client_id=None, user_id=None, cross_mode=True)

    db = SessionLocal()
    try:
        notice = db.get(ComplianceNotice, notice_id)
        if notice is None:
            logger.warning("dispatch_notice_alert: notice %d not found", notice_id)
            return {"error": "notice_not_found"}

        set_tenant_context_for_celery(
            client_id=notice.client_id, user_id=None, cross_mode=False
        )

        recipients = resolve_recipients(
            db, client_id=notice.client_id, recipient_roles=recipient_roles
        )
        if not recipients:
            logger.info(
                "dispatch_notice_alert: no recipients for notice %d roles=%s",
                notice_id, recipient_roles,
            )
            return {"recipients": 0}

        result = dispatch_alert(
            db,
            notice=notice,
            alert_type=alert_type,
            channels=channels,
            recipients=recipients,
        )
        logger.info(
            "alert dispatched: notice=%d type=%s result=%s",
            notice_id, alert_type, result,
        )
        return result
    except Exception as exc:
        logger.exception("dispatch_notice_alert failed for notice %d", notice_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"error": "retries_exhausted"}
    finally:
        db.close()
