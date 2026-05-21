# 10 · AUTH DEEP-DIVE

> JWT (HS256) access · opaque refresh w/ rotation + reuse-detect · OAuth Google & Microsoft · CSRF via state JWT · single-use exchange

## ★ Remember
- 2 tokens: short-lived JWT access + long-lived opaque refresh
- **Reuse-detect = nuke all sessions for that user**
- OAuth state = signed JWT (10 min), not cookie
- Exchange code = single-use (Redis `SET NX`, in-memory fallback)
- bcrypt cost factor default (12)

---

## 1. Local login flow

```
POST /api/auth/login
  body: { email, password }
   ▼
SELECT user WHERE email = ?
  if not found              → 401
  if auth_provider != local → 401
  if !verify_password()     → 401
  if !is_active             → 401
   ▼
access  = jwt.encode({sub, role, exp+30m})
refresh = secrets.token_urlsafe(64), exp+7d
INSERT refresh_tokens(token, user_id, expires_at)
   ▼
200 { access_token, refresh_token, user }
```

All errors return the **same** message "Invalid email or password" to avoid email enumeration.

---

## 2. Register flow

```
POST /api/auth/register
  body: { email, username, password, full_name? }
   ▼
if email exists    → 409
if username exists → 409
   ▼
is_first = users.count() == 0
role     = 'admin' if is_first else 'editor'
hashed   = bcrypt(password)
INSERT users
   ▼
issue token pair  (same as login)
201 { access_token, refresh_token, user }
```

---

## 3. Refresh rotation + reuse detection

```
POST /api/auth/refresh   body: { refresh_token }
   ▼
SELECT * FROM refresh_tokens
   WHERE token = :rt
   FOR UPDATE          ← prevents concurrent rotation race
   ▼
┌── token not found ──────────────────────────────────┐
│   401 "Invalid refresh token"                        │
└─────────────────────────────────────────────────────┘
┌── token already revoked  ←  THE KILL-SWITCH          │
│   UPDATE refresh_tokens                              │
│     SET is_revoked = TRUE, revoked_at = now()        │
│     WHERE user_id = :uid AND is_revoked = FALSE      │
│   commit                                             │
│   401 "Refresh token reuse detected --              │
│        all sessions revoked"                         │
└─────────────────────────────────────────────────────┘
┌── token expired                                      │
│   revoke it · 401 "expired"                          │
└─────────────────────────────────────────────────────┘
   ▼ valid
load user · check is_active
   ▼
new_refresh = secrets.token_urlsafe()
old.is_revoked = TRUE
old.replaced_by = new_refresh   ← rotation chain
INSERT new refresh
commit
   ▼
new access = jwt.encode({sub, role, exp+30m})
200 { access, refresh, user }
```

---

## 4. OAuth start (CSRF state)

```
GET /api/auth/oauth/google
   ▼
if GOOGLE_CLIENT_ID empty → 404
   ▼
nonce = secrets.token_urlsafe(16)
state = jwt.encode({nonce, exp: now+10m}, SECRET, HS256)
url   = google_authorize_url + state + redirect_uri
200 { url }
```

Cookies cannot be used for CSRF — backend is on `:8000` and frontend on `:3000`, cross-origin cookies are unreliable. State JWT is self-verifying.

---

## 5. OAuth callback

```
GET /api/auth/callback/google?code=...&state=...
   ▼
jwt.decode(state, SECRET)
   if ExpiredSignatureError → 400
   if InvalidTokenError     → 400 (possible CSRF)
   ▼
token_data = GoogleOAuth.exchange_code(code)
user_info  = GoogleOAuth.get_user_info(access)
   if not verified_email → 400
   ▼
find user by oauth_id
  found → use it
  not found:
    find by email:
      if auth_provider=='local' AND hashed_password
        → 409 (refuse silent link to local-pwd account)
      else: link oauth_id
    none: create new user (first user → admin)
   ▼
exchange_code  = secrets.token_urlsafe(32)
exchange_token = jwt.encode({sub, role,
                  type='oauth_exchange',
                  code: exchange_code,
                  exp: now+2m})
redirect → FRONTEND/oauth/callback?code=...&token=...
```

