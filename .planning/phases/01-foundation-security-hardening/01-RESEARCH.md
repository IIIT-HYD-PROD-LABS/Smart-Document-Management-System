# Phase 1: Foundation & Security Hardening - Research

**Researched:** 2026-02-17
**Domain:** FastAPI security, configuration management, structured logging, database migrations
**Confidence:** HIGH (all core libraries verified via Context7 and official PyPI)

## Summary

This phase transforms the application from a development prototype (hardcoded secrets, no rate limiting, no logging, no migrations) into a production-grade foundation. The codebase currently has critical security vulnerabilities including a hardcoded `SECRET_KEY`, wildcard CORS, 24-hour JWT tokens with no refresh mechanism, no rate limiting, no security headers, print-statement logging, and `Base.metadata.create_all()` instead of proper migrations.

The standard approach for FastAPI applications uses: `pydantic-settings` for validated environment configuration (already partially in place), `PyJWT` for access + refresh token management (already used for access tokens), `slowapi` for rate limiting backed by the existing Redis instance, a custom middleware for security headers (lightweight, no library needed), `structlog` for structured JSON logging with request ID correlation, and `alembic` for database migration management (already in requirements.txt but not initialized).

**Primary recommendation:** Address each requirement (SEC-01 through SEC-05, INFR-01) as a distinct plan, implementing them in dependency order: environment config first (everything depends on it), then JWT refresh tokens, then rate limiting, security headers, structured logging, and finally Alembic migrations.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-settings | 2.13.0 | Environment-based configuration with validation | Already in use (2.1.0). Built-in `.env` file support, type coercion, and startup validation. Pydantic v2 native. |
| PyJWT | 2.11.0 | JWT access and refresh token creation/validation | Already in use (2.8.0). Pure Python, well-maintained, supports HS256/RS256. No need to switch to python-jose. |
| slowapi | 0.1.9 | Rate limiting for FastAPI/Starlette endpoints | De facto standard for FastAPI rate limiting. Adapted from flask-limiter. Supports Redis backend (already available). |
| structlog | 25.5.0 | Structured JSON logging with context propagation | Most popular structured logging library for Python. Context variables support for async. Replaces print statements. |
| alembic | 1.18.4 | Database schema migrations | Official SQLAlchemy migration tool. Already in requirements.txt (1.13.0) but never initialized. |
| asgi-correlation-id | 4.x | Request ID generation and propagation | Lightweight ASGI middleware for generating unique request IDs. Integrates cleanly with structlog. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.0.0 | Load `.env` files | Already in use. Loaded by pydantic-settings automatically. |
| redis | 5.0.1 | Redis client for rate limit storage | Already in requirements. Used by slowapi for distributed rate limiting. |
| passlib[bcrypt] | 1.7.4 | Password hashing | Already in use. No changes needed for Phase 1. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slowapi | fastapi-limiter | fastapi-limiter (0.1.6) uses Lua scripts and requires more Redis setup. slowapi is simpler and better documented for basic use. |
| Custom security headers middleware | Secweb (1.30.10) | Secweb provides 16 middlewares but is overkill for 4-5 headers. A simple custom middleware is ~20 lines and avoids dependency. |
| structlog | python-json-logger | python-json-logger is simpler but lacks structlog's processor chain, context variables, and async support. structlog is the industry standard. |
| PyJWT | python-jose | python-jose is maintenance-stale. PyJWT is actively maintained (2.11.0, Jan 2026). Project already uses PyJWT. |

**Installation (additions to requirements.txt):**
```
slowapi==0.1.9
structlog==25.5.0
asgi-correlation-id==4.3.4
```

**Version upgrades needed:**
```
# Existing packages to update
PyJWT==2.11.0          # from 2.8.0
alembic==1.18.4        # from 1.13.0
pydantic-settings==2.13.0  # from 2.1.0
```

