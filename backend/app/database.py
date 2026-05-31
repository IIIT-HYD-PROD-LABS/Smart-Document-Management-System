"""SQLAlchemy database engine, session factory, and Base model."""

from sqlalchemy import create_engine
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


# Phase 9: Register tenant_context listener so every cursor.execute sets
# app.current_client_id, app.cross_client_mode, app.user_id from ContextVars
# (populated by TenantContextMiddleware). RLS policies on compliance_* tables
# automatically filter rows per these vars. The import is deferred to module
# bottom so app.compliance.middleware can import from app.database without
# triggering a circular import. Only the app engine gets the listener; the
# owner bootstrap engine intentionally does not (it bypasses RLS by design).
from app.compliance.middleware.tenant_context import register_tenant_listener  # noqa: E402

register_tenant_listener(engine)
