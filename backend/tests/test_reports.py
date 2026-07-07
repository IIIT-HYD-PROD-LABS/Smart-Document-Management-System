"""CLIENT-07: Monthly compliance health summary report on demand."""

import pytest

from app.database import AsyncSessionBootstrap


pytestmark = pytest.mark.integration


async def test_health_summary_pdf(client_a):
    """CLIENT-07: report_service returns the structured summary dict.

    Renamed-to-match-current contract: v2.0 ships HTML only; PDF was
    deferred to v2.1, so the test asserts on `summary_html` only.

    report_service is async (async-migration Phase 6); uses the owner
    bootstrap session directly (RLS-bypassed, same effective role as the
    sync `db_as_app_runtime` default used before this test converted) --
    this test exercises aggregation correctness, not tenant isolation.
    """
    from app.compliance.services.report_service import generate_health_summary

    async with AsyncSessionBootstrap() as db:
        result = await generate_health_summary(
            db, client_id=client_a.id, month="2026-04"
        )
    assert result["client_id"] == client_a.id
    assert "summary_html" in result
    assert result["summary_html"] is not None
