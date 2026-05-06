"""CLIENT-07: Monthly compliance health summary report on demand."""

import pytest


pytestmark = pytest.mark.integration


def test_health_summary_pdf(db_as_app_runtime, client_a):
    """CLIENT-07: report_service returns the structured summary dict.

    Renamed-to-match-current contract: v2.0 ships HTML only; PDF was
    deferred to v2.1, so the test asserts on `summary_html` only.
    """
    from app.compliance.services.report_service import generate_health_summary
    result = generate_health_summary(
        db_as_app_runtime, client_id=client_a.id, month="2026-04"
    )
    assert result["client_id"] == client_a.id
    assert "summary_html" in result
    assert result["summary_html"] is not None
