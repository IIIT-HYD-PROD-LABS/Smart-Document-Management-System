"""Tenant context middleware — Phase 9 CLIENT-04.

Sets PostgreSQL session variables `app.current_client_id`, `app.user_id`, and
`app.cross_client_mode` per-statement based on a ContextVar populated by FastAPI
middleware. This makes RLS policies (migrations 0015 + 0018) automatic for any
query running inside a request context.

Header convention:
  X-Client-Id: 42       → tenant_isolation policy filters to client_id=42
  X-Client-Id: *        → cross-client mode (only allowed for compliance_head/ca_consultant/cfo)
  (no header)           → no context set; RLS denies all rows (fail-closed)

Per RESEARCH Pitfall 5: the route layer must look up (user_id, client_id) →
membership and reject with 403 if not found OR membership expired. Frontend
Zustand store cross-checks activeClientId against /memberships/me.

CONNECTION-CHECKOUT vs BEFORE-CURSOR-EXECUTE
---------------------------------------------
PostgreSQL `set_config(..., is_local=true)` is transaction-local: after `COMMIT`
the value is GONE. `SET LOCAL ROLE` is also transaction-local. SQLAlchemy
re-uses the same connection across commits within a session, so a one-shot
checkout listener loses both after the first commit inside a request.

We therefore install the role + tenant vars on a `before_cursor_execute` event:
fires on every SQL statement, idempotent, and survives intra-request commits.
The cost is one ALTER-style call per cursor.execute — measured at sub-ms per
call against a local Postgres.

Production note: `app_runtime` is a non-table-owner non-BYPASSRLS role. The
listener calls `SET ROLE app_runtime` only when the underlying connection is
authenticated as a higher-privilege user (postgres in dev, app_migrator in
prod). That keeps RLS enforced even when the runtime DSN is not the literal
app_runtime user.
"""

import contextvars
from typing import Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import event as sa_event
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# ContextVars: carry tenant state through the request lifecycle.
# Listeners read from these and write to PostgreSQL session variables.
# ---------------------------------------------------------------------------
current_client_id_var: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "current_client_id", default=None
)
cross_client_mode_var: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "cross_client_mode", default=False
)
current_user_id_var: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "current_user_id", default=None
)


# Marker so we never register the listener twice on the same engine.
_LISTENER_REGISTERED_MARKER = "_phase9_tenant_listener_registered"


