# Security Policy

## Supported Versions

| Version      | Supported |
| ------------ | --------- |
| 1.0.x (current) | Yes   |

## Security Architecture

### Authentication

- JWT access tokens (HS256, 30-minute expiry)
- Opaque refresh tokens with rotation and reuse detection
- bcrypt password hashing (passlib)
- OAuth SSO: Google and Microsoft with CSRF state parameter
- Rate limiting: 5 requests/minute on auth endpoints

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
