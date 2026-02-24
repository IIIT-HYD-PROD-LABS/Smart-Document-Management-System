---
phase: 01-foundation-security-hardening
verified: 2026-02-25T00:00:00Z
status: gaps_found
score: 3/5 must-haves verified
gaps:
  - truth: "Application starts with no hardcoded secrets; app refuses to start if critical env vars missing"
    status: partial
    reason: >
      Validator code correctly blocks known-insecure keys and enforces length >= 32.
      However, backend/.env ships with SECRET_KEY set to a well-known 47-char placeholder
      that passes the length check and is NOT in the insecure_values blocklist.
      The .env is gitignored, but the on-disk file would let the app start with a compromised key.
    artifacts:
      - path: backend/.env
        issue: SECRET_KEY is a well-known placeholder (47 chars) that passes the length validator but is publicly known
      - path: backend/app/config.py
        issue: insecure_values set does not include the specific placeholder used in the .env
    missing:
      - Add the specific placeholder to insecure_values in config.py
      - Replace the placeholder SECRET_KEY in backend/.env with a truly random value
  - truth: "User sessions expire after 30 minutes; silent refresh via refresh tokens"
    status: partial
    reason: >
      Refresh token mechanism and frontend interceptor are fully and correctly implemented.
      However, backend/.env overrides ACCESS_TOKEN_EXPIRE_MINUTES to 1440 (24 hours)
      instead of the required 30 minutes. Sessions last 24 hours.
    artifacts:
      - path: backend/.env
        issue: ACCESS_TOKEN_EXPIRE_MINUTES=1440 overrides the 30-minute code default
    missing:
      - Change ACCESS_TOKEN_EXPIRE_MINUTES to 30 in backend/.env
---

# Phase 1 Verification: Foundation & Security Hardening

**Phase Goal:** The application runs on a secure, properly configured foundation with no hardcoded secrets, proper token management, and structured observability
**Verified:** 2026-02-25
**Status:** gaps_found
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No hardcoded secrets; app refuses to start if critical env vars missing | PARTIAL | Validator enforces length >= 32 and blocks known values, but actual .env has a well-known placeholder bypassing the blocklist |
| 2 | Sessions expire after 30 minutes; silent refresh via refresh tokens | PARTIAL | Refresh mechanism fully implemented; frontend interceptor correct -- but backend/.env sets ACCESS_TOKEN_EXPIRE_MINUTES=1440 (24h) |
| 3 | Rate limiting on login and upload endpoints returning 429 | VERIFIED | slowapi limiter on /api/auth/login, /api/auth/register, /api/documents/upload; RateLimitExceeded handler wired in main.py |
| 4 | Security headers (HSTS, CSP, X-Frame-Options) on all responses | VERIFIED | SecurityHeadersMiddleware sets X-Frame-Options, CSP, HSTS (when DEBUG=False), X-Content-Type-Options, Referrer-Policy, Permissions-Policy |
| 5 | Structured JSON logs with request IDs | VERIFIED | structlog with JSONRenderer; CorrelationIdMiddleware injects ID; RequestLoggingMiddleware binds request_id; zero print() in app code |

**Score:** 3/5 truths fully verified (2 partial gaps)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| backend/app/config.py | Pydantic Settings with no defaults for secrets | VERIFIED | DATABASE_URL and SECRET_KEY have no defaults; field_validator enforces strength |
| backend/.env.example | Template documenting required env vars | VERIFIED | Complete template; SECRET_KEY left blank as required |
| backend/.env | Actual env file with real secrets | PARTIAL | SECRET_KEY is a well-known placeholder passing the length check; ACCESS_TOKEN_EXPIRE_MINUTES=1440 |
| backend/app/utils/security.py | JWT creation with configurable expiry; opaque refresh token generation | VERIFIED | create_access_token uses settings.ACCESS_TOKEN_EXPIRE_MINUTES; create_refresh_token uses secrets.token_urlsafe(64) |
| backend/app/models/refresh_token.py | RefreshToken DB model with revocation fields | VERIFIED | Full model: is_revoked, revoked_at, replaced_by, expires_at, indexes on user_id and expires_at |
| backend/app/routers/auth.py | /refresh endpoint with rotation and reuse detection | VERIFIED | Reuse detection revokes ALL user tokens on reuse attempt; token rotation; expiry check all implemented |
| frontend/src/lib/api.ts | Axios interceptor for silent token refresh | VERIFIED | Queue pattern for concurrent 401s; refresh-on-401 with retry of original request; redirect on refresh failure |
| backend/app/utils/rate_limiter.py | slowapi Limiter with Redis backend | VERIFIED | Limiter with storage_uri=settings.REDIS_URL and default_limits from settings |
| backend/app/middleware/security_headers.py | Middleware adding HSTS, CSP, X-Frame-Options | VERIFIED | All required headers present; HSTS conditional on DEBUG=False |
| backend/app/utils/logging.py | structlog setup with JSON renderer | VERIFIED | JSONRenderer when LOG_JSON_FORMAT=True; configures root logger; no print() statements found |
| backend/app/middleware/logging.py | Request logging middleware binding request_id | VERIFIED | Binds request_id from correlation_id.get(), method, path, client_ip; logs duration_ms |
| backend/alembic/ | Alembic migration framework replacing create_all | VERIFIED | Initial migration creates all 3 tables; env.py uses settings.DATABASE_URL; main.py has NO create_all call |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| config.py Settings | Startup failure on missing vars | Pydantic fields with no defaults | VERIFIED | DATABASE_URL and SECRET_KEY have no defaults; pydantic raises ValidationError on startup if absent |
| config.py validator | Insecure key rejection | insecure_values set + length >= 32 check | PARTIAL | Known values blocked; length enforced; BUT specific .env placeholder is NOT in insecure_values set |
| auth.py /refresh | Token rotation + reuse detection | RefreshToken model + DB queries | VERIFIED | Revokes old token; issues new pair; revokes ALL user tokens on detected reuse |
| api.ts interceptor | Silent refresh on 401 | axios response interceptor + queue | VERIFIED | Intercepts 401; queues concurrent requests; refreshes once; retries all queued with new token |
| limiter | 429 on threshold breach | slowapi + Redis + exception handler | VERIFIED | @limiter.limit on login, register, upload; RateLimitExceeded handler in main.py |
| SecurityHeadersMiddleware | Headers on all responses | Starlette BaseHTTPMiddleware | VERIFIED | Middleware mutates response headers after call_next on every request |
| CorrelationIdMiddleware | Request ID generation | asgi-correlation-id library | VERIFIED | Imported and registered in middleware stack in main.py |
| RequestLoggingMiddleware | request_id in every log line | structlog contextvars + correlation_id | VERIFIED | Binds correlation_id.get() as request_id; merge_contextvars propagates to all log lines |
| alembic/env.py | DB URL from settings at migration time | config.set_main_option(settings.DATABASE_URL) | VERIFIED | No hardcoded URL; fully dynamic from environment |

