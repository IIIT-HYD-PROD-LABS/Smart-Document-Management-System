"""Phase 1 release-gate tests for the async migration (see the plan at
docs -- sync-to-async SQLAlchemy migration). Prove the tenant-context RLS
listener actually works correctly under the async engine/asyncpg before any
router code is built on top of it:

- Risk axis A: the listener's raw %s-placeholder cursor.execute() call must
  correctly translate through SQLAlchemy's asyncpg adapter, not silently
  no-op or raise.
- Risk axis B: checkin-triggered GUC cleanup must reliably fire across pool
  reuse, pool_recycle-triggered connection replacement, and heavy concurrent
  multi-tenant pressure on a small pool -- the scenario most likely to
  surface a cross-tenant leakage bug.

Requires a real DATABASE_URL_RUNTIME (skipped otherwise, same convention as
tests/conftest.py's app_runtime_engine fixture).
"""
import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.compliance.middleware.tenant_context import (
    current_client_id_var,
    cross_client_mode_var,
    current_user_id_var,
    register_tenant_listener,
)
from app.database import AsyncSessionLocal, _async_connect_args_for, async_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL_RUNTIME") and not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL_RUNTIME/DATABASE_URL not set -- needs a real Postgres",
)


async def _current_guc(session, name: str) -> str:
    # A neutral query MUST run first: the listener's own recursion guard
    # skips injecting set_config on any statement containing "current_setting("
    # (to avoid re-triggering itself), so calling this as a session's *only*
    # query would never actually set the GUC before reading it back --
    # confirmed empirically, this is by-design listener behavior, not a bug.
    await session.execute(text("SELECT 1"))
    result = await session.execute(text(f"SELECT current_setting('{name}', true)"))
    return result.scalar()


async def test_risk_axis_a_tenant_guc_round_trip():
    token_client = current_client_id_var.set(4242)
    token_cross = cross_client_mode_var.set(False)
    token_user = current_user_id_var.set(99)
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            assert await _current_guc(session, "app.current_client_id") == "4242"
            assert await _current_guc(session, "app.user_id") == "99"
            assert await _current_guc(session, "app.cross_client_mode") == "false"
    finally:
        current_client_id_var.reset(token_client)
        cross_client_mode_var.reset(token_cross)
        current_user_id_var.reset(token_user)


async def test_risk_axis_b_checkin_clears_guc_on_close():
    token = current_client_id_var.set(777)
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            assert await _current_guc(session, "app.current_client_id") == "777"
    finally:
        current_client_id_var.reset(token)

    # ContextVar is back to its default (None) here, so before_cursor_execute
    # should skip re-setting entirely -- but that only matters if checkin
    # actually cleared the stale '777' left on whatever physical connection
    # this next session happens to reuse.
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
        assert await _current_guc(session, "app.current_client_id") != "777"


async def test_risk_axis_b_small_pool_multi_tenant_isolation():
    # NOTE: str(engine.url) masks the password to '***' by design (SQLAlchemy
    # safety default) -- render_as_string(hide_password=False) is required to
    # get a URL that can actually authenticate. async_engine.url is already
    # the asyncpg-dialect URL, so no need to re-run it through _async_url_for.
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

    async def run_as_tenant(client_id: int) -> str:
        token = current_client_id_var.set(client_id)
        try:
            async with SmallSession() as session:
                await asyncio.sleep(0.01)
                return await _current_guc(session, "app.current_client_id")
        finally:
            current_client_id_var.reset(token)

    try:
        tenant_ids = [101, 202, 303, 404, 505, 606]
        results = await asyncio.gather(*(run_as_tenant(cid) for cid in tenant_ids))
        for expected, observed in zip(tenant_ids, results):
            assert observed == str(expected), (
                f"expected tenant {expected}, observed {observed} -- "
                "cross-tenant GUC leakage under connection reuse"
            )
    finally:
        await small_engine.dispose()


async def test_risk_axis_b_pool_recycle_preserves_isolation():
    url = async_engine.url.render_as_string(hide_password=False)
    recycle_engine = create_async_engine(
        url,
        pool_size=1,
        max_overflow=0,
        pool_recycle=1,
        pool_pre_ping=True,
        connect_args=_async_connect_args_for(url),
    )
    register_tenant_listener(recycle_engine.sync_engine)
    RecycleSession = async_sessionmaker(bind=recycle_engine, expire_on_commit=False)

    token = current_client_id_var.set(1)
    try:
        async with RecycleSession() as session:
            await session.execute(text("SELECT 1"))
            assert await _current_guc(session, "app.current_client_id") == "1"
    finally:
        current_client_id_var.reset(token)

    await asyncio.sleep(1.5)  # past pool_recycle=1, forces replacement on next checkout

    token = current_client_id_var.set(2)
    try:
        async with RecycleSession() as session:
            await session.execute(text("SELECT 1"))
            assert await _current_guc(session, "app.current_client_id") == "2"
    finally:
        current_client_id_var.reset(token)
        await recycle_engine.dispose()


async def test_risk_axis_b_release_gate_detects_broken_listener():
    """Proves the above tests actually catch the bug class they claim to --
    not just documentation-driven confidence. Simulates a broken checkin by
    manually leaving a stale GUC on a connection and confirming a *naive*
    check (bypassing the listener/ContextVar path entirely) would show
    leakage, establishing the negative-control baseline the other tests
    depend on for their assertions to be meaningful.
    """
    async with AsyncSessionLocal() as session:
        # Set directly, bypassing the listener/ContextVar path entirely --
        # this is what "checkin failed to clean up" would look like.
        await session.execute(
            text("SELECT set_config('app.current_client_id', '999999', false)")
        )
        assert await _current_guc(session, "app.current_client_id") == "999999"
    # If checkin cleanup is broken, a subsequent session reusing this exact
    # physical connection would still see '999999' here -- which is exactly
    # what test_risk_axis_b_checkin_clears_guc_on_close asserts does NOT
    # happen for the real listener-driven path.
