---
phase: 01-foundation-security-hardening
plan: 03
subsystem: backend-middleware
tags: [rate-limiting, security-headers, structlog, middleware, correlation-id]

dependency-graph:
  requires: ["01-01"]
  provides:
    - "SecurityHeadersMiddleware for all HTTP responses"
    - "RequestLoggingMiddleware with structured JSON logging"
    - "Rate-limited upload endpoint (10/minute)"
    - "Correlation ID propagation through request lifecycle"
    - "Zero print() statements in backend codebase"
  affects: ["01-04", "02-*"]

tech-stack:
  added:
    - "structlog (structured logging with JSON/console renderers)"
    - "asgi-correlation-id (request ID generation and propagation)"
  patterns:
    - "BaseHTTPMiddleware subclasses for cross-cutting concerns"
    - "structlog contextvars for per-request log binding"
    - "slowapi @limiter.limit decorator for per-endpoint rate limits"

file-tracking:
  key-files:
    created:
      - "backend/app/utils/logging.py"
      - "backend/app/middleware/__init__.py"
      - "backend/app/middleware/security_headers.py"
      - "backend/app/middleware/logging.py"
    modified:
      - "backend/app/main.py"
      - "backend/app/routers/documents.py"
      - "backend/app/ml/ocr.py"
      - "backend/app/ml/pdf_extractor.py"
      - "backend/app/ml/classifier.py"
      - "backend/app/ml/train.py"

decisions:
  - id: "01-03-01"
    decision: "HSTS max-age set to 2 years (63072000s) with includeSubDomains and preload"
    context: "Production-grade HSTS policy; only served when DEBUG=False"
  - id: "01-03-02"
    decision: "CSP allows 'unsafe-inline' for style-src only"
    context: "Required for inline styles from UI frameworks; script-src remains strict 'self'"
  - id: "01-03-03"
    decision: "Middleware order: CORS > SecurityHeaders > RequestLogging > CorrelationId"
    context: "CorrelationId must execute first (innermost) to generate request_id before logging"
  - id: "01-03-04"
    decision: "docs_url and redoc_url disabled when DEBUG=False"
    context: "API documentation should not be exposed in production"

metrics:
  duration: "~14min"
  completed: "2026-02-25"
---

# Phase 1 Plan 3: Rate Limiting, Security Headers & Structured Logging Summary

Middleware stack with rate limiting on uploads (10/min via slowapi), security headers on all responses (X-Frame-Options, X-Content-Type-Options, CSP, HSTS in prod), and structured JSON logging via structlog with per-request correlation IDs. All 30+ print() statements across 5 ML/service files replaced with structured logger calls.

## What Was Done

### Task 1: Structured Logging & Middleware Files (c7af997)

**Created `backend/app/utils/logging.py`:**
- `setup_logging()` configures structlog with shared processors: contextvars merge, logger name, log level, timestamps (ISO/UTC), stack info rendering
- JSON renderer with `format_exc_info` for production (`LOG_JSON_FORMAT=True`)
- Console renderer with colors for development
- ProcessorFormatter wraps structlog for stdlib logging compatibility
- Quiets noisy loggers: `uvicorn.access` and `sqlalchemy.engine` set to WARNING

**Created `backend/app/middleware/security_headers.py`:**
- `SecurityHeadersMiddleware(BaseHTTPMiddleware)` adds to every response:
  - `X-Frame-Options: DENY` (clickjacking protection)
  - `X-Content-Type-Options: nosniff` (MIME sniffing prevention)
  - `X-XSS-Protection: 1; mode=block` (legacy browser XSS filter)
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - `Content-Security-Policy` with strict default-src, frame-ancestors none
  - `Strict-Transport-Security` (HSTS) only when `DEBUG=False`

**Created `backend/app/middleware/logging.py`:**
- `RequestLoggingMiddleware(BaseHTTPMiddleware)` logs every request:
  - Clears and binds contextvars: `request_id`, `method`, `path`, `client_ip`
  - Times requests with `perf_counter`
  - Logs `request_completed` with `status_code` and `duration_ms`
  - Logs `request_failed` with `exc_info=True` on exceptions

### Task 2: Middleware Wiring & Print Replacement (fe1e9ef)

**Updated `backend/app/main.py`:**
- `setup_logging()` called before FastAPI app creation
- Full middleware stack in correct order (CORS, SecurityHeaders, RequestLogging, CorrelationId)
- `app.state.limiter = limiter` and exception handler wired
- `docs_url` and `redoc_url` conditional on `DEBUG` flag
- Kept `Base.metadata.create_all` for Plan 01-04 to replace

**Updated `backend/app/routers/documents.py`:**
- `@limiter.limit(settings.RATE_LIMIT_UPLOAD)` on upload endpoint
- `request: Request` added as first parameter (required by slowapi)

**Replaced print() statements (5 files):**
- `ocr.py`: 2 print() -> `logger.error("ocr_extraction_failed")`, `logger.error("ocr_pil_extraction_failed")`
- `pdf_extractor.py`: 1 print() -> `logger.error("pdf_extraction_failed")`
- `classifier.py`: 1 print() -> `logger.warning("model_files_not_found")`
- `train.py`: 30+ print() -> structured logger calls with step tracking, model metrics, timing

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| 01-03-01 | HSTS max-age 2 years with preload | Industry-standard production HSTS |
| 01-03-02 | CSP unsafe-inline for style-src only | UI framework compatibility; scripts remain strict |
| 01-03-03 | Middleware order: CORS > Security > Logging > CorrelationId | CorrelationId innermost to generate ID before logging binds it |
| 01-03-04 | Disable Swagger/ReDoc in production | API docs should not be publicly accessible |

## Verification Results

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Rate limiter wired into app state | PASS | `app.state.limiter = limiter` in main.py |
| Upload rate-limited at 10/min | PASS | `@limiter.limit(settings.RATE_LIMIT_UPLOAD)` on upload endpoint |
| X-Frame-Options header | PASS | SecurityHeadersMiddleware adds `DENY` |
| X-Content-Type-Options header | PASS | SecurityHeadersMiddleware adds `nosniff` |
| Content-Security-Policy header | PASS | Full CSP with default-src, script-src, frame-ancestors |
| HSTS only when DEBUG=False | PASS | Conditional on `not settings.DEBUG` |
| Structured JSON logging | PASS | structlog with JSONRenderer when LOG_JSON_FORMAT=True |
| request_id in log entries | PASS | `correlation_id.get()` bound via contextvars |
| Zero print() statements | PASS | `grep -r "^\s*print(" backend/app/` returns no matches |

## Deviations from Plan

None -- plan executed exactly as written. The main.py middleware wiring was found to already be committed as part of the 01-02 plan execution (which ran concurrently), so only the ML file changes and documents.py rate limiting needed separate commits.

## Next Phase Readiness

- All middleware infrastructure is in place for future endpoints
- structlog is configured globally; any new module just needs `logger = structlog.stdlib.get_logger()`
- Rate limiting decorator pattern established for future endpoints
- Plan 01-04 (Alembic migrations) can proceed -- `Base.metadata.create_all` is preserved with a comment indicating replacement