---

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| SEC-01: No hardcoded SECRET_KEY; no defaults in code | PARTIAL | Validator code correct; .env has a placeholder key slipping past the blocklist |
| SEC-02: 30-minute JWT expiry with refresh token mechanism | PARTIAL | Refresh mechanism fully implemented; .env overrides expiry to 1440 minutes (24h) |
| SEC-03: Rate limiting on auth and upload endpoints | SATISFIED | limiter on /login, /register, /upload with 429 via RateLimitExceeded handler |
| SEC-04: Security headers (HSTS, CSP, X-Frame-Options) | SATISFIED | SecurityHeadersMiddleware injects all required headers on every response |
| SEC-05: Structured JSON logging; no print statements | SATISFIED | structlog with JSONRenderer; no print() calls in any app/ source file |
| INFR-01: Alembic migrations replace auto-create | SATISFIED | Alembic env.py, initial migration covering all 3 tables, main.py without create_all |

---

## Anti-Patterns Found

| File | Finding | Severity | Impact |
|------|---------|----------|--------|
| backend/.env | SECRET_KEY set to a well-known placeholder (47 chars, passes length check, NOT in blocklist) | BLOCKER | App starts with a compromised key; attacker knowing this value can forge any JWT |
| backend/.env | ACCESS_TOKEN_EXPIRE_MINUTES=1440 -- 24-hour token lifetime instead of 30 minutes | BLOCKER | Stolen access tokens remain valid 24x longer than the security policy requires |
| backend/app/config.py | insecure_values blocklist omits the specific placeholder used in .env | WARNING | The intended security gate is bypassed by this particular value |
| docker-compose.yml | POSTGRES_PASSWORD defaults to literal postgres if env var not set | WARNING | Trivially guessable database password if .env omits POSTGRES_PASSWORD |

---

## Human Verification Required

### 1. HSTS Header Presence in Browser

**Test:** Start the backend with DEBUG unset (defaults to False). Open browser dev tools Network tab, make any API request, inspect response headers.
**Expected:** Response includes Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
**Why human:** HSTS conditional on DEBUG=False can only be confirmed by observing actual response headers in a running environment.

### 2. Rate Limit 429 Response

**Test:** Send 6 rapid POST requests to /api/auth/login within one minute from the same IP address.
**Expected:** The 6th request returns HTTP 429 with a rate-limit error body.
**Why human:** Requires Redis running and reachable; cannot verify enforcement from static code inspection.

### 3. Silent Token Refresh Flow

**Test:** Log in, clear only the token cookie (leaving refresh_token intact), then navigate to any protected page.
**Expected:** Page loads without redirecting to /login -- frontend interceptor silently obtains a new access token.
**Why human:** Multi-step browser interaction depending on runtime cookie handling and the axios interceptor executing correctly.

---

## Gaps Summary

Two gaps block full goal achievement. Both are configuration-level fixes, not architectural problems.

**Gap 1 -- Insecure SECRET_KEY in backend/.env (SEC-01 PARTIAL)**

The code infrastructure for secret validation is correct: config.py declares SECRET_KEY with no default (app fails on startup if absent) and the field_validator enforces length >= 32 and blocks a set of known-bad values. However, backend/.env currently contains a well-known placeholder that is 47 characters (passes the length check) and is NOT in the insecure_values set. This placeholder is visible in project history and any attacker who has seen this project can use it to forge valid JWTs for any user.

Two fixes required:
1. Add the specific placeholder to insecure_values in backend/app/config.py (lines 76-81).
2. Replace the value in backend/.env with a real random key.

**Gap 2 -- Access Token Expiry is 24 Hours, Not 30 Minutes (SEC-02 PARTIAL)**

The refresh token mechanism, token rotation, reuse detection, and frontend silent-refresh interceptor are all fully and correctly implemented. The gap is purely configuration: backend/.env sets ACCESS_TOKEN_EXPIRE_MINUTES=1440, overriding the 30-minute code default. Access tokens stay valid for 24 hours. A stolen token gives an attacker a 24-hour window rather than the 30-minute window the security design requires.

One fix required: change ACCESS_TOKEN_EXPIRE_MINUTES=1440 to ACCESS_TOKEN_EXPIRE_MINUTES=30 in backend/.env.

---

_Verified: 2026-02-25_
_Verifier: Claude (gsd-verifier)_
