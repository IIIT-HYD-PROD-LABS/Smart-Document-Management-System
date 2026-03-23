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
- File upload: extension whitelist, size limit (50 MB)
- SQL injection prevented by SQLAlchemy ORM parameterized queries
- Path traversal prevented by `realpath` + prefix validation in storage service

### CORS

- Explicit origin allowlist (not wildcard)
- Credentials enabled for cookie-based auth
- Restricted headers: `Authorization`, `Content-Type` only

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
