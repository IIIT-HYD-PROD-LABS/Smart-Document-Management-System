"""CLIENT-07: Monthly compliance health summary report on demand."""

import pytest


pytestmark = pytest.mark.integration


def test_health_summary_pdf(db_as_app_runtime, client_a):
    from app.compliance.services.report_service import generate_health_summary
    result = generate_health_summary(
        db_as_app_runtime, client_id=client_a.id, month="2026-04"
    )
    assert result["client_id"] == client_a.id
    assert "summary_html" in result or "summary_pdf_path" in result
