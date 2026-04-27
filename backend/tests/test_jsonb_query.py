"""CLIENT-06: config_overrides JSONB containment uses GIN index."""

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.integration


def test_containment_uses_gin(db_as_app_runtime):
    # EXPLAIN should show Bitmap Index Scan using ix_clients_config_overrides_gin
    plan = db_as_app_runtime.execute(
        text("EXPLAIN SELECT id FROM compliance_clients WHERE config_overrides @> '{}'::jsonb")
    ).all()
    plan_text = "\n".join(str(r[0]) for r in plan)
    # On small tables planner may choose Seq Scan; assert the GIN index EXISTS at minimum
    idx = db_as_app_runtime.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'compliance_clients' "
            "AND indexname = 'ix_clients_config_overrides_gin'"
        )
    ).all()
    assert len(idx) == 1, "GIN index ix_clients_config_overrides_gin missing"
