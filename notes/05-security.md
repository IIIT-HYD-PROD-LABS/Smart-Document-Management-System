# 05 · SECURITY

> JWT + opaque refresh · OAuth · 7×12 RBAC · RLS · Audit-immutable · Rate-limited · OWASP-aware

## ★ Remember
- **4 overlapping layers** — middleware, AuthN/Z, RLS, DB triggers
- RBAC at route, RLS at DB
- bcrypt for passwords, JWT (HS256) for sessions
- Refresh-token rotation with **reuse-detect = nuke**
- `audit_logs` is **immutable** at the DB level

---

## 1. Defense in depth

```
LAYER 1 — HTTP middleware            CORS · CSP · HSTS · XFO · GZip · Rate limit
LAYER 2 — AuthN (JWT) + AuthZ (RBAC) 3-tier + 7×12 matrix at the route layer
LAYER 3 — Tenant context             X-Client-Id → Postgres session var → RLS
LAYER 4 — DB triggers + role grants  audit_logs immutable; app_runtime no DELETE
```

If any one layer is bypassed, the others still hold. Each layer makes a different assumption about the threat.

---

## 2. Auth flows

```
LOCAL
  /register → bcrypt(password) → row inserted
  /login    → verify bcrypt   → access + refresh
  /refresh  → rotate refresh  → reuse-detect → nuke

OAUTH (Google · Microsoft)
  /oauth/google     → state JWT (10 min · CSRF)
  provider redirect → /callback/google
  backend creates user (or links · refuses local-pwd link)
  redirect → /oauth/callback?code=&token=  (2-min JWT)
  POST /oauth/exchange   ← single-use jti via Redis
  → access + refresh
```

---

## 3. Token strategy

| Token | Shape | Where |
|-------|-------|-------|
| Access | JWT HS256 (sub + role + exp) | `Authorization: Bearer` header |
| Refresh | Opaque random (`secrets.token_urlsafe`) | `refresh_tokens` table |
| OAuth exchange | JWT 2-min + jti for replay | URL one-shot |
| OAuth state | JWT 10-min | CSRF state param |

Access tokens are stateless (no DB read). Refresh tokens are stateful (DB row) so we can revoke instantly.

---

## 4. Refresh rotation + reuse-detect

```sql
SELECT … FROM refresh_tokens
   WHERE token = ?
   FOR UPDATE          -- row lock

-- if already revoked
UPDATE refresh_tokens
   SET is_revoked = TRUE
   WHERE user_id = ? AND is_revoked = FALSE;
-- → 401 "reuse detected" · all sessions killed

-- if expired
revoke + 401

-- otherwise
issue new refresh
old.replaced_by = new
commit
```

`backend/app/routers/auth.py:161` — `with_for_update()` prevents concurrent rotation races.

---

## 5. RBAC v1.0 (3-tier)

| Role | Powers |
|------|--------|
| admin | users · roles · soft-delete · all docs |
| editor | upload · share own docs |
| viewer | read shared docs |

- First registered user automatically becomes admin
- Admin can change role + status
- Soft-delete + PII anonymize keeps audit trail intact

---

## 6. RBAC v2.0 — Compliance 7×12 matrix

```
                  VIEW CREATE DRAFT APPROVE LEGAL CFO SUBMIT BULK REVIEW ATTACH AUDIT_VIEW EMAIL
compliance_head   ✓    ✓      ·     ✓       ·     ·   ✓      ✓    ✓      ✓      ✓          ✓
legal_team        ✓    ·      ✓     ·       ✓     ·   ·      ·    ✓      ✓      ·          ·
finance_team      ✓ᴳ   ·      ·     ·       ·     ·   ·      ·    ·      ·      ·          ·
auditor           ✓    ·      ·     ·       ·     ·   ·      ·    ·      ·      ✓          ·
ca_consultant     ✓    ✓      ✓     ✓       ✓     ✓   ✓      ✓    ✓      ✓      ·          ·
staff             ✓    ·      ·     ·       ·     ·   ·      ·    ·      ·      ·          ·
cfo               ✓    ·      ·     ·       ·     ✓   ·      ·    ✓      ✓      ✓          ✓

ᴳ FINANCE_TEAM has NOTICE_VIEW but is scoped to GST/IT only at the service layer.
+ CLIENT_CREATE · CLIENT_MANAGE · REPORT_VIEW · REPORT_EXPORT · ESCALATION_TRIGGER
```

Source: `backend/app/compliance/services/permission_registry.py`. Verified by 84-case parametrized test (`tests/test_compliance_endpoints.py::test_role_permission_matrix`).

