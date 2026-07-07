"""LIFE-07: Filter/search by authority, type, status, risk, deadline, GSTIN.

filter_notices is async (async-migration Phase 5); uses the owner
bootstrap session directly (RLS-bypassed, same effective role as the
sync `db_as_app_runtime` default used before this test converted) --
this test exercises filter correctness, not tenant isolation.
"""

import pytest

from app.database import AsyncSessionBootstrap


pytestmark = pytest.mark.integration


async def test_filter_combinations(client_a):
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import filter_notices

    async with AsyncSessionBootstrap() as db:
        # Seed
        for auth in ("GST", "IT", "MCA"):
            for st in ("received", "under_review"):
                db.add(
                    ComplianceNotice(
                        client_id=client_a.id,
                        notice_number=f"{auth}-{st}",
                        authority=auth,
                        status=st,
                    )
                )
        await db.commit()
        # Filter by authority + status
        rows = await filter_notices(
            db, client_id=client_a.id, authority="GST", status="received"
        )
    assert len(rows) == 1
    assert rows[0].authority == "GST"
    assert rows[0].status == "received"
