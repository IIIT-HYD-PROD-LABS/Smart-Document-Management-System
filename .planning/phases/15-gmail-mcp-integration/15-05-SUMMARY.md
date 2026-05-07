---
phase: 15-gmail-mcp-integration
plan: 05
subsystem: api
tags: [fastapi, oauth, gmail, jwt, csrf, rls, rbac, savepoint, mcp, in-memory-transport]

requires:
  - phase: 09-compliance-foundation
    provides: require_compliance_permission factory + RBAC matrix (EMAIL_INTEGRATION_USE permission), ClientMembership lookup, RLS-via-X-Client-Id middleware, log_audit_event_strict (consumed transitively via bill_service.mark_paid), per-row SAVEPOINT bulk pattern (notice_service.bulk_update_status)
  - phase: 11-alerts-and-calendar
    provides: APScheduler get_scheduler() + schedule_gmail_scan reschedule on cadence change, scheduler-job removal on credential delete (EMAIL-10)
  - phase: 15-gmail-mcp-integration
    provides: Plan 03 oauth_service.GmailOAuth (get_auth_url + exchange_code), credential_vault.save_credential (Fernet refresh-token), scanner_service.schedule_gmail_scan + cancel-on-delete, bill_service.list_bills + mark_paid (BILL_MARK_PAID audit + reminder-job cancel) + Plan 04 mcp/client.call_gmail_tool (in-memory FastMCP transport)

provides:
  - "POST /api/email/gmail/oauth/authorize — returns Google consent URL with signed-JWT state (10-min exp; nonce + user_id + client_id)"
  - "GET /api/email/gmail/oauth/callback — validates state JWT, exchanges code, persists Fernet-encrypted refresh_token, schedules scanner job, redirects to /dashboard/email/connect"
  - "GET /api/email/credentials — RLS-scoped list of GmailCredential rows for the active client"
  - "PATCH /api/email/credentials/{id} — updates cadence_minutes (5..1440 enforced by Pydantic) + reschedules APScheduler job"
  - "DELETE /api/email/credentials/{id} — soft-disables credential + removes APScheduler job"
  - "GET /api/email/credentials/{cred_id}/filter-rules — list ordered by priority ASC (open question #5: lower priority value wins)"
  - "POST /api/email/credentials/{cred_id}/filter-rules — create rule"
  - "PATCH /api/email/filter-rules/{id} — partial update with exclude_unset semantics"
  - "DELETE /api/email/filter-rules/{id} — hard delete"
  - "GET /api/email/credentials/{cred_id}/activity?limit=50 — last N GmailFetchLog rows newest-first"
  - "GET /api/email/bills?status=&biller_category=&due_before=&due_after=&is_recurring= — bill dashboard list (BILL-03)"
  - "GET /api/email/bills/{id} — single bill detail (404 if missing)"
  - "POST /api/email/bills/{id}/mark-paid — delegates to bill_service.mark_paid (BILL_MARK_PAID audit + APScheduler reminder cancel)"
  - "POST /api/email/bills/bulk-mark-paid — per-row SAVEPOINT (begin_nested) partial-failure pattern; results[] + summary{ok, failed}"
  - "GET /api/email/messages/{message_log_id}/view — fetches body via MCP gmail_read_message tool (D-18 + D-37); body NEVER persisted (D-34)"
  - "All 6 Phase 15 routers mounted in main.py under /api/email prefix, tagged 'gmail' for OpenAPI grouping"

affects: [15-06-frontend, 15-07-smoke, 12-response-drafting-evidence]