**Note:** The `alembic` upgrade from 1.13.0 to 1.18.4 requires Python >=3.10 (verify project's Python version).

## Architecture Patterns

### Recommended Project Structure Changes

```
backend/
├── alembic/                    # NEW: Alembic migrations directory
│   ├── env.py                  # Migration environment configuration
│   ├── script.py.mako          # Migration template
│   └── versions/               # Migration revision files
│       └── 001_initial_schema.py
├── alembic.ini                 # NEW: Alembic configuration
├── app/
│   ├── config.py               # MODIFY: Add validation, remove defaults
│   ├── main.py                 # MODIFY: Remove create_all, add middlewares
│   ├── database.py             # NO CHANGE (used by Alembic env.py)
│   ├── middleware/              # NEW: Custom middleware package
│   │   ├── __init__.py
│   │   ├── security_headers.py # Security headers middleware
│   │   └── logging.py          # Request logging middleware
│   ├── utils/
│   │   ├── security.py         # MODIFY: Add refresh token functions
│   │   └── logging.py          # NEW: structlog configuration
│   ├── models/
│   │   ├── user.py             # NO CHANGE
│   │   ├── document.py         # NO CHANGE
│   │   └── refresh_token.py    # NEW: RefreshToken model
│   ├── schemas/
│   │   ├── __init__.py         # MODIFY: Add refresh token schemas
│   │   └── document.py         # NO CHANGE
│   └── routers/
│       ├── auth.py             # MODIFY: Add refresh/logout endpoints
│       └── documents.py        # MODIFY: Add rate limiting decorators
└── .env.example                # MODIFY: Add new required variables
```

### Pattern 1: Environment Configuration with Startup Validation (SEC-01)

**What:** Remove all hardcoded secrets from `config.py`. Make critical fields required (no defaults). Application refuses to start if env vars are missing.

**Why:** The current `SECRET_KEY = "super-secret-key-change-in-production"` means the app can run in production with a known, insecure key. Removing the default forces explicit configuration.

**Current state (VULNERABLE):**
```python
# backend/app/config.py - CURRENT
class Settings(BaseSettings):
    SECRET_KEY: str = "super-secret-key-change-in-production"  # INSECURE DEFAULT
    DEBUG: bool = True  # INSECURE DEFAULT
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/smart_docs"  # HARDCODED CREDS
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours - too long
```

**Target state (SECURE):**
```python
# backend/app/config.py - TARGET
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Smart Document Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False  # Default to secure (False)

    # Database - REQUIRED, no default
    DATABASE_URL: str

    # JWT Auth - REQUIRED, no default for SECRET_KEY
    SECRET_KEY: str  # No default! App won't start without it.
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes (was 24 hours)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days for refresh tokens

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]  # Environment-specific

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"]

    # AWS S3 (optional)
    USE_S3: bool = False
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str = "smart-docs-bucket"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Rate Limiting
    RATE_LIMIT_AUTH: str = "5/minute"       # Auth endpoints
    RATE_LIMIT_UPLOAD: str = "10/minute"    # Upload endpoints
    RATE_LIMIT_DEFAULT: str = "60/minute"   # General endpoints

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = True  # JSON in production, pretty in dev

    # ML Model
    MODEL_DIR: str = "./models"
    ML_CONFIDENCE_THRESHOLD: float = 0.3

    # Tesseract OCR
    TESSERACT_CMD: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if v in ("super-secret-key-change-in-production", "super-secret-docker-key", "changeme", "secret"):
            raise ValueError("SECRET_KEY must be changed from default insecure value")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v
```

**How pydantic-settings validation works:** Fields without defaults (like `SECRET_KEY: str` and `DATABASE_URL: str`) are required. When `Settings()` is instantiated and the env var is missing, pydantic raises a `ValidationError` immediately. The app never starts. The `field_validator` on SECRET_KEY additionally rejects known-insecure values and short keys.

**Docker-compose .env pattern:**
```yaml
# docker-compose.yml - TARGET
services:
  backend:
    env_file: .env  # Load from .env file instead of hardcoding
    environment:
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
  postgres:
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

```env
# .env (not committed to git, .gitignore'd)
SECRET_KEY=your-cryptographically-random-string-at-least-32-chars
POSTGRES_DB=smart_docs
POSTGRES_USER=postgres
POSTGRES_PASSWORD=a-strong-random-password-here
DATABASE_URL=postgresql://postgres:a-strong-random-password-here@localhost:5432/smart_docs
ALLOWED_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

### Pattern 2: JWT Refresh Token Mechanism (SEC-02)

**What:** Short-lived access tokens (30 min) + long-lived refresh tokens (7 days) stored in the database with rotation on each use.

**Why:** The current 24-hour access token is far too long. If stolen, the attacker has a full day of access. With 30-minute access tokens + refresh tokens, a stolen access token is usable for max 30 minutes, and refresh tokens can be revoked server-side.

**Database Model for Refresh Tokens:**
```python
# backend/app/models/refresh_token.py - NEW FILE
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # For token rotation: track which token was used to issue this one
    replaced_by = Column(String(500), nullable=True)

    user = relationship("User")

    __table_args__ = (
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_expires", "expires_at"),
    )
```

**Token Creation Functions:**
```python
# backend/app/utils/security.py - ADDITIONS
import secrets
from datetime import datetime, timedelta, timezone

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived JWT access token (30 minutes default)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token() -> tuple[str, datetime]:
    """Create a cryptographically secure refresh token (opaque string, NOT a JWT).

    Returns (token_string, expiry_datetime).
    Opaque tokens are preferred over JWT for refresh tokens because:
    - They can be revoked instantly by deleting from DB
    - No information leakage (JWT payloads are base64, not encrypted)
    - Simpler rotation logic
    """
    token = secrets.token_urlsafe(64)  # 64 bytes = 86 chars, cryptographically random
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return token, expires_at
```

**Critical design decision: Opaque refresh tokens, NOT JWTs.** Refresh tokens are stored in the database as opaque random strings. This is better than JWT refresh tokens because:
1. Instant revocation: Delete the row, token is dead. No waiting for JWT expiry.
2. No information leakage: JWTs are base64 encoded (NOT encrypted), so claims are readable.
3. Simpler rotation: Just generate a new random string and invalidate the old row.
4. Token reuse detection: If an already-used token is presented, revoke ALL tokens for that user (indicates token theft).

**Refresh Endpoint:**
```python
# backend/app/routers/auth.py - NEW ENDPOINT
@router.post("/refresh", response_model=TokenPairResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token + refresh token pair."""
    # 1. Look up the refresh token in database
    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token == payload.refresh_token,
    ).first()

    if not stored_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # 2. Check if token has been revoked (reuse detection)
    if stored_token.is_revoked:
        # SECURITY: Token reuse detected! Revoke ALL tokens for this user.
        db.query(RefreshToken).filter(
            RefreshToken.user_id == stored_token.user_id
        ).update({"is_revoked": True, "revoked_at": datetime.now(timezone.utc)})
        db.commit()
        raise HTTPException(status_code=401, detail="Token reuse detected. All sessions revoked.")

    # 3. Check expiry
    if stored_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # 4. Rotate: Revoke old token, create new pair
    stored_token.is_revoked = True
    stored_token.revoked_at = datetime.now(timezone.utc)

    new_refresh, new_expires = create_refresh_token()
    stored_token.replaced_by = new_refresh  # Trace chain

    db_refresh = RefreshToken(
        token=new_refresh,
        user_id=stored_token.user_id,
        expires_at=new_expires,
    )
    db.add(db_refresh)

    # 5. Create new access token
    access_token = create_access_token(data={"sub": str(stored_token.user_id)})

    db.commit()

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        token_type="bearer",
    )
```

**Logout Endpoint (revoke refresh tokens):**
```python
@router.post("/logout")
def logout(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Revoke the given refresh token on logout."""
    stored = db.query(RefreshToken).filter(
        RefreshToken.token == payload.refresh_token,
        RefreshToken.is_revoked == False,
    ).first()
    if stored:
        stored.is_revoked = True
        stored.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return {"detail": "Logged out"}
```

**Updated Token Response Schemas:**
```python
# backend/app/schemas/__init__.py - ADDITIONS
class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse | None = None  # Included on login/register, not on refresh

class RefreshTokenRequest(BaseModel):
    refresh_token: str
```

**Frontend Token Refresh Flow (Axios interceptor pattern):**
```typescript
// frontend/src/lib/api.ts - UPDATED RESPONSE INTERCEPTOR
let isRefreshing = false;
let failedQueue: Array<{
    resolve: (token: string) => void;
    reject: (error: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
    failedQueue.forEach((prom) => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token!);
        }
    });
    failedQueue = [];
};

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                // Queue this request until refresh completes
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then((token) => {
                    originalRequest.headers.Authorization = `Bearer ${token}`;
                    return api(originalRequest);
                });
            }

            originalRequest._retry = true;
            isRefreshing = true;

            try {
                const refreshToken = Cookies.get("refresh_token");
                if (!refreshToken) throw new Error("No refresh token");

                const { data } = await axios.post(
                    `${API_URL}/api/auth/refresh`,
                    { refresh_token: refreshToken }
                );

                Cookies.set("token", data.access_token, { expires: 1, sameSite: "Strict" });
                Cookies.set("refresh_token", data.refresh_token, { expires: 7, sameSite: "Strict", secure: true });

                api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
                processQueue(null, data.access_token);

                originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
                return api(originalRequest);
            } catch (refreshError) {
                processQueue(refreshError, null);
                Cookies.remove("token");
                Cookies.remove("refresh_token");
                Cookies.remove("user");
                if (typeof window !== "undefined") {
                    window.location.href = "/login";
                }
                return Promise.reject(refreshError);
            } finally {
                isRefreshing = false;
            }
        }
        return Promise.reject(error);
    }
);
```

**Key detail:** The queue pattern prevents multiple simultaneous refresh requests when multiple API calls fail at once. Without it, the app would fire N refresh requests, and token rotation would revoke all but the first, causing cascading failures.

### Pattern 3: Rate Limiting with slowapi (SEC-03)

**What:** Limit request rates on authentication and upload endpoints using slowapi backed by Redis.

**Why:** Without rate limiting, attackers can brute-force passwords or flood the upload endpoint. The existing Redis service in docker-compose provides distributed rate limit storage.

**Configuration:**
```python
# backend/app/utils/rate_limiter.py - NEW FILE
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],  # "60/minute" for all routes
    headers_enabled=True,  # Include X-RateLimit-* headers in responses
)
```

**Integration in main.py:**
```python
# backend/app/main.py
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.utils.rate_limiter import limiter

app = FastAPI(...)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Endpoint decoration:**
```python
# backend/app/routers/auth.py
from app.utils.rate_limiter import limiter

@router.post("/login")
@limiter.limit("5/minute")  # Strict: 5 login attempts per minute per IP
async def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    ...

@router.post("/register")
@limiter.limit("3/minute")  # Very strict: 3 registrations per minute per IP
async def register(request: Request, payload: UserRegister, db: Session = Depends(get_db)):
    ...

# backend/app/routers/documents.py
@router.post("/upload")
@limiter.limit("10/minute")  # 10 uploads per minute per IP
async def upload(request: Request, ...):
    ...
```

**CRITICAL: Decorator order matters.** The route decorator (`@router.post`) MUST be above the limiter decorator (`@limiter.limit`). This is a documented requirement of slowapi.

**CRITICAL: Request parameter required.** Every rate-limited endpoint MUST have `request: Request` as a parameter. slowapi uses this to extract the client IP. Forgetting this causes a runtime error.

### Pattern 4: Security Headers Middleware (SEC-04)

**What:** Add standard security headers to every HTTP response via custom Starlette middleware.

**Why:** These headers instruct browsers to enable built-in security features. Missing headers leave users vulnerable to clickjacking, XSS, MIME sniffing, and protocol downgrade attacks.

```python
# backend/app/middleware/security_headers.py - NEW FILE
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent clickjacking - deny all framing
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable browser XSS filter (legacy, but harmless)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS (only enable if actually serving over HTTPS)
        # For development, this can be omitted or set conditionally
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy - restrict resource loading
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "  # unsafe-inline often needed for CSS frameworks
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # Prevent information leakage via Referrer
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable browser features not needed
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response
```

**Header reference table:**

| Header | Value | What It Prevents |
|--------|-------|-----------------|
| X-Frame-Options | DENY | Clickjacking (embedding in iframes) |
| X-Content-Type-Options | nosniff | MIME type confusion attacks |
| X-XSS-Protection | 1; mode=block | Reflected XSS (legacy browsers) |
| Strict-Transport-Security | max-age=31536000; includeSubDomains | Protocol downgrade, cookie hijacking |
| Content-Security-Policy | default-src 'self' | XSS, code injection, data theft |
| Referrer-Policy | strict-origin-when-cross-origin | Information leakage via referrer |
| Permissions-Policy | camera=(), microphone=(), geolocation=() | Unauthorized feature access |

**Note on HSTS:** Only enable in production (behind HTTPS). In development, HSTS would cause browsers to refuse HTTP connections permanently for that domain. The `settings.DEBUG` check handles this.

**Note on CSP:** The CSP policy above is strict. It may need to be relaxed for the frontend if it loads external fonts (Google Fonts), CDN scripts, or inline styles. CSP violations are logged in browser console, making it easy to identify and adjust.

### Pattern 5: Structured JSON Logging with structlog (SEC-05)

**What:** Replace all `print()` statements with structured, JSON-formatted logging using structlog. Add request ID correlation via asgi-correlation-id middleware.

**Why:** Print statements are invisible to log aggregation systems, have no severity levels, no timestamps, and no request correlation. Structured JSON logs enable filtering, alerting, and distributed tracing.

**Logging setup module:**
```python
# backend/app/utils/logging.py - NEW FILE
import logging
import sys
import structlog
from app.config import settings


def drop_color_message_key(_, __, event_dict):
    """Remove uvicorn's color_message key which duplicates the event."""
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging():
    """Configure structlog for the application.

    In production (LOG_JSON_FORMAT=True): JSON output to stderr
    In development (LOG_JSON_FORMAT=False): Pretty colored console output
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.ExtraAdder(),
        drop_color_message_key,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_JSON_FORMAT:
        # Production: JSON to stderr
        renderer = structlog.processors.JSONRenderer()
        shared_processors.append(structlog.processors.format_exc_info)
    else:
        # Development: pretty console output
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Quiet noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

**Request logging middleware:**
```python
# backend/app/middleware/logging.py - NEW FILE
import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from asgi_correlation_id import correlation_id

logger = structlog.stdlib.get_logger("access")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=correlation_id.get() or "",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request_failed",
                duration_ms=round(duration_ms, 2),
                error=str(exc),
                exc_info=True,
            )
            raise
```

**Usage - replacing print statements:**
```python
# BEFORE (current codebase)
print(f"[WARNING] Model files not found at {settings.MODEL_DIR}. Run training first.")
print(f"OCR Error: {e}")

# AFTER (structured logging)
import structlog
logger = structlog.stdlib.get_logger()

logger.warning("model_files_not_found", model_dir=settings.MODEL_DIR, hint="Run training first")
logger.error("ocr_failed", error=str(e), exc_info=True)
```

**JSON output example:**
```json
{"event": "request_completed", "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "method": "POST", "path": "/api/auth/login", "client_ip": "192.168.1.100", "status_code": 200, "duration_ms": 45.23, "level": "info", "timestamp": "2026-02-17T10:30:45.123456Z", "logger": "access"}
```

### Pattern 6: Alembic Migration Setup (INFR-01)

**What:** Initialize Alembic, create an initial migration capturing the existing schema, remove `create_all()` from main.py.

**Why:** `Base.metadata.create_all()` has no concept of schema evolution. It can only create tables that don't exist; it cannot alter existing tables, add columns, rename columns, or migrate data. Alembic provides versioned, reversible migrations.

**Step-by-step migration from create_all to Alembic:**

1. **Initialize Alembic in the backend directory:**
```bash
cd backend
alembic init alembic
```

2. **Configure alembic.ini:**
```ini
# alembic.ini
[alembic]
script_location = alembic

# Use env var for database URL (overridden in env.py)
sqlalchemy.url = postgresql://localhost/smart_docs
```

3. **Configure env.py to use app's settings and models:**
```python
# backend/alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your app's settings and models
from app.config import settings
from app.database import Base

# Import ALL models so they register with Base.metadata
from app.models.user import User
from app.models.document import Document
from app.models.refresh_token import RefreshToken  # New model

config = context.config

# Override sqlalchemy.url with app's DATABASE_URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

4. **Create initial migration (captures existing schema as baseline):**
```bash
alembic revision --autogenerate -m "initial schema - users, documents tables"
```

5. **For existing databases, stamp instead of running upgrade:**
```bash
# On a database that already has tables created by create_all():
alembic stamp head
# This marks the database as "at the latest migration" without running any SQL.
# Future autogenerate will only detect changes from this point forward.
```

6. **For fresh databases, run the migration:**
```bash
alembic upgrade head
```

7. **Remove create_all from main.py:**
```python
# backend/app/main.py - REMOVE THIS LINE
# Base.metadata.create_all(bind=engine)  # DELETE
```

**IMPORTANT: The stamp-vs-upgrade distinction is critical.** If you run `alembic upgrade head` on a database where `create_all()` already ran, Alembic will try to create tables that already exist and fail. Use `alembic stamp head` for existing databases.

### Pattern 7: CORS Fix (Part of SEC-01)

**Current state (INSECURE):**
```python
allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"]
```

The wildcard `"*"` in the origins list combined with `allow_credentials=True` is a security violation. When credentials are allowed, the browser will NOT honor `"*"` -- it requires explicit origins. However, some CORS implementations may behave unexpectedly.

**Target state:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # From environment variable
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
```

With `ALLOWED_ORIGINS` set via env var: `ALLOWED_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]` in development, `ALLOWED_ORIGINS=["https://yourdomain.com"]` in production.

### Anti-Patterns to Avoid

- **JWT refresh tokens instead of opaque tokens:** JWT refresh tokens cannot be instantly revoked, leak payload data, and add complexity. Use opaque random strings stored in DB.
- **Storing refresh tokens in localStorage:** Vulnerable to XSS. Use httpOnly cookies or at minimum secure cookies. The current implementation uses `js-cookie` which sets non-httpOnly cookies. For Phase 1, continue with cookies but add `secure` and `sameSite` attributes. True httpOnly requires backend set-cookie headers (Phase 2 improvement).
- **Rate limiting without Redis backend:** In-memory rate limiting doesn't work across multiple workers/processes. Always use Redis backend since it's already available.
- **HSTS in development:** Enabling HSTS on localhost causes browsers to permanently refuse HTTP for that origin. Only enable behind a `DEBUG` check.
- **Running Alembic autogenerate without importing all models:** Alembic only detects models that are imported and registered with `Base.metadata`. Forgetting to import a model in `env.py` causes Alembic to generate a `DROP TABLE` migration for that table.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting | Custom middleware counting requests | slowapi + Redis | Edge cases: distributed counting, race conditions, multiple time windows, header standards |
| Request ID generation | Custom UUID middleware | asgi-correlation-id | Handles header propagation, ID format validation, works across ASGI lifecycle |
| Structured logging | Custom JSON formatter | structlog | Context propagation, processor chains, async-safe contextvars, stdlib integration |
| DB migrations | Manual SQL scripts or create_all() | Alembic | Dependency tracking, autogenerate, reversibility, team collaboration, deployment automation |
| Environment config validation | Custom startup checks | pydantic-settings (already used) | Type coercion, nested models, multiple sources, .env parsing, built-in validation |
| Cryptographic random tokens | `uuid.uuid4()` for refresh tokens | `secrets.token_urlsafe(64)` | `secrets` module is cryptographically secure; `uuid4` uses system entropy but `secrets` is explicitly designed for security tokens |

**Key insight:** Every item above looks like "just 20 lines of code" but hides edge cases (distributed systems, race conditions, standards compliance, async safety) that existing solutions handle correctly.

## Common Pitfalls

### Pitfall 1: Forgetting Request Parameter in Rate-Limited Endpoints

**What goes wrong:** slowapi raises `TypeError: missing 'request' parameter` at runtime.
**Why it happens:** slowapi needs `request: Request` to extract client IP for rate limiting.
**How to avoid:** Every `@limiter.limit()` decorated function MUST have `request: Request` as a parameter, even if the endpoint doesn't otherwise need it.
**Warning signs:** Works fine without rate limiting, breaks after adding decorator.

### Pitfall 2: Decorator Order for slowapi

**What goes wrong:** Rate limiting silently doesn't apply.
**Why it happens:** The route decorator must be ABOVE the limiter decorator.
**How to avoid:** Always: `@router.post("/path")` then `@limiter.limit("5/minute")` then `async def endpoint(request: Request, ...)`.
**Warning signs:** No 429 responses even under heavy load.

### Pitfall 3: Missing Model Imports in Alembic env.py

**What goes wrong:** `alembic revision --autogenerate` generates `DROP TABLE` operations for existing tables.
**Why it happens:** Alembic compares database state against `target_metadata`. If a model isn't imported, its table isn't in metadata, so Alembic thinks it should be dropped.
**How to avoid:** Import every model file in `env.py` before setting `target_metadata = Base.metadata`. Add a comment block listing all models.
**Warning signs:** Autogenerate shows unexpected DROP TABLE or empty upgrades.

### Pitfall 4: Running alembic upgrade on Database Created by create_all()

**What goes wrong:** Migration fails with "relation already exists" errors.
**Why it happens:** `create_all()` already made the tables. The initial Alembic migration tries to create them again.
**How to avoid:** Use `alembic stamp head` on existing databases. Only use `alembic upgrade head` on fresh databases.
**Warning signs:** "psycopg2.errors.DuplicateTable" errors.

### Pitfall 5: Simultaneous Refresh Token Requests

**What goes wrong:** Multiple concurrent API calls get 401, all try to refresh, second refresh fails because first already rotated the token.
**Why it happens:** Without request queuing, N failed requests = N refresh attempts. After the first rotates the token, subsequent attempts use the now-revoked old token.
**How to avoid:** The frontend axios interceptor MUST implement a queue pattern (shown above) that blocks concurrent refresh attempts and replays queued requests with the new token.
**Warning signs:** Users randomly get logged out, especially on pages that make multiple API calls on load.

### Pitfall 6: structlog Context Leaking Between Requests

**What goes wrong:** One request's context data (user_id, request_id) appears in another request's logs.
**Why it happens:** structlog's context variables persist in thread/async context if not cleared.
**How to avoid:** Call `structlog.contextvars.clear_contextvars()` at the START of every request in the logging middleware.
**Warning signs:** Log entries showing wrong request IDs or user IDs.

### Pitfall 7: HSTS on Development (localhost)

**What goes wrong:** Browser permanently redirects `http://localhost` to `https://localhost`, breaking local development.
**Why it happens:** HSTS header instructs browser to only use HTTPS for the domain, and this persists in browser storage.
**How to avoid:** Only add HSTS header when `settings.DEBUG is False`.
**Warning signs:** "This site can't provide a secure connection" errors on localhost after testing.

## Code Examples

### Complete main.py with All Middleware (Verified Pattern)

```python
# backend/app/main.py - COMPLETE TARGET STATE
"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from asgi_correlation_id import CorrelationIdMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.utils.logging import setup_logging
from app.utils.rate_limiter import limiter
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import auth, documents

# Configure structured logging BEFORE anything else
setup_logging()

# NOTE: Base.metadata.create_all(bind=engine) REMOVED - use Alembic

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered Smart Document Management System",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware (order matters! Last added = first executed)
# 1. CORS (outermost - must handle preflight before anything else)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# 2. Security headers
app.add_middleware(SecurityHeadersMiddleware)

# 3. Request logging (logs every request with timing)
app.add_middleware(RequestLoggingMiddleware)

# 4. Correlation ID (innermost - generates request ID first)
app.add_middleware(CorrelationIdMiddleware)

# Mount static uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(auth.router)
app.include_router(documents.router)

@app.get("/", tags=["Root"])
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}

@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}
```

**Middleware execution order note:** Starlette processes middleware in reverse registration order. The last `add_middleware` call wraps the innermost layer. So `CorrelationIdMiddleware` runs first (generates ID), then `RequestLoggingMiddleware` (binds ID to logs), then `SecurityHeadersMiddleware` (adds headers), then `CORSMiddleware` (handles CORS). This is the correct order.

### Complete .env.example (Updated)

```env
# Smart Document Management System - Environment Variables
# Copy this file to .env and update the values.
# Generate SECRET_KEY with: python -c "import secrets; print(secrets.token_urlsafe(64))"

# === REQUIRED (app will not start without these) ===
SECRET_KEY=
DATABASE_URL=postgresql://postgres:your-password-here@localhost:5432/smart_docs

# === Application ===
DEBUG=true
APP_NAME=Smart Document Management System

# === CORS ===
# JSON array of allowed origins. In production, use your actual domain.
ALLOWED_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]

# === JWT ===
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# === Rate Limiting ===
RATE_LIMIT_AUTH=5/minute
RATE_LIMIT_UPLOAD=10/minute
RATE_LIMIT_DEFAULT=60/minute

# === Logging ===
LOG_LEVEL=INFO
LOG_JSON_FORMAT=false

# === Database (for docker-compose) ===
POSTGRES_DB=smart_docs
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-strong-postgres-password

# === Redis & Celery ===
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# === File Storage ===
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=50

# === AWS S3 (optional) ===
USE_S3=false
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
S3_BUCKET_NAME=smart-docs-bucket

# === ML Model ===
MODEL_DIR=./models
ML_CONFIDENCE_THRESHOLD=0.3

# === Tesseract OCR ===
TESSERACT_CMD=
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-jose for JWT | PyJWT (already in use) | python-jose unmaintained since 2022 | No change needed, project already uses PyJWT |
| print() logging | structlog JSON logging | Industry standard since ~2020 | Replace all print() calls with structlog loggers |
| create_all() | Alembic migrations | Standard practice for any production SQLAlchemy app | Must initialize Alembic and stamp existing database |
| Long-lived JWTs (24h) | Short access (30min) + refresh tokens | OWASP best practice | Requires new database table, new endpoints, frontend interceptor |
| Hardcoded config | Environment variables with validation | 12-factor app methodology | Remove all defaults for secrets, add validators |

**Deprecated/outdated patterns to avoid:**
- `python-jose`: Last release 2022, unmaintained. Use PyJWT.
- `fastapi-jwt-auth`: Archived/unmaintained. Roll refresh token logic with PyJWT directly (it's straightforward).
- `secure` library for security headers: Works but adds dependency for ~20 lines of code. Custom middleware is simpler.
- `flask-limiter` patterns: slowapi IS flask-limiter adapted for Starlette/FastAPI. Don't try to use flask-limiter directly.

## Open Questions

1. **Cookie Security for Refresh Tokens**
   - What we know: The frontend currently uses `js-cookie` (non-httpOnly cookies). Ideally, refresh tokens should be in httpOnly cookies set by the backend.
   - What's unclear: Changing to httpOnly set-cookie headers requires backend CORS changes and cookie domain configuration that depends on deployment topology.
   - Recommendation: For Phase 1, use `js-cookie` with `secure: true` and `sameSite: "Strict"` flags. Document httpOnly cookies as a Phase 2 improvement. This is a pragmatic trade-off: the refresh token is still in a cookie (accessible via JS), but rotation + reuse detection limits the damage if stolen.

2. **Alembic and Existing Production Data**
   - What we know: The app currently uses `create_all()`. If there's an existing database with user data, Alembic must be stamped (not upgraded) to avoid "table already exists" errors.
   - What's unclear: Whether there are multiple environments (dev, staging, prod) with different schema states.
   - Recommendation: The plan should include instructions for BOTH fresh setup (`alembic upgrade head`) and existing database migration (`alembic stamp head`). Document this clearly.

3. **Python Version Compatibility**
   - What we know: Alembic 1.18.4 requires Python >=3.10. The current requirements.txt doesn't specify a Python version.
   - What's unclear: What Python version the project currently runs.
   - Recommendation: Verify Python version. If <3.10, use Alembic 1.13.x (already in requirements.txt) which supports Python 3.7+. If >=3.10, upgrade to 1.18.4.

4. **Refresh Token Cleanup**
   - What we know: Expired and revoked refresh tokens accumulate in the database over time.
   - What's unclear: Whether a cleanup job should be part of Phase 1 or deferred.
   - Recommendation: Add a simple SQL cleanup (DELETE WHERE expires_at < NOW() OR is_revoked = true) as a periodic Celery task. Can be Phase 2 if scope is tight, but the query is trivial.

## Sources

### Primary (HIGH confidence)

- **Context7 /fastapi/fastapi** - CORS middleware configuration, custom middleware patterns
- **Context7 /laurents/slowapi** - Rate limiter initialization, Redis backend, FastAPI integration, decorator patterns
- **Context7 /hynek/structlog** - JSON logging configuration, contextvars integration, processor chains, Flask/FastAPI patterns
- **PyPI: slowapi 0.1.9** (verified Feb 2024 release) - https://pypi.org/project/slowapi/
- **PyPI: structlog 25.5.0** (verified Oct 2025 release) - https://pypi.org/project/structlog/
- **PyPI: alembic 1.18.4** (verified Feb 2026 release) - https://pypi.org/project/alembic/
- **PyPI: PyJWT 2.11.0** (verified Jan 2026 release) - https://pyjwt.readthedocs.io/
- **PyPI: pydantic-settings 2.13.0** (verified Feb 2026 release) - https://pypi.org/project/pydantic-settings/
- **Alembic official tutorial** - https://alembic.sqlalchemy.org/en/latest/tutorial.html
- **pydantic-settings documentation** - https://docs.pydantic.dev/latest/concepts/pydantic_settings/

### Secondary (MEDIUM confidence)

- **FastAPI + structlog integration blog** (wazaari.dev) - Complete middleware + config pattern verified against Context7 structlog docs
- **structlog + FastAPI + uvicorn gist** (nymous/GitHub) - Confirmed shared processor + renderer pattern
- **asgi-correlation-id** (snok/GitHub) - Request ID middleware for ASGI, verified integration pattern with structlog
- **Secweb PyPI** - Security headers library (noted but NOT recommended; custom middleware preferred)
- **JWT refresh token patterns** - Multiple sources (Medium, freeCodeCamp, hanchon.live) converge on same pattern: opaque tokens + DB storage + rotation

### Tertiary (LOW confidence)

- **axios-auth-refresh npm package** - Alternative to custom interceptor; not recommended (custom interceptor gives more control)
- **Docker secrets for production** - Docker official docs on /run/secrets pattern. Noted for future but not required for Phase 1.

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All libraries verified via PyPI with exact versions and release dates |
| Environment Config (SEC-01) | HIGH | pydantic-settings behavior verified via official docs; field validation is core feature |
| JWT Refresh Tokens (SEC-02) | HIGH | Pattern verified across multiple authoritative sources; PyJWT API verified via Context7 |
| Rate Limiting (SEC-03) | HIGH | slowapi configuration verified via Context7 with full code examples |
| Security Headers (SEC-04) | HIGH | Standard HTTP headers; well-documented; custom middleware is trivial |
| Structured Logging (SEC-05) | HIGH | structlog configuration verified via Context7; FastAPI integration pattern from multiple sources |
| Alembic Migrations (INFR-01) | HIGH | Official Alembic tutorial + autogenerate docs verified; stamp pattern documented |
| Frontend Token Refresh | MEDIUM | Axios interceptor queue pattern from community sources; well-established pattern but not from official docs |

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (30 days - stable ecosystem, no breaking changes expected)