---

## 7. Row Level Security (request flow)

```
incoming request
   │ X-Client-Id: 42
   ▼
TenantContextMiddleware
   sets ContextVar current_client_id = 42
   ▼
route handler → Depends(get_db)
   ▼
SQLAlchemy before_cursor_execute  (every statement)
   SET app.current_client_id = 42
   SET app.user_id           = jwt.sub
   SET app.cross_client_mode = false
   SET ROLE app_runtime
   ▼
SELECT * FROM compliance_notices
   ─► RLS rewrites:  …AND client_id = 42
```

No tenant header → no `set_config` → policy denies all rows. **Fail-closed.**

---

## 8. Security headers (`backend/app/middleware/security_headers.py`)

| Header | Value |
|--------|-------|
| X-Frame-Options | DENY |
| X-Content-Type-Options | nosniff |
| X-XSS-Protection | 0 |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | camera=() microphone=() geolocation=() |
| Content-Security-Policy | frame-ancestors 'none' |
| Cross-Origin-Resource-Policy | cross-origin |
| X-Permitted-Cross-Domain-Policies | none |
| Cache-Control | no-store, no-cache, must-revalidate, private |
| Strict-Transport-Security | 63072000; includeSubDomains; preload *(prod only)* |

---

## 9. Rate limiting (slowapi)

- Per-IP + per-route limits
- `RATE_LIMIT_AUTH` applies to register/login/refresh/logout/oauth
- OAuth provider URL endpoints capped at `30/minute`
- Storage: in-memory in dev; Redis-backed in prod
- Returns HTTP 429 with `Retry-After`

---

## 10. Upload hardening

- **Magic-byte check** — not just extension
- SVG is **rejected** for logo upload (XSS via embedded `<script>`)
- Logo cap: 340 KB base64 data URL
- Path-traversal guard via `_validate_path_inside_upload_dir()`
- `MAX_FILE_SIZE_MB` enforced before OCR
- OCR worker re-validates path before `open()`

---

## 11. Secrets & crypto

- `SECRET_KEY` validated: ≥ 32 chars, ≥ 10 unique
- OAuth client secrets live in env only
- `ai_credentials` table stores Fernet-encrypted BYOK keys
- Encryption cipher is the `INFRA-06` module
- Plaintext NEVER returned to API consumers
- bcrypt cost factor default (12)

---

## 12. OWASP Top 10 (2021) coverage

| OWASP | Mitigation |
|-------|-----------|
| A01 Broken Access Control | RBAC (3-tier + 7×12) at route + RLS at DB · audit trigger blocks tamper |
| A02 Cryptographic Failures | HTTPS in prod, HSTS, bcrypt for passwords, Fernet for BYOK keys |
| A03 Injection | SQLAlchemy parameterized queries · Pydantic v2 input validation · CHECK constraints on enums |
| A04 Insecure Design | Multi-layer (middleware + AuthZ + RLS + audit trigger) · state machines for valid transitions |
| A05 Security Misconfiguration | SecurityHeadersMiddleware · `DEBUG=false` hides /docs in prod · default-deny policies |
| A06 Vulnerable / Outdated Components | requirements.txt pinned · pip check clean · Phase 15 reconciliation block |
| A07 Identification / Auth Failures | JWT + opaque refresh + rotation + reuse-detect + slowapi rate limit |
| A08 Software & Data Integrity | Audit trigger forbids row mutation · refresh-chain integrity via `replaced_by` |
| A09 Logging & Monitoring | structlog + correlation-id · `audit_logs` append-only · dead-letter JSONL for DB-outage events |
| A10 SSRF | OAuth redirect URIs whitelisted · BYOK provider URLs hardcoded · httpx with timeouts |

---

## Exam-ready Q&A

**Q: How do you prevent tenant data leakage?**
`X-Client-Id` → ContextVar → `before_cursor_execute` → `SET app.current_client_id` → RLS policy + fail-closed when unset.

**Q: What if a refresh token is stolen?**
Reuse-detect: presenting an already-revoked token nukes *all* the user's tokens. Forces an attacker to lose access the moment the victim refreshes.

**Q: How is the audit log made tamper-proof?**
A `BEFORE UPDATE OR DELETE` trigger raises an exception. `REVOKE UPDATE, DELETE FROM app_runtime` for belt-and-braces.

**Q: How are BYOK keys protected?**
Fernet symmetric encryption (INFRA-06 cipher), key in env, plaintext never leaves the server.

---

> "Belt and braces.
> The DB doesn't trust the app, the app doesn't trust the client."
