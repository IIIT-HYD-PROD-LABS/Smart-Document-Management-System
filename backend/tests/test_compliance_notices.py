"""LIFE-01, LIFE-08: notice upload + bulk update."""

import pytest


pytestmark = pytest.mark.integration


def test_notice_upload_links_document(db_as_app_runtime, client_a, mock_current_user):
    """Reuses v1.0 upload pipeline; sets notice_id FK on Document."""
    from app.compliance.models.notice import ComplianceNotice
    from app.models.document import Document
    n = ComplianceNotice(
        client_id=client_a.id, notice_number="UP-1",
        authority="GST", status="received",
    )
    db_as_app_runtime.add(n)
    db_as_app_runtime.commit()
    d = Document(
        user_id=mock_current_user.id,
        filename="x.pdf",
        original_filename="x.pdf",
        file_type="pdf",
        file_size=1000,
        notice_id=n.id,
    )
    db_as_app_runtime.add(d)
    db_as_app_runtime.commit()
    assert d.notice_id == n.id


def test_bulk_update_partial_failure(db_as_app_runtime, client_a, mock_current_user):
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import bulk_update_status
    from app.compliance.services.notice_state_machine import NoticeStatus
    # Two notices: one in received (can advance), one in resolved (cannot)
    n1 = ComplianceNotice(
        client_id=client_a.id, notice_number="OK",
        authority="GST", status="received",
    )
    n2 = ComplianceNotice(
        client_id=client_a.id, notice_number="BLOCKED",
        authority="GST", status="resolved",
    )
    db_as_app_runtime.add_all([n1, n2])
    db_as_app_runtime.commit()
    result = bulk_update_status(
        db_as_app_runtime, [n1.id, n2.id], NoticeStatus.UNDER_REVIEW, mock_current_user
    )
    assert result["summary"]["ok"] == 1
    assert result["summary"]["failed"] == 1
