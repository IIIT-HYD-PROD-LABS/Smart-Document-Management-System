"""Regression: TenantContextMiddleware must set app.user_id from the JWT.

The RLS cutover failed because get_current_user sets current_user_id_var in a
sync threadpool dependency, whose ContextVar mutation does not propagate to the
route handler's DB query. Under RLS that left app.user_id empty and fail-closed
the user-scoped policies. The middleware now decodes the JWT in the async
request context (which DOES propagate) and sets current_user_id_var there.

This test asserts the middleware sets the var from a Bearer token for a
compliance path, and leaves it unset for a public path / missing token.
"""
import asyncio

from starlette.requests import Request
from starlette.responses import Response

from app.compliance.middleware.tenant_context import (
    TenantContextMiddleware,
    current_user_id_var,
)
from app.utils.security import create_access_token


def _run(path: str, headers: list[tuple[bytes, bytes]]):
    """Drive the middleware once and capture current_user_id_var as seen by the
    downstream handler (the value the SQLAlchemy listener would read)."""
    captured = {}

    async def call_next(_req):
        captured["uid"] = current_user_id_var.get()
        return Response("ok")

    mw = TenantContextMiddleware(app=lambda *a, **k: None)
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": headers,
    }
    asyncio.run(mw.dispatch(Request(scope), call_next))
    return captured.get("uid")


def test_middleware_sets_user_id_from_jwt_on_compliance_path():
    tok = create_access_token({"sub": "42"})
    uid = _run(
        "/api/compliance/notices",
        [(b"authorization", b"Bearer " + tok.encode())],
    )
    assert uid == 42


def test_middleware_leaves_user_id_unset_without_token():
    uid = _run("/api/compliance/notices", [])
    assert uid is None


def test_middleware_bypasses_public_path():
    tok = create_access_token({"sub": "42"})
    # /api/health is a public prefix — middleware returns early, never sets uid.
    uid = _run("/api/health", [(b"authorization", b"Bearer " + tok.encode())])
    assert uid is None
