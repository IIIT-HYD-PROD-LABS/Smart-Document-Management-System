"""INFRA-05: RegulatoryCalendar contains seeded 2026 holidays."""

import pytest


pytestmark = pytest.mark.integration


def test_2026_holidays_seeded(db_as_app_runtime):
    from app.compliance.models.regulatory_calendar import RegulatoryCalendar
    rows = (
        db_as_app_runtime.query(RegulatoryCalendar)
        .filter(RegulatoryCalendar.year == 2026)
        .all()
    )
    assert len(rows) >= 5, "Expected at least 5 seeded 2026 holidays/deadlines"