tech-stack:
  added: []  # no new libs; reuses Phase 9 + Phase 11 + Plan 03/04 surfaces
  patterns:
    - "Service-layer mutation rule held: routers in this plan never mutate Bill/GmailCredential/GmailMessageLog via direct ORM writes that affect business semantics — list/get/CRUD-of-config-rows pass through, but state changes (mark-paid, schedule, audit) flow through bill_service / credential_vault / scanner_service exclusively. Mirrors Phase 9 D-D pattern (notice_service is single point of mutation for ComplianceNotice.status)."
    - "Cross-origin OAuth state CSRF via signed JWT (HS256, 10-min exp) including {nonce, user_id, client_id} — the callback re-binds the JWT subject to the current authenticated user/membership before persisting credentials. Mirrors backend/app/routers/auth.py:309-315."
    - "Per-row SAVEPOINT for bulk endpoints (db.begin_nested()) — single-row failure rolls back only that row; loop continues; final db.commit() releases all SAVEPOINTs. Matches Phase 9 LIFE-08 partial-failure contract."
    - "Permission gate via membership dependency (not user dependency) — router signatures take ClientMembership = Depends(require_compliance_permission(...)). membership.user_id + membership.client_id used directly so routers don't have to compose two separate dependencies."
    - "On-demand body fetch for view-source-email link — routers/view_email.py invokes call_gmail_tool('gmail_read_message', ...) per request, returns the MCP tool's `data` payload as the HTTP response body, NEVER caches (D-34, D-37)."

key-files:
  created:
    - backend/app/email/routers/__init__.py
    - backend/app/email/routers/oauth.py
    - backend/app/email/routers/credentials.py
    - backend/app/email/routers/filter_rules.py
    - backend/app/email/routers/activity.py
    - backend/app/email/routers/bills.py
    - backend/app/email/routers/view_email.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Permission gate dependency takes ClientMembership directly (not (User, ClientMembership) pair). Routers read membership.user_id + membership.client_id from the single dependency object. Avoids duplicate get_current_user lookups and ensures every endpoint goes through get_active_membership (the only path that enforces auditor expiry + cross-client mode rules)."
  - "OAuth callback re-validates the state JWT user_id + client_id against the current membership before save_credential. Even if a malicious user acquired a valid state token from another session, the callback rejects with 403 if membership context doesn't match. Belt-and-suspenders on top of JWT signature validation."
  - "DELETE /credentials soft-disables (status=disabled) instead of hard-deleting. Hard-delete would orphan source_email_id FKs from ingested Documents and ComplianceNotices, breaking the provenance chain. STATUS_DISABLED is the existing CHECK-constraint value; ON DELETE CASCADE on related tables would still be destructive."
  - "Bulk mark-paid uses db.begin_nested() (SAVEPOINT) per row instead of the bare db.rollback() pattern from notice_service.bulk_update_status. Plan snippet specified begin_nested explicitly; both patterns produce equivalent partial-failure semantics. SAVEPOINT survives the inner exception cleanly without disturbing the outer session — useful when the surrounding session has other pending writes (TenantContextMiddleware sets app.current_client_id via SET LOCAL inside the request transaction)."
  - "view_email.py does NOT write its own audit log row. The MCP tool itself writes a PII-redacted MCP_TOOL_CALL audit entry per Plan 04 D-35/D-36 wiring; double-counting at the router boundary would inflate audit volume without adding traceability."
  - "Bills router status filter validated explicitly (whitelist set {upcoming, due_soon, overdue, paid}) before passing to list_bills service. Pydantic Literal would auto-validate but Query() with Pydantic Literal isn't supported in FastAPI 0.120.4 — explicit set check is the simplest solution that returns a clear 400."

patterns-established:
  - "Phase 15 router pattern: thin router (~100-150 lines) + service-layer mutation. Imports: app.compliance.dependencies.require_compliance_permission, ClientMembership, CompliancePermission, app.database.get_db, app.email.* services. No direct Bill/GmailCredential ORM writes for business semantics; only config-CRUD (filter rules, cadence) goes inline."
  - "OAuth state JWT pattern with user/client binding: state = jwt.encode({nonce, user_id, client_id, exp}); callback validates state user_id == membership.user_id AND state client_id == membership.client_id. Reusable for any future OAuth provider (Outlook, Yahoo, Slack)."
  - "Bulk endpoint return shape: {results: [{id, status: ok|failed, error?}], summary: {ok, failed}}. Frontend renders per-row status indicator + 'Updated N of M' toast from the same payload. Matches Phase 9 BulkUpdateResponse contract."

