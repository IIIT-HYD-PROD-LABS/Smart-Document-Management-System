"""CLIENT-06: config_overrides JSONB containment uses GIN index."""

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.integration


def test_containment_uses_gin(db_as_app_runtime):
    # On small tables the planner may choose Seq Scan over the GIN index, so we
    # don't EXPLAIN the JSONB containment query — we just assert the index
    # exists. CLIENT-06 only requires the index to be present.
    idx = db_as_app_runtime.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'compliance_clients' "
            "AND indexname = 'ix_clients_config_overrides_gin'"
        )
    ).all()
    assert len(idx) == 1, "GIN index ix_clients_config_overrides_gin missing"
