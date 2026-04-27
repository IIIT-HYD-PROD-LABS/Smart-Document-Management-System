"""CLIENT-03: Per-client dashboard aggregates."""

import pytest


pytestmark = pytest.mark.integration


def test_client_dashboard_aggregates(db_as_app_runtime, client_a):
    from app.compliance.models.notice import ComplianceNotice
    from app.compliance.services.client_service import get_dashboard_aggregates
    # 3 notices: 2 received, 1 under_review
    for st in ("received", "received", "under_review"):
        db_as_app_runtime.add(
            ComplianceNotice(
                client_id=client_a.id,
                notice_number=f"X-{st}",
                authority="GST",
                status=st,
            )
        )
    db_as_app_runtime.commit()
    agg = get_dashboard_aggregates(db_as_app_runtime, client_id=client_a.id)
    assert agg["total"] == 3
    assert agg["by_status"]["received"] == 2
    assert agg["by_status"]["under_review"] == 1