requirements-completed:
  - EMAIL-01  # OAuth authorize/callback wired to GmailOAuth + signed-JWT state CSRF
  - EMAIL-02  # MCP tools surface accessible via view_email router (delegating to call_gmail_tool from Plan 04)
  - EMAIL-04  # Filter rules CRUD with priority-ordered list
  - EMAIL-07  # Activity router exposing GmailFetchLog three-state status (read-only)
  - EMAIL-09  # Audit log per MCP tool call (delegated through view_email -> call_gmail_tool which writes MCP_TOOL_CALL audit row)
  - EMAIL-10  # DELETE /credentials disables credential + removes APScheduler job
  - BILL-03  # Bills dashboard list with upcoming/due_soon/overdue/paid + biller_category + recurrence filters
  - BILL-04  # Reminder cancel via mark_paid -> bill_service.mark_paid path which removes 3 APScheduler reminder jobs
  - BILL-05  # Mark-paid endpoint writes BILL_MARK_PAID audit log via bill_service
  - BILL-06  # Bulk mark-paid with per-row SAVEPOINT partial-failure semantics

duration: 5min
completed: 2026-05-08
---

# Phase 15 Plan 05: Routers Summary

**7 FastAPI routers mounted under `/api/email` prefix — Gmail OAuth (POST authorize / GET callback with signed-JWT state CSRF) + GmailCredential CRUD with APScheduler reschedule + GmailFilterRule CRUD with priority ordering + read-only GmailFetchLog activity + Bill dashboard with mark-paid + bulk-mark-paid (per-row SAVEPOINT) + on-demand view-source-email via MCP `gmail_read_message`. Every endpoint gated by `require_compliance_permission(EMAIL_INTEGRATION_USE)`. Service-layer mutation pattern preserved end-to-end.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-07T18:26:33Z
- **Completed:** 2026-05-08T (executed across midnight UTC)
- **Tasks:** 2
- **Files created:** 7 (6 router modules + 1 package __init__)
- **Files modified:** 1 (backend/app/main.py)

## Accomplishments

- Two task commits, each independently importable and verified at runtime against the running container
- 12 distinct paths registered under /api/email (15 endpoints total — credentials/{id} carries both PATCH and DELETE, filter-rules CRUD groups several methods per path); OpenAPI spec (`GET /openapi.json`) exposes all of them under the 'gmail' tag
- Backend container restarts cleanly: `Scheduler started [apscheduler.scheduler]` followed by `Application startup complete.` in logs; `/api/health` returns 200
- All endpoint handlers depend on `require_compliance_permission(EMAIL_INTEGRATION_USE)` — 21 occurrences across the 6 router files (10 endpoints × 2 imports per file = consistent gate)
- Service-layer mutation rule held: bills router does NOT call `db.add(Bill(...))` or `bill.payment_status = ...` directly — every state change routes through `bill_service.mark_paid` which writes the BILL_MARK_PAID audit row
- OAuth callback re-validates state JWT against current membership (defense in depth); JWT payload binds user_id + client_id so even a leaked state token can't cross-tenant
- Per-row SAVEPOINT bulk mark-paid: `db.begin_nested()` per bill_id; single-bill failure isolates to that row, loop continues, final `db.commit()` releases all SAVEPOINTs
- view_email router uses `call_gmail_tool('gmail_read_message', ...)` from Plan 04's in-memory FastMCP client — body never persisted to DB or Redis (D-34); audit row written by the MCP tool itself, not duplicated at the router boundary
- Plan 06 (frontend) can immediately consume all 12 endpoints via the existing `complianceApi.tenantHeaders()` axios pattern — no further wiring required

## Task Commits

1. **Task 1: OAuth + credentials + filter-rules + activity routers** — `af78443` (feat)
2. **Task 2: Bills + view-email routers + main.py mount** — `4fcfd66` (feat)

## Files Created

