"""CLIENT-03: Per-client dashboard aggregates."""

import pytest

from app.database import AsyncSessionBootstrap

pytestmark = pytest.mark.integration


async def test_client_dashboard_aggregates(client_a):
    """get_dashboard_aggregates is async (async-migration Phase 5); uses the
    owner bootstrap session directly (RLS-bypassed, same effective role as
    the sync `db_as_app_runtime` default used before this test converted) --
    this test exercises aggregation correctness, not tenant isolation.
    """
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.client_service import get_dashboard_aggregates

    async with AsyncSessionBootstrap() as db:
        # 3 notices: 2 received, 1 under_review
        for st in ("received", "received", "under_review"):
            db.add(
                ComplianceNotice(
                    client_id=client_a.id,
                    notice_number=f"X-{st}",
                    authority="GST",
                    status=st,
                )
            )
        await db.commit()
        agg = await get_dashboard_aggregates(db, client_id=client_a.id)
    assert agg["total"] == 3
    assert agg["by_status"]["received"] == 2
    assert agg["by_status"]["under_review"] == 1
