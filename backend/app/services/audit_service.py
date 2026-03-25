"""Audit logging service — fire-and-forget audit trail for all user actions.

Designed to run inside BackgroundTasks so it creates its own DB session
and never propagates exceptions to the caller.
"""

import structlog

from app.database import SessionLocal
from app.models.audit_log import AuditLog

logger = structlog.stdlib.get_logger()


def log_audit_event(
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Persist an audit log entry.

    Uses its own short-lived session (not the request session) because this
    typically executes in a BackgroundTask after the HTTP response has already
    been sent.  Failures are swallowed and logged — audit issues must never
    break business operations.
    """
    db = SessionLocal()
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception:
        logger.warning(
            "audit_log_failed",
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            exc_info=True,
        )
    finally:
        db.close()
