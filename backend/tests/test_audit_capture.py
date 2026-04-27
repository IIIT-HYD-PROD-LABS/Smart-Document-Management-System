"""AUDIT-02: audit_logs.details captures before/after; clock_timestamp default."""

import pytest


pytestmark = pytest.mark.integration


def test_status_change_captures_diff(db_as_app_runtime, client_a):
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import transition_notice_status
    from app.compliance.services.notice_state_machine import NoticeStatus
    from app.models.audit_log import AuditLog
    from app.models.user import User

    u = db_as_app_runtime.query(User).first()
    n = ComplianceNotice(
        client_id=client_a.id,
        notice_number="A1",
        authority="GST",
        status="received",
    )
    db_as_app_runtime.add(n)
    db_as_app_runtime.commit()
    transition_notice_status(db_as_app_runtime, n.id, NoticeStatus.UNDER_REVIEW, u)

    latest = (
        db_as_app_runtime.query(AuditLog)
        .filter(AuditLog.action == "notice_status_changed")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert latest is not None
    assert latest.details.get("before_value") == "received"
    assert latest.details.get("after_value") == "under_review"


def test_clock_timestamp_monotonic(db_as_app_runtime):
    """Same as test_audit_immutability.test_clock_timestamp_default — duplicated
    here so AUDIT-02 has its own verify command separable from AUDIT-01.
    """
    from app.models.audit_log import AuditLog
    a = AuditLog(action="t1", resource_type="X", details={})
    b = AuditLog(action="t2", resource_type="X", details={})
    db_as_app_runtime.add_all([a, b])
    db_as_app_runtime.flush()
    assert a.created_at < b.created_at
