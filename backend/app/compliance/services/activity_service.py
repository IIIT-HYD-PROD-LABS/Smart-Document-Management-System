"""User-facing activity timeline writes — Phase 9 D-09.

This is distinct from app.services.audit_service:
  - audit_service writes the immutable system audit_log (AUDIT-01/02).
  - activity_service writes the user-facing notice timeline shown in the
    notice detail UI (status changes, notes, file attachments, assignments).

Activity rows are mutable (RESEARCH Q2 recommendation). Immutability is the
audit_log's job; the user-visible timeline can be edited/corrected without
breaking the audit trail.
"""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.compliance.models.notice import NoticeActivity


VALID_ACTIVITY_TYPES = (
    "status_change",
    "note_added",
    "file_attached",
    "assigned",
)


def log_activity(
    db: Session,
    notice_id: int,
    user_id: Optional[int],
    type: str,
    details: Optional[dict[str, Any]] = None,
) -> NoticeActivity:
    """Insert a NoticeActivity row.

    The caller commits the session — this lets activity rows be written in
    the same transaction as the underlying state change so the timeline
    can never drift from the data.
    """
    if type not in VALID_ACTIVITY_TYPES:
        raise ValueError(
            f"Invalid activity type: {type}. "
            f"Allowed: {sorted(VALID_ACTIVITY_TYPES)}"
        )
    row = NoticeActivity(
        notice_id=notice_id,
        user_id=user_id,
        type=type,
        details=details or {},
    )
    db.add(row)
    return row
