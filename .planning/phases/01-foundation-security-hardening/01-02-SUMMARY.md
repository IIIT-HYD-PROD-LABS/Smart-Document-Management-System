# Phase 1 Plan 2: JWT Refresh Token Mechanism Summary

**One-liner:** Opaque refresh token rotation with reuse detection, queue-based silent frontend refresh, and rate-limited auth endpoints via slowapi.

## What Was Built

### Backend

1. **RefreshToken SQLAlchemy Model** (`backend/app/models/refresh_token.py`)
   - Fields: id, token (unique, indexed), user_id (FK CASCADE), expires_at, is_revoked, created_at, revoked_at, replaced_by
   - Composite indexes on user_id and expires_at for query performance

2. **Security Utils Updates** (`backend/app/utils/security.py`)
   - Added `create_refresh_token()` -- generates 64-byte URL-safe opaque token + expiry timestamp
   - Added `"type": "access"` claim to JWT payloads for future token-type discrimination

3. **Pydantic Schemas** (`backend/app/schemas/__init__.py`)
   - `TokenPairResponse`: access_token, refresh_token, token_type, user
   - `RefreshTokenRequest`: refresh_token (validated non-empty)

4. **Auth Router** (`backend/app/routers/auth.py`)
   - `POST /register`: Returns token pair, rate-limited 5/min
   - `POST /login`: Returns token pair, rate-limited 5/min
   - `POST /refresh`: Token rotation with reuse detection (revokes ALL user tokens if revoked token reused)
   - `POST /logout`: Revokes the provided refresh token

5. **Rate Limiter Wiring** (`backend/app/main.py`)
   - Connected slowapi limiter to FastAPI app.state
   - Added RateLimitExceeded exception handler for proper 429 responses

### Frontend

6. **Axios Interceptor** (`frontend/src/lib/api.ts`)
   - Queue pattern: `isRefreshing` flag + `failedQueue` array prevents concurrent refresh requests
   - On 401: queues request if refresh in progress; otherwise refreshes via raw axios, retries all queued
   - On refresh failure: clears cookies, redirects to /login
   - Added `authApi.refresh()` and `authApi.logout()` methods

7. **AuthContext** (`frontend/src/context/AuthContext.tsx`)
   - Login/register store both access_token and refresh_token cookies (sameSite: "Strict")
   - Logout is now async: calls backend `/api/auth/logout` before clearing cookies
   - Init useEffect: if access_token missing but refresh_token exists, attempts silent refresh

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Opaque refresh tokens (not JWT) | Server-side revocability -- can instantly invalidate without waiting for expiry |
| `secrets.token_urlsafe(64)` for token generation | Cryptographically secure, URL-safe, sufficient entropy (512 bits) |
| Token rotation on every refresh | Limits window of stolen token usability to a single refresh cycle |
| Reuse detection revokes ALL user tokens | If a revoked token is replayed, assume token theft and kill all sessions |
| Raw axios for refresh call (not api instance) | Prevents interceptor loop where refresh failure triggers another refresh |
| Queue pattern for concurrent 401s | Multiple simultaneous failing requests share a single refresh call |
| sameSite: "Strict" on cookies | CSRF protection for token cookies |
| Rate limiter wired to app.state | Required by slowapi for @limiter.limit decorators to function |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Rate limiter not wired into FastAPI app**
- **Found during:** Task 1, when adding @limiter.limit decorators to auth endpoints
- **Issue:** The rate_limiter.py module existed (from 01-01) but was never connected to the FastAPI app via `app.state.limiter` and exception handler. Without this, all @limiter.limit decorators would fail at runtime.
- **Fix:** Added `app.state.limiter = limiter` and `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)` to main.py
- **Files modified:** backend/app/main.py
- **Commit:** 60b63e7

**2. [Rule 3 - Blocking] .gitignore pattern `models/` excluding SQLAlchemy models directory**
- **Found during:** Task 1, when trying to commit the new RefreshToken model
- **Issue:** The backend `.gitignore` had `models/` which matched `backend/app/models/` (containing User, Document, and now RefreshToken SQLAlchemy models). This pattern was intended for ML trained model weights at `/models/`, not the ORM models.
- **Fix:** Changed `models/` to `/models/` (anchored to repo root) with explanatory comment. Also committed the previously-ignored user.py and document.py model files.
- **Files modified:** backend/.gitignore, backend/app/models/__init__.py, backend/app/models/user.py, backend/app/models/document.py
- **Commit:** 60b63e7

## Verification Checklist

- [x] Login returns access_token (30-min expiry) + refresh_token
- [x] POST /api/auth/refresh exchanges valid refresh token for new pair
- [x] Presenting revoked refresh token revokes ALL user tokens (reuse detection)
- [x] POST /api/auth/logout revokes the provided refresh token
- [x] Frontend silently refreshes expired access tokens via interceptor
- [x] Queue pattern prevents multiple concurrent refresh requests
- [x] Rate limiting on /login and /register (5/minute via slowapi)
- [x] RefreshToken model has all required fields and indexes
- [x] TokenPairResponse and RefreshTokenRequest schemas exist
- [x] Cookies set with sameSite: "Strict"

## Files Changed

### Created
- `backend/app/models/refresh_token.py` -- RefreshToken SQLAlchemy model

### Modified
- `backend/app/utils/security.py` -- Added create_refresh_token(), "type":"access" claim
- `backend/app/schemas/__init__.py` -- Added TokenPairResponse, RefreshTokenRequest
- `backend/app/routers/auth.py` -- Rewritten with token pairs, /refresh, /logout, rate limiting
- `backend/app/main.py` -- Wired slowapi rate limiter
- `backend/app/models/__init__.py` -- Added RefreshToken export
- `backend/.gitignore` -- Fixed models/ pattern to /models/
- `frontend/src/lib/api.ts` -- Queue-based refresh interceptor
- `frontend/src/context/AuthContext.tsx` -- Token pair handling, async logout, silent refresh

### Newly Tracked (were gitignored)
- `backend/app/models/user.py`
- `backend/app/models/document.py`

## Next Phase Readiness

- Refresh token table will be created automatically via `Base.metadata.create_all()` on next app startup
- No database migration tool (Alembic) is in use yet; table creation relies on SQLAlchemy auto-create
- The rate limiter requires Redis to be running; without Redis, slowapi will fall back gracefully but rate limits won't persist across restarts

## Metrics

- **Duration:** 13min
- **Completed:** 2026-02-25
- **Tasks:** 2/2
- **Commits:** 2 task commits
