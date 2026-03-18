"""FastAPI application entry point."""

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import auth, documents, ml, admin
from app.utils.logging import setup_logging
from app.utils.rate_limiter import limiter

# Configure structured logging BEFORE anything else
setup_logging()

# Database tables managed by Alembic migrations (see backend/alembic/)
# Database setup:
# Fresh database: cd backend && alembic upgrade head
# Existing database (from create_all): cd backend && alembic stamp head
# New migration: cd backend && alembic revision --autogenerate -m "description"

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
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Middleware stack
# Order matters: LAST added = FIRST executed on incoming requests.
#   1. CORSMiddleware          (outermost -- handles preflight early)
#   2. SecurityHeadersMiddleware
#   3. RequestLoggingMiddleware
#   4. CorrelationIdMiddleware  (innermost -- generates request ID first)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(CorrelationIdMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(ml.router)
app.include_router(admin.router)


@app.get("/", tags=["Root"])
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else None,
    }


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}
