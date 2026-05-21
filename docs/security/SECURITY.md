# Security Policy

## Supported Versions

| Version      | Supported |
| ------------ | --------- |
| 1.0.x (current) | Yes   |

## Recent hardening (2026-05-21 audit sweep)

The latest end-to-end agent-team audit closed the following findings. See `docs/status/STATUS_REPORT.md` for the full session log + commit hashes.

| Severity | Finding | Fix location |
|---|---|---|
| CRITICAL | Cross-tenant email body access (IDOR). `GmailMessageLog` has no `client_id`; the route resolved the credential without checking that `cred.client_id == membership.client_id`. | `backend/app/email/routers/view_email.py:62`. |
| HIGH | BYOK `POST /ai/credentials/test` reflected the provider SDK exception string back to the caller. The Anthropic `AuthenticationError` can stringify the submitted key in its message. Now logs full exc server-side, returns a fixed user-facing string. | `backend/app/compliance/routers/ai.py` (`test_credential`). |
| HIGH | Phase 16 BYOK `ai_credentials` table was created without the Row Level Security bootstrap + GRANT pattern used on every other tenant table. Migration `0033_ai_credentials_rls` adds it, with `ENABLE / FORCE RLS` guarded behind the `app_runtime` role check so a fresh dev DB without that role is not left with FORCE-RLS-no-policies (zero-rows trap). | `backend/alembic/versions/0033_ai_credentials_rls.py`. |
| HIGH | NUL-byte 500 on `/api/documents/search?q=%00`. psycopg raised `ValueError: A string literal cannot contain NUL`; surfaced as a 10s 500. Now strips NUL and returns 400 when the query is empty after strip. | `backend/app/routers/documents.py`. |
| HIGH | Per-route rate limiting added to every BYOK AI endpoint (10 to 20 per minute) so a legitimate tenant member cannot exhaust the per-tenant Anthropic / Gemini budget. | `backend/app/compliance/routers/ai.py`. |
| HIGH | python-multipart 0.0.26 to 0.0.27 patches GHSA: unbounded multipart part headers DoS (Dependabot alert #81). | `backend/requirements.txt`. |
| HIGH | Next.js 15.5.15 to 15.5.18 (backport tag) clears the bulk of the open Dependabot advisories, including middleware auth bypass (GHSA-267c-6grr-h53f), cache poisoning (GHSA-3g8h-86w9-wvmq), and the App-Router CSP-nonce / `beforeInteractive` XSS pair. Stayed on the 15.5 line; major to 16.x deferred for a planned migration. | `frontend/package.json`, `frontend/package-lock.json`. |
| MEDIUM | Tenant-context checkin cleanup bare `except: pass` could return a connection to the pool with the prior request's `app.current_client_id` still set. Now logs the failure and invalidates the connection so the next checkout opens a fresh one. | `backend/app/compliance/middleware/tenant_context.py`. |
| MEDIUM | Gmail OAuth callback was reflecting the internal exception class name in the URL query string. Removed; the full traceback is logged server-side. | `backend/app/email/routers/oauth.py`. |
| MEDIUM | `FERNET_KEY` validator was length + isalnum heuristic that false-rejected padded keys and false-accepted Unicode alphanumerics. Now base64-decodes and checks for a 32-byte payload. | `backend/app/config.py`. |
| LOW | `audit_service` rollback failure was a bare `pass`; now `logger.exception("audit_rollback_failed")` so dashboards see it. `notice_service` transitions use `log_audit_event_strict` so dead-letter writes fire the ops-attention log. | `backend/app/services/audit_service.py`, `backend/app/compliance/services/notice_service.py`. |
| LOW | `bill_reminder_task` incremented `reminder_count` even on dispatch failure; after 3 failed dispatches the cool-down silently muted the bill. Only consume the budget on success. | `backend/app/email/tasks/bill_reminder_task.py`. |
| LOW | Dependabot churn: wildcard `dependency-name: "*"` major-version ignore on both pip and npm. 8 breaking-major PRs closed (Next 16, Tailwind 4, TS 6, starlette 1.0, xgboost 3, @types/node 25, zod 4, redis 7, framer-motion 12, react-day-picker 10, react-dropzone 15). | `.github/dependabot.yml`. |

Deferred (architectural, not auto-applied):
- `response_service.py` audit-after-commit pattern. Needs audit inside the same transaction as the business write.
- DOCX zip-bomb mitigation; needs a subprocess sandbox to bound decompressed XML size before python-docx parses it.
- Frontend BFF pattern to move JWTs out of non-HttpOnly cookies.

## Security Architecture

### Authentication

- JWT access tokens (HS256, 30-minute expiry)
- Opaque refresh tokens with rotation and reuse detection
- bcrypt password hashing (passlib)
- OAuth SSO: Google and Microsoft with CSRF state parameter
- Rate limiting: 5 requests/minute on auth endpoints
- `get_current_user` rejects accounts where `is_active=False` OR `deleted_at IS NOT NULL` — soft-deleted users cannot regain access even if a future admin re-flips `is_active`.

### Account Lifecycle

- **Admin user delete (`DELETE /api/admin/users/{id}`)** — guarded by `require_admin`, rate-limited 5/min. Performs soft-delete with PII anonymization rather than a hard `DELETE FROM users`.
- **Why soft-delete:** the `audit_logs` immutability trigger (migration 0014) raises EXCEPTION on any UPDATE or DELETE. A real cascade would fire `ON DELETE SET NULL` on `audit_logs.user_id` (an UPDATE), trip the trigger, and abort. Anonymizing the user row keeps `audit_logs` untouched and the audit chain forensically valid.
- **Anonymization fields:** `email` → `deleted-{id}-{epoch}@deleted.local`, `username` → `deleted_{id}_{epoch}`, `full_name`, `oauth_id`, `hashed_password` → NULL. Frees the unique `email`/`username`/`oauth_id` slots for re-registration.
- **Cascade behavior:** documents, refresh_tokens, document_permissions (as user), and compliance_memberships are FK-CASCADE-deleted. document_permissions.granted_by gets SET NULL.
- **Guards:** cannot delete self, cannot delete the last active admin (mirrors update_user_role / update_user_status guards).
- **Audit trail:** every deletion writes an `audit_logs` row with `action="user_delete"` and the original username/email captured in `details` JSON for forensic recovery.

### Token Security

- **Refresh token rotation:** each use issues a new token and revokes the old one.
- **Reuse detection:** if a revoked token is presented, ALL tokens for that user are immediately revoked (protects against token theft).
- **Row-level locking** prevents concurrent rotation race conditions.
- Access tokens validated for type (`"access"`) to prevent refresh/exchange token misuse.
- Redis-backed rate limiting with in-memory fallback.

### HTTP Security Headers

- `Strict-Transport-Security` (2 years + preload)
- `Content-Security-Policy` (frame-ancestors 'none')
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Cross-Origin-Resource-Policy: cross-origin`
- `Cache-Control: no-store` on API responses

### Input Validation

- Pydantic v2 schema validation on all request bodies
- Email regex validation + lowercase normalization
- Username restricted to `[a-zA-Z0-9_-]`
- Passwords require minimum 8 characters with at least one uppercase letter, one lowercase letter, one digit, and one special character.
- File upload: extension whitelist, size limit (50 MB)
- Uploaded files are validated against magic byte signatures to prevent disguised file uploads.
- SQL injection prevented by SQLAlchemy ORM parameterized queries
- Path traversal prevented by `realpath` + prefix validation in storage service

### CORS

- Explicit origin allowlist (not wildcard)
- Credentials enabled for cookie-based auth
- Restricted headers: `Authorization`, `Content-Type` only

### Audit Logging

All state-changing operations (upload, download, delete, share, role changes, status changes) are logged to the audit_logs table with user ID, action, resource info, IP address, and timestamp.

## Recent Security Fixes (March 2026)

- OAuth CSRF state parameter validation
- Rate limiter IP spoofing fix (ignore `X-Forwarded-For`)
- OAuth JSON response safety (`JSONResponse` instead of string concatenation)
- Refresh token rotation reordered (validate user before rotating)
- Cookie expiry consistency across all auth paths
- `ValueError` handling in OAuth token exchange

## Reporting a Vulnerability

**Contact:** pollisettisravankumar@gmail.com

Please include:
- Steps to reproduce the issue
- Expected vs. actual behavior
- Any relevant logs or screenshots

## Production Security Checklist

Before deploying to production, ensure all items are completed:

### Secrets & Configuration
- [ ] Generate a cryptographically random SECRET_KEY (64+ chars): `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- [ ] Set `DEBUG=false` in .env
- [ ] Set `ALLOWED_ORIGINS` to exact production domain(s) only
- [ ] Set strong `REDIS_PASSWORD` (not the default)
- [ ] Ensure `.env` files are in `.gitignore` and never committed

### Network & Transport
- [ ] Enable HTTPS via reverse proxy (nginx/Caddy with Let's Encrypt)
- [ ] Verify HSTS header is present (`Strict-Transport-Security`)
- [ ] Verify all security headers present (X-Frame-Options, CSP, etc.)
- [ ] Restrict database access to application servers only

### Database
- [ ] Use SSL for database connections (`sslmode=require` — automatic for non-localhost)
- [ ] Enable connection pooling (Supabase pooler on port 6543)
- [ ] Set up regular database backups
- [ ] Rotate database password periodically

### Authentication
- [ ] Verify rate limiting is active on all endpoints
- [ ] Test that weak passwords are rejected
- [ ] Verify OAuth redirect URIs match production domain
- [ ] Confirm token expiry settings are appropriate (30min access, 7d refresh)

### File Storage
- [ ] For production, enable S3 storage (`USE_S3=true`) instead of local filesystem
- [ ] Ensure uploaded files have restrictive permissions
- [ ] Verify magic bytes validation is active (file type spoofing prevention)

### Monitoring
- [ ] Set up log aggregation for structured JSON logs
- [ ] Monitor health endpoint (`/api/health`)
- [ ] Set up alerts for high error rates and health check failures
- [ ] Review audit logs regularly (`GET /api/admin/audit`)
