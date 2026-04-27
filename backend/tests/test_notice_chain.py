"""LIFE-05: Recursive CTE notice chain."""

import pytest


pytestmark = pytest.mark.integration


def test_chain_returns_ancestors_and_descendants(db_as_app_runtime, client_a):
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import get_notice_chain
    # SCN -> Assessment -> Demand
    scn = ComplianceNotice(
        client_id=client_a.id, notice_number="SCN-1",
        authority="GST", status="received",
    )
    db_as_app_runtime.add(scn)
    db_as_app_runtime.commit()
    asmt = ComplianceNotice(
        client_id=client_a.id, notice_number="ASMT-1",
        authority="GST", status="received",
        parent_notice_id=scn.id,
    )
    db_as_app_runtime.add(asmt)
    db_as_app_runtime.commit()
    demand = ComplianceNotice(
        client_id=client_a.id, notice_number="DRC-01",
        authority="GST", status="received",
        parent_notice_id=asmt.id,
    )
    db_as_app_runtime.add(demand)
    db_as_app_runtime.commit()

    chain = get_notice_chain(db_as_app_runtime, asmt.id, max_depth=10)
    ids = {row["id"] for row in chain}
    assert {scn.id, asmt.id, demand.id}.issubset(ids)


def test_chain_terminates_on_cycle(db_as_app_runtime, client_a):
    """If a cycle exists, max_depth bound prevents infinite recursion."""
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import get_notice_chain
    a = ComplianceNotice(
        client_id=client_a.id, notice_number="A",
        authority="GST", status="received",
    )
    db_as_app_runtime.add(a)
    db_as_app_runtime.commit()
    b = ComplianceNotice(
        client_id=client_a.id, notice_number="B",
        authority="GST", status="received",
        parent_notice_id=a.id,
    )
    db_as_app_runtime.add(b)
    db_as_app_runtime.commit()
    # Inject cycle: a.parent_notice_id = b.id
    a.parent_notice_id = b.id
    db_as_app_runtime.commit()

    # Should terminate via max_depth, not hang
    chain = get_notice_chain(db_as_app_runtime, a.id, max_depth=5)
    assert chain is not None
    assert len(chain) <= 12  # bounded