def register_tenant_listener(engine) -> None:
    """Register the per-statement tenant_context listener ONCE at startup.

    Reads ContextVars and runs `set_config()` + `SET ROLE` on every cursor
    execute. Idempotent: if already registered on this engine, no-op.
    """
    if getattr(engine, _LISTENER_REGISTERED_MARKER, False):
        return
    setattr(engine, _LISTENER_REGISTERED_MARKER, True)

    @sa_event.listens_for(engine, "before_cursor_execute")
    def _set_tenant_before_each_statement(
        conn, cursor, statement, parameters, context, executemany
    ):
        # Skip the listener's own SET / SELECT set_config / RESET / SHOW
        # statements to avoid infinite recursion on the same cursor.
        # Match a small, fixed prefix set rather than full parsing.
        s = statement.lstrip().upper()
        if (
            s.startswith("SET ")
            or s.startswith("RESET ")
            or s.startswith("SHOW ")
            or "SET_CONFIG(" in s
            or "CURRENT_SETTING(" in s
        ):
            return

        client_id = current_client_id_var.get()
        cross_mode = cross_client_mode_var.get()
        user_id = current_user_id_var.get()

        # No tenant context set → leave session as-is. The connection is still
        # authenticated as the configured DB role (app_runtime in production,
        # postgres in dev tests when the test fixture has not opted in).
        if client_id is None and not cross_mode and user_id is None:
            return

        new_state = (
            str(client_id) if client_id is not None else "",
            "true" if cross_mode else "false",
            str(user_id) if user_id is not None else "",
        )
        # WAN-perf hardening: when the same tenant tuple has already been
        # SET on this connection, skip the redundant round-trip. Cleared on
        # checkin so the next request starts blank.
        #
        # IMPORTANT: this dedup assumes Supavisor SESSION-mode pooling
        # (Supabase pooler port 5432). It is NOT safe under transaction-
        # mode pooling (port 6543), where set_config(..., is_local=false)
        # values do not persist across transactions and `_tenant_state`
        # would falsely match. The override file enforces port 5432; if
        # the deployment ever flips to 6543, this listener must change.
        # State on conn.connection.info (PoolProxiedConnection dict that
        # mirrors connection_record.info and persists across checkouts).
        # The previous attribute-on-psycopg2-conn approach raised
        # AttributeError silently inside `except: pass`, so dedup never
        # actually worked. Combined-SET round-trip reduction is what
        # delivered the perf gain; this fix makes dedup work too.
        info = conn.connection.info
        if info.get("_tenant_state") == new_state:
            return
        # Mark dirty BEFORE issuing the SQL so checkin cleanup always
        # runs after any attempt — even one that raised mid-execute. Was
        # a security-auditor finding: order matters for fail-closed
        # tenant context across a connection that gets recycled.
        info["_tenant_dirty"] = True
        try:
            # Combined into ONE round trip (was 3 separate executes).
            # set_config(name, value, is_local=false) → session-scoped,
            # cleaned up on checkin so the next request starts clean.
            cursor.execute(
                "SELECT "
                "set_config('app.current_client_id', %s, false), "
                "set_config('app.cross_client_mode', %s, false), "
                "set_config('app.user_id', %s, false)",
                new_state,
            )
            info["_tenant_state"] = new_state
        except Exception as exc:
            # Invalidate the cache so the next call cannot match the
            # shortcut against state Postgres no longer has — fail-open
            # to a re-attempt rather than silently skip. Cleanup will
            # still run on checkin because _tenant_dirty was set above.
            info["_tenant_state"] = None
            # Log but do not re-raise: RLS still fail-closes when the
            # tenant context is missing, and we don't want a transient
            # listener failure to crash an otherwise-valid request.
            import logging
            logging.getLogger(__name__).warning(
                "tenant_context listener failed to set session state: %r", exc
            )

    @sa_event.listens_for(engine, "checkin")
    def _clear_tenant_on_checkin(dbapi_connection, connection_record):
        """Reset tenant context when the connection returns to the pool.

        Critical: without this, a connection that served a request for client A
        could be handed to a request that hasn't set tenant context yet. RLS
        would still see the leftover client A id and leak rows.

        psycopg2 default is autocommit=False, so the SELECT set_config calls
        below open an implicit transaction. We MUST commit (or rollback) before
        the connection returns to the pool — otherwise the next checkout sees
        an "idle in transaction" connection and SQLAlchemy's pool_pre_ping
        SELECT 1 fails intermittently. This was the root cause of the
        /api/health 200/503 flap.
        """
        # WAN-perf hardening: skip cleanup when this connection never wrote
        # any tenant state during the just-finished request (e.g. /api/health,
        # pool pre_ping). _tenant_dirty is set by before_cursor_execute when
        # SET was issued. State lives on connection_record.info (the same
        # dict the per-cursor handler reads via conn.connection.info).
        info = connection_record.info
        if not info.get("_tenant_dirty"):
            return
        try:
            cur = dbapi_connection.cursor()
            # Combined into ONE round trip (was 3 separate executes).
            cur.execute(
                "SELECT "
                "set_config('app.current_client_id', '', false), "
                "set_config('app.cross_client_mode', 'false', false), "
                "set_config('app.user_id', '', false)"
            )
            cur.close()
            if not getattr(dbapi_connection, "autocommit", True):
                dbapi_connection.commit()
            info["_tenant_state"] = None
            info["_tenant_dirty"] = False
        except Exception:
            # Cleanup failed: the next checkout could see this connection
            # with the prior request's `app.current_client_id` still set,
            # breaking tenant isolation. Discard the connection so the
            # pool opens a fresh one instead of recycling tainted state.
            import logging
            logging.getLogger(__name__).warning(
                "tenant_context checkin cleanup failed; invalidating connection"
            )
            try:
                if not getattr(dbapi_connection, "autocommit", True):
                    dbapi_connection.rollback()
            except Exception:
                logging.getLogger(__name__).exception(
                    "tenant_context rollback after cleanup failure also failed"
                )
            try:
                connection_record.invalidate()
            except Exception:
                logging.getLogger(__name__).exception(
                    "tenant_context connection invalidate failed"
                )


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Resolves X-Client-Id header → ContextVars on every /api/compliance/* request.

    The downstream route handler dependency (`get_active_membership`) validates
    that the authenticated user has a non-expired membership for X-Client-Id;
    this middleware only populates ContextVars from the header. ContextVar
    isolation is provided by Python's contextvars module + Starlette's per-task
    context copy semantics, so there is no cross-request leakage.
    """

    # Public paths that don't need tenant context (auth, health, OpenAPI)
    PUBLIC_PREFIXES = (
        "/api/auth/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/health",
    )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Bypass for paths not requiring tenant context
        if any(path.startswith(p) for p in self.PUBLIC_PREFIXES):
            return await call_next(request)

        # Enforce on /api/compliance/* + /api/email/* (Phase 15 routes are
        # gated by require_compliance_permission and need the same tenant
        # context). v1.0 routes stay user-scoped.
        if not (
            path.startswith("/api/compliance")
            or path.startswith("/api/email")
        ):
            return await call_next(request)

        client_header = request.headers.get("X-Client-Id")

        client_token = None
        cross_token = None
        try:
            if client_header == "*":
                cross_token = cross_client_mode_var.set(True)
                client_token = current_client_id_var.set(None)
            elif client_header:
                try:
                    client_token = current_client_id_var.set(int(client_header))
                    cross_token = cross_client_mode_var.set(False)
                except ValueError:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": "Invalid X-Client-Id header"},
                    )
            else:
                # No client header — /api/compliance/* without header → fail-closed
                # via RLS (no rows). Endpoints requiring tenant context will
                # additionally raise 400 in get_active_client_id dependency.
                client_token = current_client_id_var.set(None)
                cross_token = cross_client_mode_var.set(False)

            response = await call_next(request)
            return response
        finally:
            # Reset ContextVars to avoid leaking to next request
            if client_token is not None:
                try:
                    current_client_id_var.reset(client_token)
                except Exception:
                    pass
            if cross_token is not None:
                try:
                    cross_client_mode_var.reset(cross_token)
                except Exception:
                    pass


def set_tenant_context_for_celery(
    client_id: Optional[int],
    user_id: Optional[int],
    cross_mode: bool = False,
) -> None:
    """Helper for Celery tasks — call at task start to set ContextVars.

    Per RESEARCH Pitfall 6: Celery workers do NOT inherit middleware. Task code
    MUST call this BEFORE issuing any DB query that touches client-scoped tables.

    Example:
        @celery_app.task
        def regenerate_report(client_id: int, user_id: int):
            set_tenant_context_for_celery(client_id, user_id)
            # All ORM queries below see RLS-filtered rows for this client only.
            ...
    """
    current_client_id_var.set(client_id)
    current_user_id_var.set(user_id)
    cross_client_mode_var.set(cross_mode)
