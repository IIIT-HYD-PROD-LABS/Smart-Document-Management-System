"""SQLAlchemy database engine, session factory, and Base model."""

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings


# SSL required only for remote production databases. Local docker-compose
# Postgres (hostname `db`), localhost, and 127.0.0.1 connect without SSL.
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "@db:", "@db/")


def _connect_args_for(url: str) -> dict:
    args: dict = {"connect_timeout": 10}
    if url.startswith("postgresql") and not any(h in url for h in _LOCAL_HOSTS):
        args["sslmode"] = "require"
    return args


def _async_url_for(sync_url: str) -> str:
    """Rewrite a sync (psycopg2-implied) DSN to the asyncpg dialect."""
    return make_url(sync_url).set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)


def _async_connect_args_for(url: str) -> dict:
    # asyncpg.connect() takes `timeout`/`ssl`, not psycopg2's `connect_timeout`/
    # `sslmode` -- reusing _connect_args_for's dict verbatim would raise
    # TypeError on first connect. `ssl=True` asks asyncpg to build a default
    # SSLContext, which VERIFIES the server cert -- stricter than psycopg2's
    # sslmode="require" (encrypt only, no cert validation). Not exercised by
    # any current DSN (all local, see _LOCAL_HOSTS), but revisit this if a
    # future remote host presents a cert that fails default verification --
    # sslmode="require" parity would need an SSLContext with
    # verify_mode=ssl.CERT_NONE instead of the bare `True` here.
    args: dict = {"timeout": 10}
    if url.startswith("postgresql") and not any(h in url for h in _LOCAL_HOSTS):
        args["ssl"] = True
    return args


# RLS activation gate (see Settings.DB_ENFORCE_RLS). When enabled AND a runtime
# DSN is configured, the app process connects as the non-owner `app_runtime`
# role so the RLS policies on client-scoped tables are enforced. Otherwise it
# connects as the owner role (BYPASSRLS) and the explicit per-endpoint
# client_id filters are the active isolation layer. Migrations always use
# DATABASE_URL (owner) via alembic, regardless of this gate.
_enforce_rls = bool(settings.DB_ENFORCE_RLS and settings.DATABASE_URL_RUNTIME)
_db_url = settings.DATABASE_URL_RUNTIME if _enforce_rls else settings.DATABASE_URL

engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_timeout=30,
    echo=False,
    connect_args=_connect_args_for(_db_url),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Owner engine for the few privileged BOOTSTRAP operations that cannot satisfy
# RLS WITH CHECK because no tenant context exists yet — onboarding a brand-new
# client (Client + Registrations + Memberships in one transaction, before any
# membership row exists). When RLS is NOT enforced the app engine already IS
# the owner, so reuse it instead of opening a second pool. This engine BYPASSES
# RLS: use get_bootstrap_db ONLY for first-client onboarding, never for normal
# tenant-scoped reads/writes (that would be an IDOR).
if _enforce_rls:
    owner_engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
        pool_timeout=30,
        echo=False,
        connect_args=_connect_args_for(settings.DATABASE_URL),
    )
else:
    owner_engine = engine

SessionBootstrap = sessionmaker(autocommit=False, autoflush=False, bind=owner_engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_bootstrap_db():
    """Owner-role session for first-client onboarding ONLY (RLS-bypassing).

    See `owner_engine` above. Do NOT use for tenant-scoped queries.
    """
    db = SessionBootstrap()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Async engine -- FastAPI HTTP/WebSocket request path only. Celery, Alembic,
# and CLI scripts stay on the sync engine/SessionLocal above permanently (see
# app/tasks/__init__.py's worker_process_init: forked prefork workers can't
# safely carry an asyncio event loop across fork, and there's no persistent
# loop between task invocations to justify the async driver anyway).
#
# Same dual-engine split as the sync side, mirrored exactly: `async_engine`
# is the RLS-subject app_runtime connection (or owner, when RLS disabled),
# `owner_async_engine` is BYPASSRLS, single legitimate consumer is
# get_bootstrap_async_db for first-client onboarding.
_async_db_url = _async_url_for(_db_url)

async_engine = create_async_engine(
    _async_db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_timeout=30,
    echo=False,
    connect_args=_async_connect_args_for(_async_db_url),
)

# expire_on_commit=False: after commit, a default AsyncSession expires all
# ORM attributes so the next access re-fetches them -- but that re-fetch is
# normally implicit/lazy, which needs an await and cannot happen inside plain
# attribute access under async. Same underlying hazard as the unaudited
# lazy-relationship-loading risk (MissingGreenlet); this specific case is the
# documented, standard mitigation for it.
AsyncSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, expire_on_commit=False
)

if _enforce_rls:
    _async_owner_url = _async_url_for(settings.DATABASE_URL)
    owner_async_engine = create_async_engine(
        _async_owner_url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
        pool_timeout=30,
        echo=False,
        connect_args=_async_connect_args_for(_async_owner_url),
    )
else:
    owner_async_engine = async_engine

AsyncSessionBootstrap = async_sessionmaker(
    autocommit=False, autoflush=False, bind=owner_async_engine, expire_on_commit=False
)


async def get_async_db():
    """Async dependency that provides a database session per request."""
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()


async def get_bootstrap_async_db():
    """Async owner-role session for first-client onboarding ONLY (RLS-bypassing).

    See `owner_async_engine` above. Do NOT use for tenant-scoped queries.
    """
    db = AsyncSessionBootstrap()
    try:
        yield db
    finally:
        await db.close()


# Phase 9: Register tenant_context listener so every cursor.execute sets
# app.current_client_id, app.cross_client_mode, app.user_id from ContextVars
# (populated by TenantContextMiddleware). RLS policies on compliance_* tables
# automatically filter rows per these vars. The import is deferred to module
# bottom so app.compliance.middleware can import from app.database without
# triggering a circular import. Only the app engine gets the listener; the
# owner bootstrap engine intentionally does not (it bypasses RLS by design).
from app.compliance.middleware.tenant_context import register_tenant_listener  # noqa: E402

register_tenant_listener(engine)

# AsyncEngine has no events of its own -- ConnectionEvents/PoolEvents are
# registered on the real underlying Engine, exposed via `.sync_engine`. The
# adapted DBAPI-level cursor/connection asyncpg hands to sync-style hooks
# (like this listener) presents a synchronous-looking execute()/commit()
# surface backed by SQLAlchemy's greenlet bridge, so the listener body itself
# needs no changes. Same owner-engine exclusion as the sync registration
# above.
register_tenant_listener(async_engine.sync_engine)
