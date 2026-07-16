"""FastAPI application entry point."""

from contextlib import asynccontextmanager

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from sqlalchemy import text

from app.compliance.middleware.tenant_context import TenantContextMiddleware
from app.config import settings
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import auth, documents, ml, admin, early_access
from app.utils.logging import setup_logging
from app.utils.rate_limiter import limiter

# Configure structured logging BEFORE anything else
setup_logging()

# Database tables managed by Alembic migrations (see backend/alembic/)
# Database setup:
# Fresh database: cd backend && alembic upgrade head
# Existing database (from create_all): cd backend && alembic stamp head
# New migration: cd backend && alembic revision --autogenerate -m "description"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Phase 15: APScheduler warm-up + MCP server init.

    Reconciliation #1 (D-38): MCP transport is in-memory
    (Client(server_instance)); no child process to spawn here.
    Reconciliation #5: this is the FIRST lifespan handler in main.py.

    APScheduler init is best-effort. The runtime DB role (app_runtime) does
    not own schema public, so the scheduler's lazy CREATE TABLE for
    apscheduler_jobs raises InsufficientPrivilege when the table is absent.
    A separate migration owns table creation; the lifespan only triggers
    the scheduler when it can.
    """
    import structlog as _structlog

    _bootlog = _structlog.stdlib.get_logger()

    import app.email.mcp.server  # noqa: F401  -- register module-level FastMCP instance

    try:
        from app.compliance.services.scheduler import get_scheduler

        get_scheduler()  # lazy-init; pulls persisted jobs from apscheduler_jobs
    except Exception as exc:  # noqa: BLE001 — scheduler must not block app startup
        _bootlog.warning(
            "scheduler_init_skipped",
            reason=type(exc).__name__,
            detail=str(exc)[:240],
            note=(
                "FastAPI startup proceeded; deadline alerts will be scheduled "
                "lazily on next /api/compliance/* request that triggers add_job."
            ),
        )
    yield
    # Shutdown: APScheduler atexit handler closes the scheduler if it started.


# Initialize FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered Smart Document Management System that automatically "
        "organizes documents using ML classification, OCR, and intelligent search."
    ),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Middleware stack
# Order matters: LAST added = FIRST executed on incoming requests.
#   1. CORSMiddleware            (outermost -- handles preflight early)
#   2. GZipMiddleware
#   3. SecurityHeadersMiddleware
#   4. RequestLoggingMiddleware
#   5. CorrelationIdMiddleware
#   6. TenantContextMiddleware   (innermost -- runs FIRST; resolves X-Client-Id
#                                 to ContextVars before any route or
#                                 dependency runs so the SQLAlchemy listener
#                                 has the values available on first query)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Client-Id"],
    max_age=600,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(CorrelationIdMiddleware)

# Phase 9 CLIENT-04: tenant context for RLS — added LAST so it runs FIRST
# on incoming requests (before dependencies resolve get_db).
app.add_middleware(TenantContextMiddleware)


# Reject oversized JSON/form bodies before they are buffered into memory.
# Multipart/file-upload routes (notice/document uploads) legitimately send
# large bodies and stream to disk/storage, so they are exempt from the cap.
MAX_REQUEST_BODY_BYTES = 2_000_000  # 2 MB cap for non-upload payloads


@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):
    content_type = request.headers.get("content-type", "")
    # File uploads stream large bodies by design; skip the cap for them.
    if not content_type.startswith("multipart/form-data"):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )
    return await call_next(request)


# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(ml.router)
app.include_router(admin.router)
app.include_router(early_access.router)

# Phase 9: Compliance routers (Wave 4 / Plan 09-05).
# All seven mount under /api/compliance. Every endpoint composes
# Depends(require_compliance_permission(...)) — RBAC is enforced at the
# route layer; RLS isolation is automatic via TenantContextMiddleware.
from app.compliance.routers import (  # noqa: E402  (intentional grouping with v1.0 routers above)
    ai as compliance_ai,
    alerts as compliance_alerts,
    audit as compliance_audit,
    calendar as compliance_calendar,
    clients as compliance_clients,
    memberships as compliance_memberships,
    notice_types as compliance_notice_types,
    notices as compliance_notices,
    notifications as compliance_notifications,
    portal as compliance_portal,
    regulatory_calendar as compliance_regulatory_calendar,
    reports as compliance_reports,
    responses as compliance_responses,
    review_queue as compliance_review_queue,
    search as compliance_search,
)

app.include_router(compliance_clients.router, prefix="/api/compliance")
app.include_router(compliance_memberships.router, prefix="/api/compliance")
app.include_router(compliance_notices.router, prefix="/api/compliance")
app.include_router(compliance_portal.router, prefix="/api/compliance")
app.include_router(compliance_reports.router, prefix="/api/compliance")
app.include_router(compliance_audit.router, prefix="/api/compliance")
app.include_router(compliance_review_queue.router, prefix="/api/compliance")
# Phase 11 — alerts + calendar
app.include_router(compliance_alerts.router, prefix="/api/compliance")
app.include_router(compliance_calendar.router, prefix="/api/compliance")
# Phase 11 — WebSocket /ws/notifications (no /api prefix; uses ws://)
app.include_router(compliance_notifications.router)
# Phase 12 — response workflow + evidence
app.include_router(compliance_responses.router, prefix="/api/compliance")
# Phase 13 — unified search
app.include_router(compliance_search.router, prefix="/api/compliance")
app.include_router(compliance_notice_types.router, prefix="/api/compliance")
app.include_router(compliance_regulatory_calendar.router, prefix="/api/compliance")
# Phase 16 — BYOK AI surface (notice + invoice summaries / actions / timing)
app.include_router(compliance_ai.router, prefix="/api/compliance")

# Phase 15 — Gmail MCP integration routers (Plan 15-05 Wave 4).
# All seven mount under /api/email. Every endpoint composes
# Depends(require_compliance_permission(EMAIL_INTEGRATION_USE)) so the
# RBAC + RLS posture matches Phase 9 compliance routers above.
from app.email.routers import (  # noqa: E402  (intentional grouping)
    activity as gmail_activity_router,
    bills as gmail_bills_router,
    credentials as gmail_credentials_router,
    filter_rules as gmail_filter_rules_router,
    oauth as gmail_oauth_router,
    view_email as gmail_view_email_router,
)

app.include_router(gmail_oauth_router.router, prefix="/api/email", tags=["gmail"])
app.include_router(gmail_credentials_router.router, prefix="/api/email", tags=["gmail"])
app.include_router(gmail_filter_rules_router.router, prefix="/api/email", tags=["gmail"])
app.include_router(gmail_activity_router.router, prefix="/api/email", tags=["gmail"])
app.include_router(gmail_bills_router.router, prefix="/api/email", tags=["gmail"])
app.include_router(gmail_view_email_router.router, prefix="/api/email", tags=["gmail"])


_logger = structlog.stdlib.get_logger()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    _logger.error("unhandled_exception", path=request.url.path, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "An internal server error occurred."})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        errors.append({
            "loc": list(err.get("loc", [])),
            "msg": str(err.get("msg", "")),
            "type": str(err.get("type", "")),
        })
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/", tags=["Root"])
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else None,
    }


# Module-level cached Redis client for /api/health. The previous handler
# constructed a fresh `redis.from_url(...)` on every request, paying TCP
# handshake + auth + (in TLS mode) SSL context setup each call. Under the
# 10-RPS concurrency the live E2E probe ran, p99 hit ~5 seconds. Lazy
# singleton recovers the steady-state to sub-100ms per call.
_health_redis_client = None


def _get_health_redis():
    global _health_redis_client
    if _health_redis_client is not None:
        return _health_redis_client
    import redis
    redis_kwargs = {"socket_connect_timeout": 5, "socket_timeout": 5}
    if settings.REDIS_URL.startswith("rediss://"):
        import ssl
        ctx = ssl.create_default_context()
        if not settings.REDIS_SSL_VERIFY:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        redis_kwargs["ssl"] = ctx
    _health_redis_client = redis.from_url(settings.REDIS_URL, **redis_kwargs)
    return _health_redis_client


@app.get("/api/health/live", tags=["Health"])
def liveness_check():
    """Kubernetes-style liveness probe: the process is up and the event loop
    is responsive. Does NOT touch the DB or Redis, so it stays cheap and
    cannot flip the container to unhealthy when an external dependency has
    a transient outage. Used as the docker-compose healthcheck."""
    return {"status": "alive"}


@app.get("/api/health", tags=["Health"])
def health_check():
    """Detailed health check for monitoring."""
    health = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        # Intentionally omit `debug` — advertising DEBUG=true on a public
        # health endpoint is free reconnaissance for attackers.
    }

    # Check database
    try:
        from app.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception:
        health["database"] = "disconnected"
        health["status"] = "degraded"

    # Check Redis (uses cached client so a hot path is ~1 round trip)
    try:
        _get_health_redis().ping()
        health["redis"] = "connected"
    except Exception:
        # Reset the cached client so the next call can re-establish
        # against a healed Redis rather than reusing the broken socket.
        global _health_redis_client
        _health_redis_client = None
        health["redis"] = "disconnected"
        health["status"] = "degraded"

    if health["status"] == "degraded":
        return JSONResponse(status_code=503, content=health)
    return health