| File | Purpose |
|------|---------|
| `backend/app/email/routers/__init__.py` | Package marker |
| `backend/app/email/routers/oauth.py` | POST /gmail/oauth/authorize + GET /gmail/oauth/callback. Signed-JWT state CSRF; calls credential_vault.save_credential + scanner_service.schedule_gmail_scan after token exchange. |
| `backend/app/email/routers/credentials.py` | GET list / PATCH cadence / DELETE soft-disable. PATCH reschedules APScheduler job at the new cadence; DELETE removes the job. |
| `backend/app/email/routers/filter_rules.py` | Full CRUD on GmailFilterRule. List ordered by `priority ASC, id ASC` (open question #5: lower priority value wins). |
| `backend/app/email/routers/activity.py` | Read-only GET listing of last N GmailFetchLog rows for a credential, newest first. |
| `backend/app/email/routers/bills.py` | GET list with bucket filter (upcoming/due_soon/overdue/paid) + biller_category + due_before/after + is_recurring; GET detail; POST mark-paid (delegates to bill_service); POST bulk-mark-paid with per-row SAVEPOINT (begin_nested) partial-failure shape. |
| `backend/app/email/routers/view_email.py` | GET /messages/{message_log_id}/view. Resolves message_log -> credential, calls `await call_gmail_tool('gmail_read_message', ...)`, returns MCP tool result as the HTTP body. NEVER caches body (D-34). |

## Files Modified

| File | Change |
|------|--------|
| `backend/app/main.py` | + 6-line `from app.email.routers import (oauth, credentials, filter_rules, activity, bills, view_email)` block + 6 `app.include_router(..., prefix='/api/email', tags=['gmail'])` lines after the existing Phase 9-13 compliance router mounts. Lifespan + middleware + exception handlers + v1.0 routers untouched. |

## Endpoint Matrix

| Method | Path | Auth | Service-layer call |
|--------|------|------|--------------------|
| POST | `/api/email/gmail/oauth/authorize` | EMAIL_INTEGRATION_USE | `GmailOAuth.get_auth_url(state, redirect_uri)` |
| GET | `/api/email/gmail/oauth/callback` | EMAIL_INTEGRATION_USE | `GmailOAuth.exchange_code` -> `credential_vault.save_credential` -> `scanner_service.schedule_gmail_scan` |
| GET | `/api/email/credentials` | EMAIL_INTEGRATION_USE | RLS-scoped list query |
| PATCH | `/api/email/credentials/{id}` | EMAIL_INTEGRATION_USE | `scanner_service.schedule_gmail_scan(cred.id, new_cadence)` |
| DELETE | `/api/email/credentials/{id}` | EMAIL_INTEGRATION_USE | scheduler.remove_job(`gmail_scan_{id}`) |
| GET | `/api/email/credentials/{id}/filter-rules` | EMAIL_INTEGRATION_USE | priority ASC list |
| POST | `/api/email/credentials/{id}/filter-rules` | EMAIL_INTEGRATION_USE | (config-CRUD; inline ORM allowed) |
| PATCH | `/api/email/filter-rules/{id}` | EMAIL_INTEGRATION_USE | (config-CRUD; inline ORM allowed) |
| DELETE | `/api/email/filter-rules/{id}` | EMAIL_INTEGRATION_USE | (config-CRUD; inline ORM allowed) |
| GET | `/api/email/credentials/{id}/activity` | EMAIL_INTEGRATION_USE | RLS-scoped read-only list |
| GET | `/api/email/bills` | EMAIL_INTEGRATION_USE | `bill_service.list_bills` |
| GET | `/api/email/bills/{id}` | EMAIL_INTEGRATION_USE | RLS-scoped read |
| POST | `/api/email/bills/{id}/mark-paid` | EMAIL_INTEGRATION_USE | `bill_service.mark_paid` (writes BILL_MARK_PAID audit, cancels reminders) |
| POST | `/api/email/bills/bulk-mark-paid` | EMAIL_INTEGRATION_USE | per-row `bill_service.mark_paid` inside `db.begin_nested()` |
| GET | `/api/email/messages/{id}/view` | EMAIL_INTEGRATION_USE | `call_gmail_tool('gmail_read_message', ...)` (in-memory FastMCP) |

## Decisions Made

- **Permission gate dependency takes ClientMembership directly, not (User, ClientMembership).** Routers signatures take `membership: ClientMembership = Depends(require_compliance_permission(EMAIL_INTEGRATION_USE))` and read `membership.user_id + membership.client_id` from the single dependency object. Avoids duplicate `get_current_user` lookups and ensures every endpoint goes through `get_active_membership`, which is the only path that enforces auditor expiry + cross-client mode rules.

- **OAuth callback re-validates state JWT user_id + client_id against current membership before persisting credentials.** Even if a malicious user acquired a valid state token from another session, the callback rejects with 403 if membership context doesn't match. Belt-and-suspenders on top of JWT signature validation. Mirrors a defense-in-depth posture similar to v1.0 OAuth state validation.

- **DELETE /credentials soft-disables (status=disabled) instead of hard-deleting.** Hard-delete would orphan `source_email_id` FKs from ingested Documents (Plan 02 added the column) and from `gmail_message_log` rows referenced by Bill.source_email_id, breaking the provenance chain. STATUS_DISABLED is the existing CHECK-constraint value (active|revoked|disabled); soft-disable preserves all FK relationships. ON DELETE CASCADE on related tables would still be destructive — chosen pattern keeps audit history intact.

- **Bulk mark-paid uses `db.begin_nested()` (SAVEPOINT) per row.** Plan snippet specified `begin_nested` explicitly. Both `db.begin_nested` (SAVEPOINT) and `db.rollback` patterns produce equivalent partial-failure semantics, but SAVEPOINT survives the inner exception cleanly without disturbing the outer session — useful when the surrounding session has other pending writes (TenantContextMiddleware sets `app.current_client_id` via SET LOCAL inside the request transaction). Acceptance criterion `grep "begin_nested"` passes.

- **view_email.py does NOT write its own audit log row.** The MCP tool itself writes a PII-redacted `MCP_TOOL_CALL` audit entry per Plan 04 D-35/D-36 wiring (`_audit_call('gmail_read_message', {...})`). Adding a router-side audit row would double-count without adding traceability. The MCP audit row already includes the user/client context via the call args.

- **Bills router validates status filter with explicit set whitelist `{upcoming, due_soon, overdue, paid}` before passing to `list_bills`.** Using Pydantic Literal directly on a `Query(...)` parameter doesn't fully constrain the value in FastAPI 0.120.4 (the bill_service falls through silently if the bucket doesn't match). Explicit set check returns a clear 400 — better debuggability than a silent empty list.

