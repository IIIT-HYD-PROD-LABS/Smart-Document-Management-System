"""LIFE-05: Recursive CTE notice chain.

get_notice_chain is async (async-migration Phase 5); uses the owner
bootstrap session directly (RLS-bypassed, same effective role as the
sync `db_as_app_runtime` default used before this test converted) --
this test exercises the CTE, not tenant isolation.
"""

import pytest

from app.database import AsyncSessionBootstrap


pytestmark = pytest.mark.integration


async def test_chain_returns_ancestors_and_descendants(client_a):
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import get_notice_chain

    async with AsyncSessionBootstrap() as db:
        # SCN -> Assessment -> Demand
        scn = ComplianceNotice(
            client_id=client_a.id, notice_number="SCN-1",
            authority="GST", status="received",
        )
        db.add(scn)
        await db.commit()
        asmt = ComplianceNotice(
            client_id=client_a.id, notice_number="ASMT-1",
            authority="GST", status="received",
            parent_notice_id=scn.id,
        )
        db.add(asmt)
        await db.commit()
        demand = ComplianceNotice(
            client_id=client_a.id, notice_number="DRC-01",
            authority="GST", status="received",
            parent_notice_id=asmt.id,
        )
        db.add(demand)
        await db.commit()

        chain = await get_notice_chain(db, asmt.id, max_depth=10)
    ids = {row["id"] for row in chain}
    assert {scn.id, asmt.id, demand.id}.issubset(ids)


async def test_chain_terminates_on_cycle(client_a):
    """If a cycle exists, max_depth bound prevents infinite recursion."""
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import get_notice_chain

    async with AsyncSessionBootstrap() as db:
        a = ComplianceNotice(
            client_id=client_a.id, notice_number="A",
            authority="GST", status="received",
        )
        db.add(a)
        await db.commit()
        b = ComplianceNotice(
            client_id=client_a.id, notice_number="B",
            authority="GST", status="received",
            parent_notice_id=a.id,
        )
        db.add(b)
        await db.commit()
        # Inject cycle: a.parent_notice_id = b.id
        a.parent_notice_id = b.id
        await db.commit()

        # Should terminate via max_depth, not hang
        chain = await get_notice_chain(db, a.id, max_depth=5)
    assert chain is not None
    assert len(chain) <= 12  # bounded
