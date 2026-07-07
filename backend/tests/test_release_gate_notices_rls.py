"""Async-migration release gate: end-to-end cross-tenant isolation proof.

Fires genuinely concurrent HTTP requests as two different tenants against a
converted compliance router (/api/compliance/notices), through the REAL
FastAPI app -- TenantContextMiddleware -> get_current_user ->
get_active_membership -> require_compliance_permission -> router -- on a
deliberately small connection pool (pool_size=2) to maximize the odds that
two different tenants' requests reuse the SAME physical connection back to
back, which is exactly the scenario under which a broken tenant_context
listener (stale GUC left on checkin) would leak client A's notices into
client B's response.

Unlike tests/test_async_pilot_rls_integration.py (notice_types /
regulatory_calendar -- global reference tables with no client_id column),
compliance_notices is genuinely per-tenant row data. This test seeds distinct
notice_number markers per client and asserts NONE of client A's markers ever
appear in a response scoped to client B, and vice versa, across many
concurrent interleaved requests.

Only the physical DB engine backing get_async_db is swapped to a small pool
for this test (via dependency_overrides) -- TenantContextMiddleware, JWT
auth, get_active_membership, and the notices router all run unmodified.
"""
import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.compliance.middleware.tenant_context import register_tenant_listener
from app.database import _async_connect_args_for, async_engine, get_async_db
from app.main import app
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
async def seeded_notices(db_as_app_runtime_async, client_a_async, client_b_async):
    """5 notices per client with unique markers, inserted under RLS bypass.

    Cleanup is implicit: client_a_async/client_b_async teardown deletes the
    Client rows, and compliance_notices.client_id has ondelete=CASCADE.
    """
    from app.compliance.models.notice import ComplianceNotice

    await db_as_app_runtime_async.execute(text("RESET ROLE"))
    markers: dict[int, list[str]] = {}
    for client, tag in ((client_a_async, "A"), (client_b_async, "B")):
        nums = [f"RELGATE-{tag}-{uuid.uuid4().hex[:10]}" for _ in range(5)]
        markers[client.id] = nums
        for num in nums:
            db_as_app_runtime_async.add(
                ComplianceNotice(
                    client_id=client.id,
                    notice_number=num,
                    authority="GST",
                    status="received",
                )
            )
    await db_as_app_runtime_async.commit()
    await db_as_app_runtime_async.execute(text("SET ROLE app_runtime"))
    return markers


async def test_release_gate_concurrent_notices_no_cross_tenant_leak(
    client_a_async, client_b_async, seeded_notices
):
    """The release gate: no request scoped to one client ever sees the
    other client's notice_number markers, under real concurrent pressure on
    a 2-connection pool."""
    client_a_id = client_a_async.id
    client_b_id = client_b_async.id
    markers = seeded_notices

    url = async_engine.url.render_as_string(hide_password=False)
    small_engine = create_async_engine(
        url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args=_async_connect_args_for(url),
    )
    register_tenant_listener(small_engine.sync_engine)
    SmallSession = async_sessionmaker(bind=small_engine, expire_on_commit=False)

    async def _get_small_db():
        db = SmallSession()
        try:
            yield db
        finally:
            await db.close()

    app.dependency_overrides[get_async_db] = _get_small_db
    auth = _bearer_header(1)  # user_id=1 is compliance_head on both fixture clients

    async def _call(client_id: int):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get(
                "/api/compliance/notices",
                headers={**auth, "X-Client-Id": str(client_id)},
            )
            return client_id, resp

    try:
        # Interleave many requests for BOTH tenants so asyncio.gather schedules
        # them onto the pool's 2 connections in an unpredictable, overlapping
        # order -- the condition most likely to surface stale per-connection
        # GUC state from an earlier request.
        calls = []
        for _ in range(15):
            calls.append(_call(client_a_id))
            calls.append(_call(client_b_id))
        results = await asyncio.gather(*calls)
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        await small_engine.dispose()

    other_of = {client_a_id: client_b_id, client_b_id: client_a_id}
    for expected_client_id, resp in results:
        assert resp.status_code == 200, resp.text
        body = resp.json()
        returned_numbers = {item["notice_number"] for item in body["items"]}
        foreign_numbers = set(markers[other_of[expected_client_id]])
        leaked = returned_numbers & foreign_numbers
        assert not leaked, (
            f"cross-tenant leak: request scoped to client {expected_client_id} "
            f"saw notice(s) belonging to client {other_of[expected_client_id]}: {leaked}"
        )
        own_numbers = set(markers[expected_client_id])
        assert own_numbers <= returned_numbers, (
            f"client {expected_client_id} did not see its own seeded notices "
            f"({own_numbers - returned_numbers} missing) -- request may have "
            "silently scoped to the wrong tenant instead of leaking"
        )