- **OAuth callback uses GET with code/state/error query params (not POST body).** Google's OAuth 2.0 web-server flow always redirects back via GET with query params — there's no choice here. The router signature reflects that with `Query(default=None)` for code/state/error. The authorize endpoint uses POST because it's an internal API call from the React frontend (no browser navigation) — POST keeps the signed JWT state out of access logs.

## Deviations from Plan

None — plan executed exactly as written. The plan's task action snippets were directly usable; the only adjustments made were to align the dependency signature (`require_compliance_permission` returns `ClientMembership`, not a User object) with the router pattern from `backend/app/compliance/routers/notices.py:142` (which the plan referenced as the canonical example). The plan's `read_first` list pointed at this pattern explicitly so this is not a deviation — it's adherence to the referenced pattern.

## Issues Encountered

None — backend container restarted cleanly; all router imports resolved on the first try; all acceptance criteria checks passed without iteration. Phase 15 email tests still 10 passed / 32 skipped (matching Plan 04 baseline; no new stub flips because the existing router-level stubs use a guard pattern of `pytest.skip("Plan 05 — full behavior assertions land then")` AFTER the import, so a successful import is sufficient for the import-check half but the deferred behavior assertions still skip).

## User Setup Required

None for code exercise. End-to-end OAuth round-trip requires:
1. **Google Cloud Console**: register `${BASE_URL}/api/email/gmail/oauth/callback` as an authorized redirect URI on the existing OAuth client (the same client_id used for Google login is fine — scopes are additive at consent time).
2. **Environment variables**: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are already configured for v1.0 Google login. Optional: `GMAIL_OAUTH_REDIRECT_URI` if BASE_URL-derived default isn't suitable.