---

## 6. OAuth exchange (single-use)

```
POST /api/auth/oauth/exchange
   body: { code, token }
   ▼
payload = jwt.decode(token, SECRET)
   if InvalidTokenError              → 401
   if payload.type != 'oauth_exchange' → 401
   ▼
secrets.compare_digest(payload.code, body.code)  ← constant-time
   ▼
jti = payload.jti
   ▼
redis.set('oauth_exchange_used:'+jti, '1', NX=True, EX=180)
   if NX fails  → 401 "already used"     ← replay block
   if redis down → in-memory dict fallback ← still single-use
   ▼
load user; check is_active
   ▼
return token pair (200)
```

Two layers of replay protection: a Redis `SET NX`, and an in-process dict + lock as fallback. Exchange token lives only 2 minutes.

---

## 7. Logout

```
POST /api/auth/logout
  body: { refresh_token }
   ▼
find row
  if not found → 401
  if !revoked  → revoke + commit
   ▼
200 "Successfully logged out"
```

Access token still valid until natural expiry (30 min). Refresh revoked = no rotation possible.

---

## 8. Token shapes

```
ACCESS  (JWT HS256)
  sub  : "42"           ← user id as str
  role : "admin"
  iat  : 17xx…
  exp  : 17xx…  (30m default)

REFRESH (opaque)
  64-char urlsafe base64
  stored in refresh_tokens row:
    id · token (UQ) · user_id
    expires_at · is_revoked
    revoked_at · replaced_by
```

---

## 9. Rate limits (slowapi)

| Endpoint | Default |
|----------|---------|
| `/register · /login · /refresh · /logout` | `RATE_LIMIT_AUTH` |
| `/oauth/google · /callback/* · /oauth/exchange` | `RATE_LIMIT_AUTH` |
| `/providers · /oauth/diag` | 30 / minute |
| `/upload` | `RATE_LIMIT_UPLOAD` (default 10 / min) |
| default | `RATE_LIMIT_DEFAULT` (default 60 / min) |

---

## 10. CSRF / state notes

- OAuth `state` is a signed JWT (10 min) — replaces cookie-based CSRF
- Backend and frontend on different origins → cookies unreliable for CSRF
- Exchange token `jti` tracked in Redis (in-memory fallback)
- Refresh tokens are opaque → no signature to forge
- JWT decoded with explicit `algorithms=[settings.ALGORITHM]` whitelist — no algorithm-confusion attacks

---

## 11. AuthN vs AuthZ

| Layer | What |
|-------|------|
| AuthN | "Who are you?" — bcrypt verify · OAuth |
| JWT | "Proof you're you" — short-lived bearer |
| AuthZ v1.0 | 3-tier role on `users` row · admin/editor/viewer |
| AuthZ v2.0 | 7×12 matrix · per-tenant via `compliance_memberships` |
| Tenant | `X-Client-Id` → ContextVar → RLS at DB |

---

## 12. Edge cases to remember

- **OAuth + local pwd**: if email already has a password, OAuth link is refused with 409. User must log in with password first to prove ownership, then link OAuth from settings.
- **Microsoft no verified_email flag**: rely on `mail` or `userPrincipalName`; lowercase normalized.
- **First user is admin**: skip registration gate; subsequent users default to `editor`.
- **Race on concurrent refresh**: `FOR UPDATE` serializes; second caller hits "reuse detected".
- **Redis down for exchange replay**: in-memory dict fallback (single-worker safe).
- **OAuth user creation conflict**: re-fetch by email if `IntegrityError` (concurrent register).

---

> "Stateless tokens scale.
> Stateful tokens revoke.
> The right design uses both."

**Why opaque refresh + JWT access?**
- JWT access is fast (no DB read) and short-lived (30 min)
- Opaque refresh is stateful → can revoke instantly + detect reuse
- You can't have BOTH stateless and revocable, so split the responsibility
- Rotation chain via `replaced_by` lets you trace a stolen-token tree
