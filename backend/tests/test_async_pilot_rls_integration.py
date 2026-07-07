"""Async-migration Phase 2 pilot release gate.

Proves tenant isolation works end-to-end through the REAL request path --
TenantContextMiddleware -> get_current_user -> get_active_membership ->
require_compliance_permission -> router -- running on the async engine, for
the two routers converted in this phase (notice_types, regulatory_calendar).

This is deliberately NOT conftest.py's _set_tenant_context shortcut: that
helper writes PG session vars directly onto a sync test session and never
touches TenantContextMiddleware, get_current_user, or get_active_membership.
It's the right tool for testing RLS policies in isolation (see
tests/test_rls_isolation.py), but it can't prove this phase's actual
deliverable -- that the newly-async get_active_membership dependency,
reached through the real header -> ContextVar -> Depends() chain, correctly
gates access per tenant when driven by a real HTTP request.

compliance_notice_types / compliance_regulatory_calendar are GLOBAL reference
tables with no client_id column (confirmed by
tests/test_rls_isolation.py::test_app_runtime_can_read_non_rls_lookup_tables),
so there is no per-row tenant data to leak between clients here. Isolation
for these two endpoints is enforced one layer up, at the membership gate: a
request's X-Client-Id is only honoured if the authenticated user actually
holds a ClientMembership row for that client (the "Pitfall 5" mitigation
documented in app/compliance/dependencies.py). This test proves that gate
holds through the real chain: a user scoped to client B only can read the
catalog as client B, but is rejected with 403 -- not a silent empty list --
the moment they present client A's id.
"""
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.compliance.models.membership import ClientMembership
from app.main import app
from app.models.user import User
from app.utils.security import create_access_token

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL_RUNTIME") and not os.environ.get("DATABASE_URL"),
        reason="DATABASE_URL_RUNTIME/DATABASE_URL not set -- needs a real Postgres",
    ),
]


def _bearer_header(user_id: int) -> dict:
    token = create_access_token({"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def tenant_b_only_user(db_as_app_runtime, client_b):
    """A user with a ClientMembership on client_b ONLY.

    client_a/client_b (conftest._create_client_with_rls_bypass) both already
    grant user_id=1 a compliance_head membership, so user_id=1 alone can't
    demonstrate cross-tenant rejection -- it's legitimately a member of both.
    This fixture creates a second, independent user scoped to exactly one
    tenant so the test can prove the negative case (403 on the other tenant)
    as well as the positive one.
    """
    client_b_id = client_b.id  # capture before any further commit can expire it

    db_as_app_runtime.execute(text("RESET ROLE"))
    user = User(
        email="pilot-phase2-tenant-b@example.com",
        username="pilot_phase2_tenant_b",
        hashed_password="x",
        role="editor",
    )
    db_as_app_runtime.add(user)
    db_as_app_runtime.flush()
    user_id = user.id
    membership = ClientMembership(
        user_id=user_id,
        client_id=client_b_id,
        compliance_role="staff",  # NOTICE_VIEW is granted to all 7 roles
    )
    db_as_app_runtime.add(membership)
    db_as_app_runtime.commit()
    db_as_app_runtime.execute(text("SET ROLE app_runtime"))

    yield user_id

    db_as_app_runtime.rollback()
    db_as_app_runtime.execute(text("RESET ROLE"))
    db_as_app_runtime.execute(
        text("DELETE FROM compliance_client_memberships WHERE user_id = :uid"),
        {"uid": user_id},
    )
    db_as_app_runtime.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    db_as_app_runtime.commit()
    db_as_app_runtime.execute(text("SET ROLE app_runtime"))


async def test_membership_gate_isolates_tenants_through_real_async_chain(
    client_a, client_b, tenant_b_only_user
):
    """End-to-end proof against both converted routers, via httpx.AsyncClient
    hitting the real FastAPI app (real middleware, real JWT auth, real async
    get_active_membership / get_async_db) -- not a dependency override.
    """
    client_a_id = client_a.id
    client_b_id = client_b.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # --- Tenant B's own user, requesting its own tenant: authorized. ---
        # regulatory_calendar has real migration-0016 seed data (12 rows for
        # 2026), so this also proves the async SELECT executed for real,
        # not just that the gate let the request through.
        own_calendar = await ac.get(
            "/api/compliance/regulatory-calendar",
            params={"year": 2026},
            headers={**_bearer_header(tenant_b_only_user), "X-Client-Id": str(client_b_id)},
        )
        assert own_calendar.status_code == 200, own_calendar.text
        own_calendar_body = own_calendar.json()
        assert len(own_calendar_body) >= 5, "expected the migration-0016 seeded 2026 rows"

        # notice_types is empty in this environment (no seed migration) --
        # 200 + a list is the correct "no seed data" proof the gate passed,
        # per the empty-result allowance for this phase.
        own_types = await ac.get(
            "/api/compliance/notice-types",
            headers={**_bearer_header(tenant_b_only_user), "X-Client-Id": str(client_b_id)},
        )
        assert own_types.status_code == 200, own_types.text
        assert isinstance(own_types.json(), list)

        # --- Same user, presenting the OTHER tenant's id: rejected. ---
        # No ClientMembership row exists for (tenant_b_only_user, client_a),
        # so get_active_membership must 403 -- not silently scope to client_b,
        # not return an empty list, not 500.
        foreign_calendar = await ac.get(
            "/api/compliance/regulatory-calendar",
            params={"year": 2026},
            headers={**_bearer_header(tenant_b_only_user), "X-Client-Id": str(client_a_id)},
        )
        assert foreign_calendar.status_code == 403, foreign_calendar.text
        assert f"client {client_a_id}" in foreign_calendar.json()["detail"]

        foreign_types = await ac.get(
            "/api/compliance/notice-types",
            headers={**_bearer_header(tenant_b_only_user), "X-Client-Id": str(client_a_id)},
        )
        assert foreign_types.status_code == 403, foreign_types.text
        assert f"client {client_a_id}" in foreign_types.json()["detail"]

        # --- Control: user_id=1 is a genuine compliance_head on BOTH fixture
        # clients, so it must be admitted to BOTH -- confirming the 403s
        # above are real per-tenant gating, not a blanket rejection bug.
        for cid in (client_a_id, client_b_id):
            resp = await ac.get(
                "/api/compliance/regulatory-calendar",
                params={"year": 2026},
                headers={**_bearer_header(1), "X-Client-Id": str(cid)},
            )
            assert resp.status_code == 200, resp.text
            assert len(resp.json()) >= 5
