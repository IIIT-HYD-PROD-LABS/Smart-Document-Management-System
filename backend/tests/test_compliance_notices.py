"""LIFE-01, LIFE-08: notice upload + bulk update."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_assign_notice_logs_activity_with_valid_type():
    """C1 regression — assign_notice must call log_activity with the param
    name `type` and the value "assigned" (the only assignment value in
    VALID_ACTIVITY_TYPES + the DB CHECK). The pre-fix call used
    activity_type="notice_assigned", which both used a non-existent kwarg
    and an invalid value, raising TypeError -> HTTP 500 on every assign.

    Pure-unit (no DB): drives the router function with mocked deps.
    """
    from app.compliance.routers.notices import assign_notice

    notice = MagicMock()
    notice.id = 1
    notice.client_id = 5
    notice.assigned_user_id = 3
    notice.notice_number = "N-1"
    notice.authority = "GST"
    notice.response_deadline = None

    db = MagicMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.first.return_value = notice
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    current_user = MagicMock(id=42)
    membership = MagicMock(client_id=5)

    with patch(
        "app.compliance.routers.notices.log_activity"
    ) as mock_log_activity, patch(
        "app.compliance.routers.notices.log_audit_event"
    ):
        # assigned_user_id=None clears the assignment, skipping the realtime
        # notification branch so we exercise only the activity write.
        await assign_notice(
            notice_id=1,
            payload={"assigned_user_id": None},
            current_user=current_user,
            db=db,
            membership=membership,
        )

    mock_log_activity.assert_called_once()
    kwargs = mock_log_activity.call_args.kwargs
    assert kwargs.get("type") == "assigned"
    assert "activity_type" not in kwargs


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


async def test_bulk_update_partial_failure(client_a, mock_current_user):
    """bulk_update_status is async (async-migration Phase 5); uses the
    owner bootstrap session directly (RLS-bypassed, same effective role
    as the sync `db_as_app_runtime` default used before this converted)."""
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import bulk_update_status
    from app.compliance.services.notice_state_machine import NoticeStatus
    from app.database import AsyncSessionBootstrap

    async with AsyncSessionBootstrap() as db:
        # Two notices: one in received (can advance), one in resolved (cannot)
        n1 = ComplianceNotice(
            client_id=client_a.id, notice_number="OK",
            authority="GST", status="received",
        )
        n2 = ComplianceNotice(
            client_id=client_a.id, notice_number="BLOCKED",
            authority="GST", status="resolved",
        )
        db.add_all([n1, n2])
        await db.commit()
        result = await bulk_update_status(
            db, [n1.id, n2.id], NoticeStatus.UNDER_REVIEW, mock_current_user
        )
    assert result["summary"]["ok"] == 1
    assert result["summary"]["failed"] == 1
