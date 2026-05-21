# 09 · API REFERENCE

> REST · JSON · JWT-Bearer · `X-Client-Id` header for tenant · `/docs` in dev only
> 5 v1 routers + 14 compliance + 6 email

## ★ Remember
- Always send `Authorization: Bearer <jwt>` (refresh on 401)
- Pass `X-Client-Id: <id>` for compliance/multi-tenant endpoints
- HTTP 202 → enqueued; poll `/{id}/status` or use WebSocket
- HTTP 422 from AI endpoints → check for `OUT_OF_SCOPE`

---

## 1. Root & health

| Method · Path | Purpose |
|---------------|---------|
| GET `/` | app banner |
| GET `/api/health` | db + redis check |
| GET `/docs` | Swagger (dev only) |
| GET `/redoc` | Redoc (dev only) |

---

## 2. Auth `/api/auth`

| Path | Purpose |
|------|---------|
| POST `/register` | create + token pair · 201 |
| POST `/login` | token pair · 200 |
| POST `/refresh` | rotate + reuse-detect |
| POST `/logout` | revoke refresh |
| GET `/providers` | list local/google/microsoft |
| GET `/oauth/diag` | redirect URI hints |
| GET `/oauth/google` | provider URL + state JWT |
| GET `/callback/google` | provider returns code |
| GET `/oauth/microsoft` | provider URL + state JWT |
| GET `/callback/microsoft` | provider returns code |
| POST `/oauth/exchange` | code → token pair (single-use) |

---

## 3. Documents `/api/documents`

| Path | Purpose |
|------|---------|
| POST `/upload` | 202 + celery_task_id |
| GET `/all` | list + filter + source filter |
| GET `/shared-with-me` | docs shared TO me |
| GET `/search` | FTS query |
| GET `/category/{category}` | filter by category |
| GET `/stats` + `/stats/trends` | aggregates |
| POST `/batch-delete` | bulk soft-delete |
| GET `/{id}` | detail |
| GET `/{id}/status` | poll celery state |
| GET `/{id}/download` | raw file |
| GET `/{id}/preview` | inline preview |
| PUT `/{id}/highlights` | save spans |
| POST `/{id}/share` | add permission |
| GET `/{id}/permissions` | list shares |
| DELETE `/{id}/share/{pid}` | revoke share |
| GET `/{id}/versions` | version history |
| POST `/{id}/rollback` | restore version |
| GET `/{id}/versions/{n}/download` | older snapshot |
| DELETE `/{id}` | soft-delete |

---

## 4. Admin `/api/admin`

| Path | Purpose |
|------|---------|
| GET `/users` | list users |
| GET `/users/{id}` | one user |
| PATCH `/users/{id}/role` | change role |
| PATCH `/users/{id}/status` | activate / deactivate |
| DELETE `/users/{id}` | soft-delete + anonymize |
| GET `/stats` | system stats |
| GET `/audit` | read audit_logs |
| GET `/early-access` | signup queue |
| GET `/early-access/stats` | signup metrics |
| PATCH `/early-access/{rid}` | approve / reject |

---

## 5. ML `/api/ml`

| Path | Purpose |
|------|---------|
| GET `/evaluation` | live accuracy + confusion matrix |

Frontend page `/dashboard/model-evaluation` consumes this.

---

## 6. Early access `/api/early-access`

| Path | Purpose |
|------|---------|
| POST `/` | submit signup (public) |

Approval / listing lives under `/api/admin/early-access`.

---

## 7. Compliance clients `/api/compliance/clients`

| Path | Purpose |
|------|---------|
| GET `/me` | my memberships |
| POST `/` | create client (CLIENT_CREATE) |
| GET `/{id}` | client detail |
| GET `/{id}/members` | list members |
| PATCH `/{id}/branding` | logo url · website · address |
| POST `/{id}/logo` | multipart PNG/JPEG/WEBP (≤340 KB) |
| DELETE `/{id}/logo` | clear logo |

---

## 8. Notices `/api/compliance/notices`

