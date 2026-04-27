"""LIFE-07: Filter/search by authority, type, status, risk, deadline, GSTIN."""

import pytest


pytestmark = pytest.mark.integration


def test_filter_combinations(db_as_app_runtime, client_a):
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.notice_service import filter_notices
    # Seed
    for auth in ("GST", "IT", "MCA"):
        for st in ("received", "under_review"):
            db_as_app_runtime.add(
                ComplianceNotice(
                    client_id=client_a.id,
                    notice_number=f"{auth}-{st}",
                    authority=auth,
                    status=st,
                )
            )
    db_as_app_runtime.commit()
    # Filter by authority + status
    rows = filter_notices(
        db_as_app_runtime, client_id=client_a.id, authority="GST", status="received"
    )
    assert len(rows) == 1
    assert rows[0].authority == "GST"
    assert rows[0].status == "received"