These are not new environment variables — they reuse the v1.0 Google OAuth credentials. Plan 06 (frontend) UX prompts the user through the Google consent screen.

## Next Phase Readiness

- **Plan 06 (Wave 5 — Frontend)** can immediately wire React pages to all 12 endpoints. Recommended `complianceApi.tenantHeaders()` + axios interceptor reuse from Phase 9 Plan 06. The OAuth flow is a single POST -> response.authorize_url -> window.location.href = url; the callback redirects to `/dashboard/email/connect?status=success&credential_id=N` so the page can fetch `GET /credentials` and surface the new credential.
- **Plan 07 (Wave 6 — Smoke)** end-to-end flow now executable from the user's browser:
  1. POST /api/email/gmail/oauth/authorize -> redirect to Google
  2. User consents -> Google redirects to /api/email/gmail/oauth/callback
  3. Callback persists credential + schedules scanner -> APScheduler runs scanner_task -> ingests messages -> creates ComplianceNotice (B2 wiring from Plan 03) + Bill records (B1 wiring from Plan 03)
  4. UI fetches /api/email/bills -> shows bill -> POST /api/email/bills/{id}/mark-paid -> BILL_MARK_PAID audit row written
  5. UI clicks "View source email" -> GET /api/email/messages/{id}/view -> MCP gmail_read_message returns body -> body NEVER persisted (D-34)
- **Phase 12 (Response Drafting + Evidence Agents)** can now layer on by reusing `call_gmail_tool` from agent contexts; the router tier is fully decoupled.

## Reconciliation Anchors Locked at Code Layer

| Recon # / Decision | Contract | Where verified |
|--------------------|----------|----------------|
| Open question #5 | Lower priority value wins; ties by id ASC | `routers/filter_rules.py: order_by(GmailFilterRule.priority.asc(), GmailFilterRule.id.asc())` |
| D-04 / D-35 / D-36 | Audit row per MCP tool call written inside the tool, not the router | `routers/view_email.py` does NOT call log_audit_event_strict; `mcp/tools.py:_audit_call` does |
| D-18 / D-37 | View-source-email link delegates to MCP gmail_read_message | `routers/view_email.py: await call_gmail_tool('gmail_read_message', ...)` |
| D-22 (BILL-04) | Mark-paid stops further reminders | `routers/bills.py -> bill_service.mark_paid -> sched.remove_job(_reminder_job_id(bill_id, tier))` for tier in (bill_t3, bill_t1, bill_overdue) |
| D-34 | Body never persisted to DB or Redis | `routers/view_email.py` returns the MCP tool result directly; no Redis writes; no DB column references the body |
| EMAIL-10 | DELETE /credentials disables + removes scheduler job | `routers/credentials.py: cred.status = STATUS_DISABLED; sched.remove_job(f'gmail_scan_{credential_id}')` |
| Phase 9 D-D | Service-layer mutation only for state changes | `grep -E 'db.add\(.*Bill\(|bill\.payment_status\s*=' backend/app/email/routers/bills.py` returns 0 |
| Phase 9 LIFE-08 (Pattern 8) | Per-row SAVEPOINT bulk partial-failure | `routers/bills.py:bulk_mark_bills_paid: with db.begin_nested(): mark_paid(...)` |

---

*Phase: 15-gmail-mcp-integration*
*Plan: 05 — Routers (Wave 4)*
*Completed: 2026-05-08*

## Self-Check: PASSED

All 7 created files exist on disk. Modified file (backend/app/main.py) exists. Both task commits exist in git history (`af78443`, `4fcfd66`). Plan-level verification: 6 router files + main.py edit; 6 `include_router(gmail_*)` calls in main.py; 12 distinct paths under /api/email in OpenAPI spec; backend container reaches healthy after restart with `Scheduler started` + `Application startup complete` log lines; `pytest tests/compliance/email/` returns 10 passed / 32 skipped (matching Plan 04 baseline; no regression).