| Path | Purpose |
|------|---------|
| GET `/` | paginated list w/ filters |
| POST `/` | create (NOTICE_CREATE) |
| GET `/{id}` | full detail |
| PATCH `/{id}` | edit fields |
| PATCH `/{id}/status` | state machine transition |
| POST `/{id}/upload` | attach file · feeds OCR queue |
| GET `/{id}/chain` | recursive CTE chain |
| GET `/{id}/activity` | timeline events |
| POST `/bulk` | bulk update (NOTICE_BULK_UPDATE) |

---

## 9. Responses `/api/compliance/{notice_id}/...`

| Path | Purpose |
|------|---------|
| GET `/responses` | get current draft |
| POST `/responses` | create draft (Drafter) |
| PATCH `/responses` | edit draft |
| POST `/responses/submit` | advance approval stage |
| POST `/responses/approve` | reviewer/legal/cfo approve |
| POST `/responses/reject` | send back |
| POST `/responses/withdraw` | drafter rescind |
| POST `/responses/rollback` | restore prior version |
| GET `/evidence` | list attached docs |
| POST `/evidence` | attach document |
| DELETE `/evidence/{doc_id}` | detach |

---

## 10. Reports · Search · AI

| Path | Purpose |
|------|---------|
| POST `/api/compliance/reports/health-summary` | Generate-summary (REPORT_VIEW) |
| GET `/api/compliance/reports/penalty-by-authority` | analytics #1 |
| GET `/api/compliance/reports/notice-volume-by-status` | analytics #2 |
| GET `/api/compliance/reports/response-time-percentiles` | analytics #3 |
| GET `/api/compliance/reports/export.csv` | CSV stream (v2.0.1) |
| GET `/api/compliance/search` | unified FTS (notices + documents) |
| GET `/api/compliance/ai/credentials` | BYOK key state |
| POST `/api/compliance/ai/credentials` | save key (Fernet) |
| DELETE `/api/compliance/ai/credentials` | clear key |
| POST `/api/compliance/ai/test` | ping provider |
| POST `/api/compliance/ai/notice/{id}/summary` | scope-locked |
| POST `/api/compliance/ai/notice/{id}/actions` | recommended actions |
| POST `/api/compliance/ai/invoice/{id}/summary` | |
| POST `/api/compliance/ai/invoice/{id}/actions` | |
| POST `/api/compliance/ai/invoice/{id}/timing` | payment timing |
| POST `/api/compliance/ai/chat` | scope-locked Q&A |

---

## 11. Remaining compliance routers

| Router | Purpose |
|--------|---------|
| `/memberships` | add / remove team members |
| `/notice_types` | CRUD taxonomy |
| `/regulatory_calendar` | list FY 25-26 deadlines |
| `/calendar` | per-client deadline mgmt |
| `/alerts` | schedule/cancel APScheduler jobs |
| `/review_queue` | low-confidence triage list/accept/override |
| `/audit` | compliance audit read (AUDIT_VIEW) |
| WS `/ws/notifications` | real-time bell · auto-reconnect |

---

## 12. Email · Gmail MCP `/api/email`

| Router | Endpoints |
|--------|-----------|
| `oauth` | `GET /gmail/oauth/authorize` · `GET /gmail/oauth/callback` |
| `credentials` | `GET/POST/DELETE /gmail/credentials` (Fernet) |
| `filter_rules` | CRUD ingestion rules |
| `activity` | `GET /activity` ingestion log |
| `bills` | `/email/bills/*` (rebranded "Vendor invoices" — paths unchanged) |
| `view_email` | `GET /view-email/{message_id}` |

All gated on `EMAIL_INTEGRATION_USE` permission.

---

## Status codes you'll see

- `200/201/204` happy paths
- `202` upload accepted, work enqueued
- `207` bulk partial-success
- `400` bad input · `401` bad token · `403` AuthZ deny
- `409` conflict (email exists, OAuth-link refused, duplicate username)
- `422` Pydantic validation **OR** AI `OUT_OF_SCOPE`
- `429` rate-limited · `503` DB/redis down

---

> "In dev hit `/docs` for the live OpenAPI.
> In prod that's hidden — read this page instead."
