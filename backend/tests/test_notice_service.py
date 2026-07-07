"""LIFE-04: notice service writes audit_log + notice_activity rows on transitions.

transition_notice_status is async (async-migration Phase 5); uses the
owner bootstrap session directly (RLS-bypassed, same effective role as
the sync `db_as_app_runtime` default used before this test converted).
"""

import pytest

from app.database import AsyncSessionBootstrap
from sqlalchemy import select


pytestmark = pytest.mark.integration


async def test_transition_writes_both_records(client_a, mock_current_user):
    from app.compliance.models.notice import ComplianceNotice, NoticeActivity
    from app.compliance.services.notice_service import transition_notice_status
    from app.compliance.services.notice_state_machine import NoticeStatus
    from app.models.audit_log import AuditLog

    async with AsyncSessionBootstrap() as db:
        n = ComplianceNotice(
            client_id=client_a.id, notice_number="P", authority="GST",
            status="received",
        )
        db.add(n)
        await db.commit()
        await transition_notice_status(
            db, n.id, NoticeStatus.UNDER_REVIEW, mock_current_user
        )
        # NoticeActivity row exists
        act = (await db.execute(
            select(NoticeActivity).where(
                NoticeActivity.notice_id == n.id,
                NoticeActivity.type == "status_change",
            )
        )).scalars().all()
        assert len(act) == 1
        # AuditLog row exists
        log = (await db.execute(
            select(AuditLog).where(
                AuditLog.action == "notice_status_changed",
                AuditLog.resource_id == n.id,
            )
        )).scalars().all()
        assert len(log) >= 1
