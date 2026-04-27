"""LIFE-04: notice service writes audit_log + notice_activity rows on transitions."""

import pytest


pytestmark = pytest.mark.integration


def test_transition_writes_both_records(db_as_app_runtime, client_a, mock_current_user):
    from app.compliance.models.notice import ComplianceNotice, NoticeActivity
    from app.compliance.services.notice_service import transition_notice_status
    from app.compliance.services.notice_state_machine import NoticeStatus
    from app.models.audit_log import AuditLog
    n = ComplianceNotice(
        client_id=client_a.id, notice_number="P", authority="GST",
        status="received",
    )
    db_as_app_runtime.add(n)
    db_as_app_runtime.commit()
    transition_notice_status(
        db_as_app_runtime, n.id, NoticeStatus.UNDER_REVIEW, mock_current_user
    )
    # NoticeActivity row exists
    act = (
        db_as_app_runtime.query(NoticeActivity)
        .filter(
            NoticeActivity.notice_id == n.id,
            NoticeActivity.type == "status_change",
        )
        .all()
    )
    assert len(act) == 1
    # AuditLog row exists
    log = (
        db_as_app_runtime.query(AuditLog)
        .filter(
            AuditLog.action == "notice_status_changed",
            AuditLog.resource_id == n.id,
        )
        .all()
    )
    assert len(log) >= 1
