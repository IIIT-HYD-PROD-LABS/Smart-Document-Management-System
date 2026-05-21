"""Audit logging service — fire-and-forget audit trail for all user actions.

Designed to run inside BackgroundTasks so it creates its own DB session
and never propagates exceptions to the caller.

Hardening 2026-05-05 (#3): write failures are now ERROR-level (not warning)
AND a structured fallback line is appended to AUDIT_FAILURES_PATH so the
regulatory trail is recoverable even when the DB write fails. The
function still does NOT raise — Phase 9 AUDIT contract is "audit failures
must not 500 the user" — but failures are now operationally visible
instead of vanishing into a warning log.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import structlog

from app.database import SessionLocal
from app.models.audit_log import AuditLog

logger = structlog.stdlib.get_logger()


# Fallback file path for audit writes that fail. Defaults to /tmp under
# the Docker container; override via AUDIT_FAILURES_PATH env in production.
#
# CRIT-3 second hardening: emit a startup warning if the resolved path is
# under /tmp/. /tmp is wiped on every container restart, defeating the
# regulatory recovery contract. docker-compose.yml is configured to set
# AUDIT_FAILURES_PATH to a named-volume mount (/var/log/smartdocs/...) but
# operators running outside compose may forget; the warning catches that.
AUDIT_FAILURES_PATH = Path(
    os.environ.get("AUDIT_FAILURES_PATH", "/tmp/audit_failures.jsonl")
)
_FALLBACK_LOCK = threading.Lock()


def _emit_startup_path_warning_if_ephemeral() -> None:
    """Log an ERROR-level message at import time if the dead-letter path
    is under /tmp/. /tmp is ephemeral under Docker — operators must mount
    a durable volume in production.
    """
    if str(AUDIT_FAILURES_PATH).startswith("/tmp/"):
        logger.error(
            "audit_failures_path_ephemeral",
            path=str(AUDIT_FAILURES_PATH),
            warning=(
                "AUDIT_FAILURES_PATH resolves under /tmp; the audit-write "
                "dead-letter file will be wiped on every container restart. "
                "Set AUDIT_FAILURES_PATH to a path on a durable volume."
            ),
        )


_emit_startup_path_warning_if_ephemeral()


def _append_audit_failure_fallback(record: dict, exc: BaseException) -> None:
    """Append a JSON line to AUDIT_FAILURES_PATH so a failed audit row
    can be replayed by ops. Best-effort: filesystem failure here is logged
    but does not propagate."""
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "exc_type": type(exc).__name__,
        "exc_msg": str(exc)[:1000],
        "record": record,
    }
    try:
        AUDIT_FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _FALLBACK_LOCK:
            with open(AUDIT_FAILURES_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        logger.error(
            "audit_log_fallback_write_failed",
            path=str(AUDIT_FAILURES_PATH),
            exc_info=True,
        )


def log_audit_event(
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> bool:
    """Persist an audit log entry.

    Returns True on successful DB persistence, False on failure.

    Hardening (#3 first pass): on failure, escalate to ERROR + write a
    fallback JSONL line to AUDIT_FAILURES_PATH. Operators replay failed
    entries via that file. The function still does not raise — preserving
    the original "audit issues must not break business operations" rule.

    Most v1.0 callers (BackgroundTasks-style fire-and-forget) ignore the
    bool return because they have no recovery path. Phase 12+ regulatory
    callers SHOULD use `log_audit_event_strict` instead so failures are
    raised to caller-visible WARNING-level signals.
    """
    record = {
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": ip_address,
    }
    db = SessionLocal()
    try:
        entry = AuditLog(**record)
        db.add(entry)
        db.commit()
        return True
    except Exception as exc:
        logger.error(
            "audit_log_failed",
            **record,
            exc_info=True,
        )
        _append_audit_failure_fallback(record, exc)
        try:
            db.rollback()
        except Exception:
            # Rollback after a commit failure can itself fail when the
            # connection is already torn down; log loudly so this is
            # visible in dashboards rather than disappearing.
            logger.exception("audit_rollback_failed")
        return False
    finally:
        db.close()


def log_audit_event_strict(
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> bool:
    """CRIT-4 second-pass hardening — same contract as `log_audit_event`
    but a False return is amplified into a structured alert-worthy log
    line so ops dashboards can fire on it.

    Use from regulatory state-change paths (response approvals, evidence
    attach, escalation) where a missing audit row is operationally
    significant. The function still does not raise — caller's transaction
    has already committed by the time this runs.
    """
    ok = log_audit_event(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    if not ok:
        logger.error(
            "regulatory_audit_write_failed",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            requires_ops_attention=True,
            recovery=(
                f"check {AUDIT_FAILURES_PATH} for the dead-letter row + "
                "investigate DB or schema; replay the row when DB is healthy"
            ),
        )
    return ok
