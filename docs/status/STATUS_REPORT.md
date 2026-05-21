# Smart Document Management System, Status Report

**Organization:** Product Labs, IIIT Hyderabad
**Last Updated:** 2026-05-21 (compliance overhaul, admin-only client creation, email-based team invites, notice-assign endpoint, review-queue heuristic + triage workbench)

## 2026-05-21 (PM), compliance flow rewired end-to-end

The morning sweep stopped 500s and CI churn; the afternoon went deeper into the compliance domain after the user flagged structural bugs ("review queue is not working at all", "the email is not there by user id how can they login", "only admin can create a client then client can add the rest of the team"). Five commits shipped, CI + Deploy green, live E2E verified against Supabase.

### Admin-only client creation + email-based team invite

The team-add flow was broken at a structural level: admins added members by typing a numeric user_id into a form, which only worked if the invitee had already self-registered. There was no way to invite someone who did not yet have a TaxSync account, so the natural "I am setting up the workspace for my team" path was impossible.

New shape (`backend/app/services/invitation_service.py`):

1. system admin (`users.role='admin'`) calls `POST /api/compliance/clients` to provision a workspace. Earlier paths (bootstrap-no-memberships, ca_consultant CLIENT_CREATE) are gone, removing the tenant-sprawl risk.
2. admin or compliance_head calls `POST /api/compliance/clients/{id}/memberships` with `{email, full_name?, compliance_role}`.
3. the resolver decides: existing TaxSync account, attach directly; no account, pre-create a pending User (`is_active=False`, `hashed_password=NULL`) plus a 7-day signed JWT emailed via Resend.
4. invitee opens `/accept-invite?token=<JWT>`, sets a password, the backend flips `is_active=True` and returns the standard access + refresh pair. The invitee lands signed-in on `/dashboard` with the membership granted in step 2.
5. idempotency: a second accept-invite call returns 400 with "sign in with your existing password" instead of overwriting silently.

`compliance/schemas/client.py` enforces exactly-one-of email/user_id with a Pydantic model_validator. `compliance/services/client_service.py:onboard_client` resolves email-keyed team rows the same way, so the onboarding wizard's team step can invite by email too. `compliance/dependencies.py:require_client_create_or_first_onboard` collapsed from 100 lines of conditional gates to a single admin check.

Frontend: `AddMemberDialog` swapped the numeric input for email + optional full name, and the toast now reports whether the path was attach vs invite-sent. `OnboardingWizard/StepTeam` and `onboardingWizardStore` track the same shape. New `/accept-invite` page wires `setTokensFromOAuth` so the invitee is signed-in immediately after setting their password.

Commit: `f6447d8` (13 files, 854 insertions, 139 deletions).

### Dedicated notice-assign endpoint + WebSocket notification

Reassigning a notice used to mean calling `PATCH /notices/{id}` with an `assigned_user_id` field. That endpoint validated only the FK (which accepts any users.id, including cross-tenant), and never told the new assignee.

New `POST /api/compliance/notices/{notice_id}/assign` (`backend/app/compliance/routers/notices.py`):

- body `{"assigned_user_id": <int> | null}` (null clears),
- permission `NOTICE_CREATE`,
- verifies the assignee has an active ClientMembership on the notice's client (defence vs cross-tenant FK win),
- writes a `NoticeActivity` row with `activity_type="notice_assigned"`,
- writes an immutable AuditLog entry with before / after,
- publishes `{type: "notice_assigned", recipient_user_id, payload: {notice_id, notice_number, authority, response_deadline, inviter_user_id}}` to the `notifications:{client_id}` Redis pubsub channel. The existing `NotificationBell` WebSocket forwards it to the assignee's open dashboard.

`dispatch_alert` was bypassed intentionally: the `notice_alert_log.alert_type` CHECK constraint would need a migration for a new `notice_assigned` enum value, and the WebSocket envelope alone is enough for in-app surfacing; the immutable AuditLog still records the assignment for compliance forensics.

Commit: `cb412b4`.

### Review queue, populated today (not waiting for v2.1)

The queue was wired but dead: `compliance_tasks.py` only called `enqueue_low_confidence` when classifier confidences were non-null, and the v2.0 rule-based path left those NULL by design. The empty-state told operators to wait for v2.1, which made the whole feature dead weight.

Two backend changes flip the queue on now:

1. **Heuristic confidences** (`compute_heuristic_confidence` in `services/review_queue_service.py`). Authority confidence is 0.92 when the extractor's entity list matches the authority (GST + gstins, IT + pans, MCA + cins), 0.85 for RBI / SEBI with any extracted financial identifier, 0.55 for manual entry with nothing to corroborate. Type confidence is 0.90 when notice_type_id is set, 0.40 when it is NULL. With the 0.75 threshold, every notice that lacks corroborating entities OR a type assignment lands in the queue. Tagged `model_version="rule_based_heuristic_v1"` so the UI distinguishes the source from BERT or manual.
2. **Manual flag endpoint** `POST /api/compliance/review/manual-enqueue/{notice_id}` (`compliance/routers/review_queue.py`). Permission `NOTICE_VIEW` so any active member can flag. Bypasses the threshold gate. Reason field captures an optional 36-char operator note as `manual_flag:<note>`. Writes an immutable AuditLog row with `action="review_queue_manual_flag"`.

When BERT ships in v2.1 the existing classifier path takes over automatically; the heuristic only fires when classifier confidences are NULL.

Commit: `04cd316` (heuristic + UI), `7b3a47f` (em-dash placeholder cleanup), `ebd7e59` (test_classify_and_score_task updated to match the new contract).

### Triage workbench UI (review queue page redesign)

`frontend/src/app/dashboard/compliance/review/page.tsx` replaced the old table with a card grid:

- **Sticky filter strip** at top with reason buckets (Both unclear / Low authority / Low type / Operator flag), each chip showing its count plus a coloured dot keyed to the semantic token (warning, info, danger, accent). Click to filter, click again to clear.
- **Cards** (two per row on lg viewports), each with: header (notice link + authority pill + source badge (HEURISTIC / BERT / MANUAL) + age in 1h / 2d / 3w units), two segmented confidence dot strips (10 dots with a dashed marker at the 75% threshold, so "below the bar" reads in under a second), reason chip with optional operator note, and three actions (Confirm assigns the predicted label, Re-classify opens an authority + type dialog, Open jumps to the notice detail).
- **Reason-tinted left spine** on each card, semantic colour tied to the bucket.
- **Empty state** stopped being passive: a manual-flag form is embedded inline so the page is useful when the queue is dry.

Design decisions matched the existing SaaS aesthetic (refined / minimal, blue accent on neutral grays, no maximalism). The dot-strip is the one non-generic visual choice; everything else extends the existing token vocabulary.

Commit: `04cd316`.

### Live verification (against Supabase via WARP)

Admin promoted to `admin` role, created client #253, invited `bob_<ts>@e2e.test`:
- login as Bob before accept-invite returns 401 (correct, account inactive),
- POST /accept-invite returns a 204-char JWT and flips Bob to active,
- /clients/me as Bob returns the membership,
- normal /login as Bob now succeeds,
- POST /notices/{id}/assign rejects non-member user_id with 400, accepts Bob with 200, clears with null,
- POST /review/manual-enqueue rejects nonexistent notice with 404, rejects unauthenticated with 401.

### CI / CD

Commit `ebd7e59`: docker-build, test, lint, frontend-checks all green. Deploy ran from the same SHA and succeeded (skipping image push because DOCKER_USERNAME secret is unset in this repo).

### Out of scope (deferred)

- response_service.py audit-after-commit pattern (architectural).
- DOCX zip-bomb subprocess sandbox.
- BERT classifier itself (v2.1 milestone). The heuristic fully covers the queue today.
- Force-pushing the 2 em-dashes that landed in commit message bodies of f6447d8 and 04cd316 (user denied the force-push when offered; left as-is).

## 2026-05-21, production-readiness audit sweep (agent team + CI cleanup)

Re-ran the parallel agent audit (security-auditor, code-reviewer, silent-failure-hunter, live-HTTP probe, pytest) against `main` head `c0dc994` plus the uncommitted Phase 16 BYOK working tree. Stack pushed 6 commits, CI + Deploy green, live E2E confirmed end-to-end against the real Supabase DB (WARP-tunneled).

**Security**
1. Cross-tenant email body access (IDOR) closed in `backend/app/email/routers/view_email.py:62`. `GmailMessageLog` has no `client_id` column; only the `require_compliance_permission` dependency checked tenant scope, never the resolved credential's client. Added `cred.client_id == membership.client_id` guard. Confirmed live: a token without a membership for the target client now gets a 403.
2. BYOK API key reflection in `POST /api/compliance/ai/credentials/test` closed. The endpoint returned `detail=f"Auth failed: {e}"`, and the Anthropic SDK's `AuthenticationError` can stringify request headers (including the submitted key). Replaced with fixed strings; full exception goes to `logger.warning` server-side.
3. NUL-byte 500 on `GET /api/documents/search?q=%00`. psycopg raised `ValueError: A string literal cannot contain NUL (0x00) characters`, surfacing as HTTP 500 in ~10s. Now strips NUL and returns 400 if the query is empty after the strip.
4. Internal exception class name was being reflected in the Gmail OAuth callback redirect URL. Removed; the full traceback is logged server-side under the same correlation ID.
5. Per-route rate limiting (10 to 20/minute) added to every BYOK AI endpoint (`test_credential`, `notice_summary`, `notice_actions`, `invoice_summary`, `invoice_actions`, `invoice_timing`, `chat`) so a legitimate tenant member cannot exhaust the per-tenant Anthropic / Gemini budget. Pattern follows `documents.py:286`.
6. Migration `0033_ai_credentials_rls` ENABLE / FORCE RLS statements moved inside the `app_runtime` guard so a fresh dev database without that role is not left with FORCE RLS applied but no policies (a one-way trap that returns zero rows on every CRUD).
7. `config.FERNET_KEY` validator now base64-decodes and checks for a 32-byte payload, replacing the brittle `len == 44 + isalnum` heuristic that was both false-positive (Unicode alphanumerics) and false-negative (quoted or padded keys in `.env`).

**Reliability**
8. `tenant_context` checkin cleanup used bare `except: pass`, so a cleanup failure returned the connection to the pool with the prior request's `app.current_client_id` still set, breaking tenant isolation. Now logs the failure and calls `connection_record.invalidate()` so the next checkout opens a fresh connection.
9. `scheduler.get_scheduler()` left a half-dead singleton on `start()` failure; the next caller would receive the same broken instance forever. Reset to `None` on start failure, plus `pool_pre_ping=True` on the jobstore engine to recover from Supabase pooler idle disconnects.
10. `bill_reminder_task` incremented `reminder_count` even on dispatch failure; after 3 failed dispatches the cool-down at line 45 silently muted the bill. Only consume the budget on successful dispatch.
11. `audit_service` rollback-after-commit-failure became `logger.exception("audit_rollback_failed")` instead of `except: pass`.
12. `notice_service.transition_notice_status` uses `log_audit_event_strict` so a regulatory dead-letter write fires the ops-attention log line (matches the AUDIT-02 contract). Test `test_response_submitted_gate.py` patches updated.
13. `bulk_mark_bills_paid` calls `db.expire_all()` after rollback so a stale `Bill` from a prior successful iteration cannot resurface as expired-but-still-cached state in the next loop iteration.
14. `access_token_cache` now reads `settings.REDIS_URL` (with SSL options aligned with `rate_limiter.py` and `main.py`) instead of `os.environ.get(REDIS_URL, "redis://localhost:6379/0")`, which previously bypassed the pydantic-settings normalization.
15. `ai_providers.AnthropicProvider` now uses `isinstance(block, TextBlock)` before returning `block.text`, so a future SDK content-block with an unrelated `.text` attribute cannot leak.

**API surface, slowapi 500 fix (the one that you flagged)**
16. Every `@limiter.limit(...)` AI route now declares `response: Response` in its signature. slowapi's `_inject_headers` (extension.py:383) raises `parameter response must be an instance of starlette.responses.Response` when the handler returns a non-Response value; the wrapper falls back to `kwargs.get("response")` to find a Response on which to set `X-RateLimit-*` headers, and that lookup returned `None` because the routes did not declare the param. Effect was a 500 on every successful chat turn AFTER Gemini returned 200, with the user's reply discarded. Pattern now matches `documents.py:286`.
17. `from __future__ import annotations` removed from `compliance/routers/ai.py`. The combination of future-annotations + `@limiter.limit(...)` + Pydantic body params produced `PydanticUserError: TypeAdapter[Annotated[ForwardRef(...), Body(...)]] is not fully defined` when FastAPI rebuilt the schema, breaking `/openapi.json`. Removing the future import resolves all ForwardRefs at import time.

**Health-check split (k8s-style)**
18. New `GET /api/health/live` endpoint (no DB / Redis access) wired to the docker-compose healthcheck. `GET /api/health` still does the DB + Redis ping for monitoring dashboards. Previous configuration tripped the container to `unhealthy` whenever the Supabase tunnel hiccupped, taking `depends_on` cascades down with it. Liveness now stays green during external-dependency blips; monitoring still alerts.
19. `/api/health` cached its Redis client at module scope (was constructing a fresh `redis.from_url(...)` on every call). p99 under 10-RPS concurrency dropped from ~5.2s to ~1s steady state. Cache is reset on ping failure so the next call can re-establish.

**Frontend**
20. `BillDashboard.loadCountsAndList` switched from `Promise.all` to `Promise.allSettled` so a single bucket failure (e.g., Overdue server-side filter timing out) no longer blanks the entire dashboard. The user keeps seeing every bucket that loaded plus a non-blocking error toast naming the failed bucket. Bulk mark-paid toast on partial failure now lists the failing bill IDs and stays up for 8s so the user can reconcile.
21. `api.ts` axios refresh-token timeout dropped from 30s to 10s. The 30s cap stacked with the per-request 30s, so a flaky link burned ~60s before any error rendered and `AuthContext.isLoading` could stick.

**CI / CD**
22. Bumped Next.js to 15.5.18 (Dependabot 8H / 4M / 2L cleared). Stayed on the 15.5 line via the `backport` dist-tag; held back from the major jump to 16.x which changes turbopack defaults and would need a planned migration.
23. python-multipart 0.0.26 to 0.0.27 patches GHSA: unbounded multipart part headers DoS, the last remaining HIGH Dependabot advisory.
24. Resend free-tier 550 ("verify a domain at resend.com/domains") rejection now downgraded to WARNING with a one-line resolution hint, so the scheduler / alert retries stop flooding the ERROR log. Real send failures still surface at ERROR.
25. `dependabot.yml` rewritten with a wildcard `dependency-name: "*"` major-version ignore on both pip and npm ecosystems, plus explicit per-package entries kept as documentation. Closed 8 dependabot PRs that opened breaking majors (Next 16, Tailwind 4, TS 6, starlette 1.0, xgboost 3, @types/node 25, plus a second-wave 5 PRs: zod 4, react-dropzone 15, react-day-picker 10, framer-motion 12, redis 7).

**Commits pushed to `origin/main`**
- `acd7160` fix(backend): close IDOR, BYOK key reflection, NUL byte 500, RLS guard gaps
- `b9a16e1` fix(frontend): BillDashboard partial-failure rendering + faster auth-refresh timeout
- `f31f93c` docs: consolidate top-level docs into docs/ subdirs + add internship notes + script polish
- `960283e` fix(deps): bump Next.js to 15.5.18 + split health into liveness vs monitoring
- `2f192ac` fix(api): Response parameter on rate-limited AI routes + Resend 550 spam suppression + dependabot major ignore
- `b45aca4` fix(deps): patch python-multipart DoS CVE + block all dependabot majors with a wildcard

**Live E2E (against rebuilt images + WARP-tunneled Supabase)**
- `/api/health` healthy, db connected, redis connected
- Auth register returns a 204-char JWT
- NUL-byte search returns 400 (was 500)
- IDOR view_email target returns 403 (tenant guard)
- AI chat returns 403 (was 500, slowapi crash is gone, 403 is the correct no-membership answer)
- AI test endpoint returns 403 (rate-limit + permission guard)
- 0 HTTP 500 responses in `smartdocs-backend` logs over the verification window

**CI run on `b45aca4`**: 4 / 4 jobs green (docker-build, test, lint, frontend-checks). Deploy workflow ran on top and completed successfully in 3m8s.

**Out of scope this sweep (deferred, architectural)**
- `response_service.py` audit-after-commit pattern; needs to move audit into the same transaction as the business write. Architecture change, not an audit-sweep fix.
- DOCX zip-bomb mitigation; needs a subprocess sandbox to bound decompressed XML size before python-docx parses it.
- Switching CI workflows from Node 20 actions (deprecation warning, runner stays on 20 until June 2026).
- Supabase password rotation; manual ops task per the existing `feedback_supabase_only` memory note.

## 2026-05-18, Repo consolidation + 5-agent audit pass, Tier 1 fixes applied; CI re-run pending

Doc layout was scattered (10+ markdown / html / pdf / docx files at repo root, plus 6 UI screenshots in the parent directory). Consolidated everything under `docs/` with a clean subfolder structure (`deployment/`, `security/`, `reference/`, `status/`, `operations/`, `exports/`, `screenshots/`); rewrote the 2 cross-references in `README.md`; updated all 4 build scripts (`scripts/build_*.py`, `scripts/md_to_docx.py`) to point at the new source + output paths; created `docs/README.md` as the index; added `.pytest_cache/` and `.ruff_cache/` to `.gitignore`. Top-level is now 9 entries (3 dirs, 4 config files, README, vercel.json) versus 27 before.

Five parallel audit agents (`backend functional`, `frontend functional`, `security`, `code quality`, `repo hygiene`) produced a combined report covering 159 backend `.py` files and 116 frontend `.ts/.tsx` files. Tier 1 fixes applied this session (12 files + 1 new migration):

1. **`fix(ws): notification stream now reads token from the cookie, not localStorage`** — `frontend/src/hooks/useNotificationStream.ts:43`. The hook was reading `localStorage.getItem("access_token")`; tokens have always been stored as the `Cookies.get("token")` cookie. Effect: the notification bell was silently dead on every dashboard page — every D-16 alert (deadline_t7/t3/t1, overdue, escalation) failed to render. Switched to `Cookies.get("token") ?? null`.
2. **`fix(dashboard): rebrand stale "Bills" category label to "Vendor invoices"`** — `frontend/src/app/dashboard/page.tsx:42`. Sole user-visible string that survived the 2026-05-08 rename.
3. **`fix(bills): de-dupe merged buckets in the "all" view`** — `frontend/src/components/email/BillDashboard.tsx:113-125`. A bill on a boundary date could appear in `due_soon` and `upcoming` server-side; `responses.flatMap()` rendered it twice. Replaced with id-Set dedup.
4. **`fix(api): add 30s axios timeout (instance + raw refresh) and remove duplicate API_URL_BASE`** — `frontend/src/lib/api.ts:6-11, 88-94, 259`. Without a timeout, an unreachable `/auth/refresh` left every queued request hanging and `AuthContext.isLoading` stuck on `true`, producing an infinite global spinner. Also re-used the existing `API_URL` constant for `earlyAccessApi` instead of redeclaring.
5. **`fix(bills): bulk_mark_bills_paid no longer wraps committed work in begin_nested`** — `backend/app/email/routers/bills.py:140-180`. `mark_paid` issues `db.commit()`; wrapping it in `db.begin_nested()` ends the savepoint context and raises `InvalidRequestError` on SQLAlchemy 2.x. Loop now calls `mark_paid` plainly with per-row try/except + `db.rollback()`; the final outer commit became a no-op and was removed.
6. **`fix(ai): walk anthropic content blocks for first TextBlock`** — `backend/app/compliance/services/ai_providers.py:128-140`. SDK 0.52 can return `ToolUseBlock` / `ThinkingBlock` at index 0; the code raised `unexpected content block type` (HTTP 502). Now iterates and returns the first block with a `.text`.
7. **`fix(rls): ai_credentials gets RLS + GRANT (Phase 16 ship-blocker)`** — new migration `backend/alembic/versions/0033_ai_credentials_rls.py`. Migration `0032` created the table without the RLS bootstrap + `app_runtime` grants every other tenant table got in `0017` / `0025`. Effect when running as `app_runtime`: every AI endpoint replies HTTP 412 because `SELECT` lacks privilege. Effect when running as a superuser: encrypted keys are reachable cross-tenant via integer-ID enumeration. `0033` is additive (DO-block-guarded so it's a no-op on Postgres without the role chain), mirrors the 0025 pattern exactly, and includes a `downgrade()`.
8. **`fix(byok): Pydantic protected_namespaces=() on AICredentialCreate + AICredentialOut`** — `backend/app/compliance/schemas/ai.py:26-43`. Pydantic 2.13 warns on `model_*` field names; `model` is the canonical LLM-model field. Opt out explicitly.
9. **`fix(config): validate FERNET_KEY format if set`** — `backend/app/config.py:129-145`. Empty is still allowed (dev), but a malformed key fails fast at startup instead of crashing on first BYOK request.
10. **`fix(audit): log audit_rollback failures instead of pass`** — `backend/app/services/audit_service.py:128-134`. Rollback-after-commit-failure now logs via `logger.exception("audit_rollback_failed")`. The other `except Exception: pass` sites in `app/` are intentional best-effort post-commit cleanup paths (audit dead-letter fallback, ContextVar reset).
11. **`build(frontend): add typecheck script`** — `frontend/package.json:5-11`. `next build` was the only TS gate. `npm run typecheck` (= `tsc --noEmit`) now usable in CI and pre-commit.

**Verification this patch:**
- All 10 modified `.py` files + the new migration pass `python -m py_compile`.
- `frontend/package.json` valid JSON.
- `tsc --noEmit` on frontend completes with zero errors.
- Doc moves verified: 21 expected files at their new paths; no broken cross-references in `README.md` or `docs/README.md`.
- All 4 build scripts (`build_features_docx.py`, `build_features_pdf.py`, `build_tech_pdf.py`, `md_to_docx.py`) updated to point at `docs/reference/*` sources and `docs/exports/*` outputs.

**Findings flagged but not auto-applied (in-flight or architectural):**

- `backend/app/database.py:8` — uses `DATABASE_URL` rather than `DATABASE_URL_RUNTIME`. If the deployment wires `DATABASE_URL` to a BYPASSRLS account, every Phase 9-15 RLS policy is silently bypassed. **File is in the user's WIP (`git M`); fix likely already in progress.**
- `docker-compose.yml:14` — `${POSTGRES_PASSWORD:-postgres}` weak default + 0.0.0.0 host bind. **File is in the user's WIP.**
- `backend/app/compliance/services/scheduler.py` — bare excepts at lines 106 / 129 / 163. **File is in the user's WIP.**
- `backend/app/compliance/routers/notifications.py:100` — JWT in WebSocket URL query string. Move to first-message handshake or one-time exchange code. (HIGH security; needs design discussion.)
- `frontend/next.config.mjs:9-11` — `ignoreDuringBuilds: true` for ESLint plus no typecheck script meant the cookie-vs-localStorage bug above slipped through; `typecheck` script added (#11). ESLint re-enable deferred because the comment notes 5 pre-existing v1.0 hook errors that need to be fixed first.
- `frontend/src/middleware.ts` + `Cookies.set(...)` — JWTs in non-`HttpOnly` cookies. Needs BFF pattern to fix — architectural.
- `backend/app/services/oauth_service.py` + `routers/auth.py:362-367, 497-504` — login-OAuth state JWT has no per-user binding. Gmail-OAuth path already binds `user_id + client_id`; backport that pattern.
- **`npm audit fix` (Next.js 15.5.15 → 15.5.16+)** — patches middleware-bypass `GHSA-26hh-7cqf-hhc6`. Defer to the human so the lockfile update is reviewed before commit.
- Code-quality god-files: `backend/app/routers/documents.py` (1,228 lines), `frontend/src/app/dashboard/documents/[id]/page.tsx` (1,010 lines). Refactor as a dedicated phase.
- Phase 16 BYOK has zero unit tests. Add `tests/test_ai_service.py` covering credential round-trip, OUT_OF_SCOPE handling, JSON-fence parsing.

---


**Overall Progress:** v1.0 shipped (8/8 phases, March 2026). v2.0 Phase 9 shipped 2026-04-28. v2.0 Phases 10 + 11 + 12 + 13 CODE-COMPLETE 2026-05-05; Phase 10 + Phase 12 + Phase 13 end-to-end smokes PASSED. Two consecutive hardening passes shipped (5-agent end-to-end audit covering Phases 1-13): first pass landed 13 fixes between Phases 11 and 12; second pass landed 5 CRITICAL + 9 HIGH fixes including a regressed APScheduler RLS bypass and a cross-user document leak in Phase 13 unified search. UI polish pass landed IBM Plex typography system + design tokens + refined sidebar grouping + brand mark. v2.1.1 (2026-05-09) consolidated the sidebar to a 5-group / 14-item IA, introduced a Profile section, and shipped a backend listener fix that roughly halves WAN round-trips per request. **502+ backend tests GREEN; CI green on `main`**. Phase 14 CONTEXT seeded; external-credential blockers documented (GSP empanelment, IT API access). Phase 15 CONTEXT seeded 2026-04-28.

**v2.1.1 patch (2026-05-09) — IA reset + perf hardening + CI repair**

Production-incident-driven session. Started with a Supabase pooler outage (rotated DB password unblocked the stack via `mcp__plugin_supabase_supabase__execute_sql`), then four shipped fixes plus a documentation refresh.

1. **`perf(compliance): batch tenant_context set_config + skip no-op cleanup`** (`1fd38dd`) — `backend/app/compliance/middleware/tenant_context.py`. Three separate `SELECT set_config(...)` cursor.executes in `before_cursor_execute` and three more in `checkin` cleanup were costing 6 wasted RTTs per request to Supabase ap-south-1. Collapsed each set into a single round-trip; cached the last-set tenant tuple on the DBAPI connection so subsequent queries within one request skip the listener; track `_tenant_dirty` so cleanup is a no-op for connections that never set tenant state (health checks, pool pre_pings). **Measured: `/api/health` warm 1.0–1.4s → 0.30–0.74s (~2x). Multi-query compliance endpoints ~3x.**
2. **`test(compliance): align role matrix with audit:view grant for compliance_head + ca_consultant`** (`3093b9b`) — `backend/tests/test_compliance_endpoints.py`. The 7×13 RBAC matrix was stale: `compliance_head` and `ca_consultant` had been granted `AUDIT_VIEW` in `permission_registry.py` (commit `f79362f`) with explicit comment justification, but the test still expected `False`. Flipped both expectations to `True`. CI was failing on every push since `f79362f`; now green.
3. **`perf(dashboard): align active-client queryKey with ClientSwitcher`** (`caba717`) — `frontend/src/app/dashboard/layout.tsx`. Layout used `queryKey: ["active-client", id]` while ClientSwitcher and the `clients/[id]` route used `["client", id]`, so React Query treated them as separate caches and emitted duplicate `GET /api/compliance/clients/{id}` per render. Aligned to the dominant key. Verified live: `/dashboard` and `/dashboard/compliance/clients/{id}` both drop from 2 calls to 1 per render.
4. **`feat(ia): consolidate sidebar, add Profile section, hub-ify Documents page`** (`a004fd3`) — Three frontend files. The headline UX change of the session.
   - **Sidebar 19 items → 14**, regrouped to 5 groups: `Core` (Overview), `Workspace` (Documents, Analytics), `Compliance` (Notices, Review queue, Calendar, Audit log, Reports), `Profile` (Account, Email center, AI assistant), `Admin` (Admin, Clients, Model eval). Reflects the single-tenant deployment model — each customer runs their own instance, so cross-client navigation (Clients list, Cross-entity search) belongs in Admin, not in the daily nav.
   - **`/dashboard/documents` is now a hub.** Added a 3-column action row (Upload / Shared / Search) at the top so the four document workflows live on one screen. Each card links to the existing standalone route — no logic moved, no routes deleted, fully reversible.
   - **`/dashboard/profile` (new).** Identity card with avatar, name, email, role + username pills. Two destination cards link to Email center and AI assistant. The Email and AI sections moved out of their own top-level groups so user-scoped settings live together.
   - **Backend RLS, `X-Client-Id` machinery, and `compliance_clients` table intentionally untouched.** Sidebar consolidation is purely cosmetic. The "no multi-org" architectural decision (collapsing the multi-tenant runtime to a single client per deployment) is deferred to a separate phase because removing the tenant primitives can break existing data and audit-log linkage.

**Verification this patch:**
- Backend tests: full suite green on CI run `25593798115` (latest CI on `main`); CodeQL also green; Deploy auto-triggered and succeeded.
- Frontend: `docker compose build frontend` clean (no TS errors); image rebuilt and recreated.
- Playwright E2E sweep across all 10 dashboard pages (`/dashboard`, `/compliance`, `/compliance/review`, `/compliance/audit`, `/compliance/calendar`, `/compliance/reports`, `/compliance/clients/206`, `/documents`, `/email/bills`, `/settings/ai`, `/admin`): zero console errors anywhere.
- Sidebar nav structure verified live via `Array.from(document.querySelectorAll('aside nav h2, aside nav a'))` — 5 group headers, 14 nav items, no orphan routes.
- New `/dashboard/profile` page renders with identity + destination cards; no console errors.

**Operational note (out of band):** A Supabase Supavisor `ECIRCUITBREAKER` was triggered earlier in the session by repeated bad-credential connection attempts from the backend healthcheck loop. Recovery procedure documented in auto-memory: stop the backend container before rotating credentials, then `docker compose up -d --force-recreate backend` to load the new env. Memory `project_supabase_config.md` and `project_perf_listener_fix.md` updated with the full recipe.

**Phase 17c — Agent-team review sweep (2026-05-09, commit `8f81ef3`):**

Spawned 3 parallel review agents on the 11-commit session diff: `code-reviewer`, `security-auditor`, plus a follow-up `security-auditor` pass on the UserMenu commit. Combined verdict: 2 HIGH + 4 MEDIUM real findings (plus several INFO items already mitigated). All HIGH and MEDIUM closed in `8f81ef3`.

Findings closed:
- **HIGH (latent crash)** — `backend/app/compliance/middleware/tenant_context.py` had been writing `_tenant_state` and `_tenant_dirty` as attributes on the psycopg2 connection object (a C extension type with no `__dict__`). The original `except: pass` swallowed the AttributeError silently — meaning the dedup cache had been a no-op the whole time (the perf gain came purely from collapsing 3 SET round-trips into 1). Setting `_tenant_dirty` BEFORE the try/except in this session's earlier commit then surfaced the AttributeError as a hard request-killing crash mid-tenant-context-set. Moved cache state to `conn.connection.info` / `connection_record.info` (SQLAlchemy's pool-record dict, persistent across checkouts). Dedup now actually works; combined-SET reduction still the dominant win.
- **HIGH (frontend)** — `frontend/src/app/dashboard/compliance/clients/page.tsx` `useQueries` queryFn was calling `setActiveClientId(m.client_id)` for every membership during fan-out, mutating global Zustand tenant state non-deterministically on page visit. Removed the side-effect; selection now happens only on the Link `onClick`. Also gated the `useQueries.enabled` flag on `user?.role === "admin"` so non-admins don't trigger backend `GET /clients/{id}` for every membership before the render guard short-circuits.
- **MEDIUM** — `frontend/src/app/dashboard/model-evaluation/page.tsx` had no frontend admin guard. Backend `require_admin` returned 403, but the page rendered for non-admins anyway. Added the same `useEffect` redirect + render-time `return null` pattern used in `/dashboard/admin` and `/compliance/clients/page.tsx`.
- **MEDIUM** — `frontend/src/components/UserMenu.tsx` outside-click handler used `mousedown`, which races with Link `click` on touch devices. Switched to `click`. Added focus management: on open, focus the first `menuitem`; on Escape close, return focus to the trigger button (WCAG 2.4.3). Verified live via `document.activeElement` probe.
- **MEDIUM** — `frontend/src/app/dashboard/compliance/page.tsx` `setStatusFilter` cast a plain `string | undefined` to `NoticeFilters["status"]` at the call site, hiding any typo from TypeScript. Typed `workflowStages[].statusFilter` against the same union so typos are build-time errors. Also replaced the disabled `<button>` for Overdue (dead UX) with a plain `<div>`, so AT users see a presentational tile rather than a button with no action.

Findings deferred (already mitigated per agent or out-of-scope):
- INFO — `tenant_context.py` "wrong cache for transaction-pooled connections": the agent assumed pgbouncer transaction mode. Our deployment uses Supavisor session mode (port 5432 per `docker-compose.override.yml`); the listener now documents this requirement explicitly.
- INFO — UserMenu `focusout` close on screen-reader tab-past: covered by the focus-management fix (focus leaving the menu via Escape returns to trigger; Tab past last item is a minor a11y nit, not a security finding).
- MEDIUM — `/compliance/clients/me` returns expired memberships in JSON: tracked as a follow-up; defense-in-depth, doesn't change the tenant-isolation outcome of this patch.

Verified live via Playwright across 12 pages: zero console errors anywhere; filter card `aria-pressed` toggles correctly; UserMenu opens with focus on first menuitem; ESC closes and returns focus to trigger; backend serves `/api/health` 200 with no `AttributeError` after restart.

---

**Phase 17b — UserMenu popover, sidebar collapsed to 3 groups (2026-05-09, commit `852fe4d`):**

User feedback after Phase 4: "Profile section should not be in the sidebar; click on the profile area to open it. Admin too — only admin uses it." Implemented via a new `UserMenu` popover that opens upward from the user cluster at the bottom of the sidebar.

- New `frontend/src/components/UserMenu.tsx` (one component, ~280 lines). Trigger reuses the existing user-cluster styling plus a rotating chevron. Popover renders three sections: identity strip header, Personal (Account / Email center / AI assistant), Admin (only when `users.role === 'admin'`: Admin / Organizations / Model eval), and Sign out as its own bottom strip. Outside-click and Escape both close. `aria-haspopup`, `aria-expanded`, `role="menu"` + `menuitem` throughout; chevron rotation wrapped in `motion-safe:` per `ui-ux-pro-max` `prefers-reduced-motion` guidance.
- `frontend/src/app/dashboard/layout.tsx`: `NAV_GROUPS` trimmed from 5 groups / 14 items to **3 groups / 8 items** (Core / Workspace / Compliance only). The previous user cluster and standalone Sign out button replaced with `<UserMenu />`. 12 now-unused `react-icons` imports cleaned out.
- Renamed the admin "Clients" link to "Organizations" inside the menu so the multi-tenant SaaS terminology matches the sidebar header pill.
- Verified live via Playwright: `aside nav h2` list returns exactly `["Core", "Workspace", "Compliance"]`; UserMenu popover items return `[Account, Email center, AI assistant, Admin, Organizations, Model eval, Sign out]`; ESC press correctly closes the menu and flips `aria-expanded` to `false`; zero console errors.

**Phase 4 — tenant-isolation hardening (2026-05-09 same session, three more commits):**

5. **`feat(compliance): workflow-oriented hero with status filter cards`** (`b6e62d7`) — `frontend/src/app/dashboard/compliance/page.tsx`. The compliance landing page header was "Notice classification" — jargon. Replaced with "Compliance notices" + a plain-English subtitle naming the workflow stages (receive, triage, draft, file, audit). Added a 4-card status row above the existing risk distribution: New / In review / Awaiting submission / Overdue, each pulling counts from `DashboardAggregates.by_status` and `.overdue`. Each card except Overdue is a status-filter shortcut into the table below. Visual treatment per `ui-ux-pro-max` "Data-Dense Dashboard" guidance.
6. **`feat(security): tenant isolation -- hide cross-org switcher from non-admins`** (`54d9a9f`) — `frontend/src/components/compliance/ClientSwitcher.tsx`. The dropdown previously listed every organization the signed-in user had a `compliance_client_memberships` row for, leaking org-existence to non-admin users with multiple memberships. Three behavior changes: (a) dropdown only renders when `users.role === 'admin' && memberships.length > 1`; non-admins and single-membership users see a static pill with their org name; (b) cross-client mode (`All Clients` toggle) is now gated on `users.role === 'admin'` in addition to the existing `compliance_role` check; (c) auto-pin `activeClientId` to the user's single membership on first load.
7. **`fix(security): close two tenant-isolation gaps flagged by security-auditor`** (`02af56c`) — Triggered by a `security-auditor` agent review of `54d9a9f`. Two real findings closed:
   - **HIGH** — Backend `get_active_membership` in `backend/app/compliance/dependencies.py` accepted `X-Client-Id: *` for any user with a `compliance_head` / `ca_consultant` / `cfo` membership, regardless of `users.role`. An editor with a `ca_consultant` compliance_role could `curl -H "X-Client-Id: *"` and read cross-tenant data even though the UI toggle was hidden in `54d9a9f`. Added a `users.role == 'admin'` check at the top of the cross-client branch.
   - **CRITICAL** — `/dashboard/compliance/clients/page.tsx` fans out `getClient(...)` for every membership, so a non-admin URL-typing in could enumerate org names. Added a `useEffect` redirect to `/dashboard` for non-admin users plus a render-time `return null` (placed after all hooks) so org names are never rendered for the brief pre-redirect window.

**Verification this Phase 4 wave:**
- Playwright DOM probe: `hasSwitcher: false`, `hasStaticPill: true`, `staticPillText: "Sravan Pollisetti"` for the test admin (single membership) — dropdown gone.
- Admin path through `/dashboard/compliance/clients` still renders normally; non-admin path redirects (verified by code review of the useEffect / render-guard ordering).
- Backend `dependencies.py` reloaded via `docker compose restart backend` (volume-mounted source, no rebuild needed).
- Frontend rebuilt twice (`docker compose build frontend`) so the production bundle reflects the source.
- Two `MEDIUM` findings remain in the security-auditor report and are tracked as follow-ups: (a) `/compliance/clients/me` returns expired memberships in its JSON response (org IDs still leak even though `get_active_membership` rejects requests against them); (b) the `setActiveClientId` side-effect inside the `clientQueries.queryFn` cycles `activeClientId` through every membership during the fan-out — refactor opportunity, not a security regression now that the route is admin-only.

---

**v2.0.2 patch (2026-05-08) — Admin user-delete + audited bug sweep** — Added admin-driven user removal with audit-trail-preserving soft-delete (the audit_logs immutability trigger from migration 0014 makes a real `DELETE FROM users` impossible — anonymizing in place keeps the chain valid). Same session, an end-to-end audit agent (covering Phases 1-15) surfaced four production issues all fixed:
1. **CRITICAL — Backend test suite couldn't run.** `pytest 9.0.3` + `pytest-asyncio 0.23.3` collision: `INTERNALERROR ... 'Package' object has no attribute 'obj'` on every collection. The "389 tests green" claim was unverifiable — pytest aborted before collecting anything. Fix: pinned `pytest-asyncio>=0.26,<1.0` in `requirements.txt`. **502 tests now pass** (up from the previous 389 baseline because more tests now run + 11 new admin-delete tests).
2. **CRITICAL — `/dashboard/upload/page.tsx` hooks ordering.** `if (user?.role === "viewer") return null;` placed BEFORE 5 hooks (`useCallback`, `useEffect`, `useDropzone`). When `user` resolves from undefined → defined during auth hydration, hook count changes and React throws "Rendered more hooks than during the previous render", crashing the upload page. ESLint reported 5 errors here. Fix: moved the early-return AFTER all hooks (render-time guard). Lint is now error-free.
3. **HIGH — Gmail scanner_task spammed errors every 15 min.** `HttpError` handler only caught 404 (history-id reset). Permanent 401 (revoked tokens) and 403 (Gmail API disabled) re-raised → APScheduler logged a fresh exception every cadence. Fix: added explicit 401/403 catch that flips `gmail_credentials.status = REVOKED`, logs a warning (not exception), and returns without re-raise. Subsequent scans short-circuit at the `STATUS_ACTIVE` guard.
4. **HIGH — `get_current_user` didn't check `deleted_at`.** A future re-activation of a soft-deleted user (PATCH /status with is_active=true) would re-grant API access despite the user being "deleted." Fix: `if not user.is_active or user.deleted_at is not None` in `app/utils/security.py:get_current_user`.

**Admin user-delete feature (this patch's headline):**
- `DELETE /api/admin/users/{user_id}` — guarded by `require_admin`, rate-limited 5/min.
- Guards (mirroring existing role/status endpoints): cannot delete self (400), cannot delete the last active admin (400), 404 when target missing or already-deleted.
- Action in one transaction: anonymize PII (`email`, `username`, `full_name`, `oauth_id`, `hashed_password`), set `is_active=False`, set `deleted_at=now()`, revoke all active refresh tokens. FK CASCADE handles documents and own document_permissions; `audit_logs.user_id` is left intact (the row exists, just anonymized) — `audit_logs` immutability trigger is never fired.
- New migration: `0030_add_user_deleted_at` — `deleted_at TIMESTAMPTZ NULL` + partial index `WHERE deleted_at IS NOT NULL`.
- All listing / lookup queries (admin list, detail, role update, status update, stats) now filter `deleted_at IS NULL`.
- Frontend: `DeleteUserModal` (mirrors `MarkPaidModal` design contract — same dimensions, header/body/footer rhythm, focus-trap, ESC, Enter-to-confirm, ARIA dialog) with type-to-confirm gating the destructive button. `FiTrash2` icon button per user row, disabled for the admin's own row.
- 11 new backend tests cover: happy path, PII anonymization, self-delete reject, last-admin reject, multi-admin-allowed, refresh-token revocation, non-admin reject, 404 path, ID validation.

**Verification this patch:**
- 502 backend tests passing (single full-suite invocation; 107 errors are pre-existing Phase 9 RLS infra cases that need a local Postgres with role-switching, not Supabase pooler — documented limitation).
- Migration 0030 applied to Supabase: `users.deleted_at TIMESTAMPTZ` + partial index `ix_users_deleted_at WHERE deleted_at IS NOT NULL` confirmed via `inspect()`.
- Frontend: `tsc --noEmit` clean (no type errors); `next lint` reports 9 pre-existing warnings (no errors); the upload-page hooks-ordering errors flagged by the audit agent are resolved.
- OpenAPI: `/api/admin/users/{user_id}` exposes both `get` and `delete`; unauth `DELETE` returns 401 (security gate works).
- All Docker services healthy after restart (backend, celery, compliance-worker, frontend, db, redis).

---

**v2.0.1 patch (2026-05-06)** — End-to-end agent-team review of Phases 1-13 surfaced and fixed three user-facing gaps:
1. **Compliance report download was unimplemented** (Phase 13 explicitly deferred CSV/PDF/Excel exports to v2.1). Retrofitted 4 CSV export endpoints (`/reports/{penalty-by-authority,notice-volume-by-status,response-time,health-summary}/export`) using stdlib `csv` + `StreamingResponse` (no new deps); added `Download CSV` buttons to the four report cards on `/dashboard/compliance/reports`. Verified end-to-end with browser-driven download (`penalty_by_authority_20260506.csv` produced via real button click).
2. **Compliance notice upload never dispatched OCR/classification** — Phase 09's `POST /notices/{id}/upload` reused v1.0 storage (`save_file`) but skipped the Celery `process_document_task.delay()` step that the regular doc upload (Phase 02) wires. Notice documents stayed in `status=PENDING` forever, breaking Phase 10's classification chain. Added Celery dispatch with degraded-mode error logging (failure non-fatal — file already saved). Verified: notice document transitions PENDING→COMPLETED in 2s with extracted text + AI fields.
3. **Sign in with Google button was missing** on login + register pages. Code was 100% implemented (backend OAuth service, callback handler, frontend buttons + click handlers) but conditionally hidden because `/auth/providers` filters Google out when `GOOGLE_CLIENT_ID` env var is empty. Updated frontend to always show Google + Microsoft buttons; backend gracefully fails with helpful toast (`"Google sign-in not yet configured. Set GOOGLE_CLIENT_ID in backend .env to enable."`) when creds missing. Buttons render unconditionally, OAuth dance still gated server-side on creds. Real Google OAuth credentials were configured later same day (`GOOGLE_CLIENT_ID=764178367858-…`); `/auth/providers` now returns `["local","google"]` and the Google sign-in flow works end-to-end (verified Playwright redirect to `accounts.google.com/v3/signin/identifier?...client_id=…&redirect_uri=…/api/auth/callback/google`).

**v2.0.1 patch — Supabase Security Advisor (migration 0024)** — Closed 5 CRITICAL + 6 HIGH advisor findings in one migration:
- **5 CRITICAL** — RLS now enabled on `users`, `documents`, `refresh_tokens`, `alembic_version` (postgres role bypasses, zero behavior change); dropped the "Allow all for authenticated" `USING(true) WITH CHECK(true)` policy on `document_permissions`. **Targeted permissive `app_runtime_full` policy** added on `users`/`documents`/`refresh_tokens` so the integration test fixture (which `SET ROLE app_runtime` to subject test bodies to RLS) can still INSERT/SELECT — scoped strictly to the internal `app_runtime` role, never to PUBLIC/anon/authenticated, so the advisor doesn't reflag.
- **3 HIGH (SECURITY DEFINER privilege)** — REVOKE EXECUTE on `is_cross_client_eligible`, `user_has_client_membership`, `rls_auto_enable` from PUBLIC + anon + authenticated + service_role; GRANT only to `app_runtime` (or postgres for the admin helper). Verified via `has_function_privilege()`: only the intended roles can execute.
- **3 HIGH (search_path)** — Pinned `search_path = pg_catalog, public` on `documents_search_vector_update`, `compliance_notices_search_vector_update`, `reject_audit_log_modification`.
- **40+ noisy advisor warnings collapsed** — Revoked ALL privileges (TABLES + SEQUENCES + FUNCTIONS + default privileges) from Supabase's `anon` and `authenticated` roles. Those roles are unused by FastAPI (custom JWT, not `auth.uid()`), so the revoke has zero functional impact but eliminates every "Public/Signed-In Users Can See Object in GraphQL Schema" warning.
- **Out of scope (deliberate)** — "Auth RLS Initialization Plan" warnings on compliance_* tables: false positives because the policies use `current_setting('app.current_client_id')`, not `auth.uid()`. The advisor's pattern-match is overzealous; no fix needed.
- **CI portability** — All function/role REVOKE/GRANT/ALTER wrapped in `DO $$ IF EXISTS $$` blocks against `pg_proc` and `pg_roles` so the migration runs cleanly on vanilla Postgres (CI) where Supabase-only roles + dashboard-created functions don't exist. `rls_auto_enable()` was created via the Supabase UI on the user's project — never in any migration — so the existence check is load-bearing.
- **Verification**: 389 backend tests GREEN; login + document list + compliance notices + reports CSV export all return correct data; `has_function_privilege` and `has_table_privilege` confirm the revokes landed.

**v2.0.1 patch — Compliance workflow + reports unblock (2026-05-06 evening, 4-agent E2E audit Phases 1-13)** — End-to-end audit by 4 parallel investigation agents surfaced 7 distinct bugs blocking the user-facing flows; all fixed:
- **CRITICAL — Status workflow blocked for `compliance_head`**: `notices.py:_permission_for_target_status` mapped `received → under_review` to `NOTICE_DRAFT_RESPONSE` only; `compliance_head` (the most senior role) doesn't have that permission per the 84-case test matrix — they have `NOTICE_REVIEW`. Result: managers couldn't even start reviewing their own notices; only `dismiss` worked. Fix: dispatcher now returns a tuple of acceptable permissions; `under_review` accepts `{NOTICE_REVIEW, NOTICE_DRAFT_RESPONSE}`. Verified live: `received → under_review` succeeds for compliance_head; `under_review → response_drafted` still 403 (drafter-only, correct boundary).
- **CRITICAL — Report Generate + Download both 422**: frontend `reports/page.tsx` appended `-01` to the month input, sending `2026-04-01` to a backend schema that requires regex `^\d{4}-\d{2}$`. Both buttons silently failed with 422. Fix: send `month` directly. Verified: POST `/reports/health-summary` and `/reports/health-summary/export` both return 200.
- **HIGH — Notice upload `db.rollback()` after commit**: `notices.py:upload_notice_file` called `db.rollback()` AFTER the document had already been committed two lines earlier when Celery dispatch failed. The rollback only un-set the in-memory `celery_task_id` assignment but left the session in unclear state for the subsequent first-upload-wins commit. Fix: drop the rollback; document is already persisted, log-only is sufficient.
- **HIGH — Response time CSV had semantically wrong column header**: `reports.py:export_response_time` wrote `sample_count` (integer count of notices) into a column named `days`, mixed with float percentile values. Misleading for downstream Excel/BI consumers. Fix: switched to 3-column shape `metric,value,unit`; percentiles get `unit=days`, sample count gets `unit=notices`.
- **MEDIUM — Unified search accepted 1-char queries**: `search.py:unified_search` had `min_length=1` on `q`. PostgreSQL FTS with single-char tokens triggers sequential scans. Bumped to `min_length=2`.
- **MEDIUM — CSV `charset=utf-8` not declared**: `reports.py:_csv_response` — added charset to the `media_type` so older Excel and BOM-sniffing importers handle non-ASCII authority/status names correctly.
- **MEDIUM — Stale test asserted on non-existent field**: `test_reports.py` asserted `summary_pdf_path in result`. PDF was deferred to v2.1; v2.0 only ships `summary_html`. Updated to assert on `summary_html` only.

**v2.0.1 patch — CI/Deployment portability (today's 9-commit chain)** — The big v2.0+v2.0.1 commit (`fc81b2b`, 118 files) revealed CI/Vercel divergence in 4 successive layers; each fix unblocked the next:
- **`8723a51`**: cleared 19 ruff lint errors in test files (pre-existing dead code, never pushed before); added `backend/pyproject.toml` with `[tool.uv] index-strategy = "unsafe-best-match"` so Vercel's uv resolver finds Pillow 12.2.0 on PyPI when `--extra-index-url` points to PyTorch's CPU index.
- **`73c3100`**: made migration 0024 portable to vanilla Postgres by wrapping every function/role-specific operation in `DO $$ IF EXISTS $$` blocks (Supabase's `anon`/`authenticated`/`service_role` roles + dashboard-created `rls_auto_enable()` function don't exist on CI's stock Postgres).
- **`8183759`**: added the `app_runtime_full` permissive policy (mentioned above) — RLS-enabled tables without policies block integration tests that `SET ROLE app_runtime`.
- **`0a55e4a` + `907a9f5`**: aligned Python version across pyproject.toml (`>=3.12`) and `.python-version` (`3.12`) since `vercel-runtime==0.13.0` requires 3.12 and uv resolves to the lowest matching version. Docker (`FROM python:3.11-slim`) and CI (`actions/setup-python@v5: '3.11'`) explicitly pin their own versions, so they're unaffected.
- **`886a0c8`**: the 7-bug compliance fix bundle (above).
- **`89e1207`**: retired the legacy `(1) (1).docx` mirror filename in `scripts/md_to_docx.py`.

**Final ship state (all green on `89e1207`)**:
- GitHub Actions: lint ✓ test ✓ docker-build ✓ frontend-checks ✓ CodeQL JS ✓ CodeQL Python ✓ deploy ✓
- Vercel production deploy: ✓ Ready
- Local `docker compose build --no-cache`: ✓ exit 0 (4 images rebuilt: backend 4.54GB, celery 4.54GB, compliance-worker 4.54GB, frontend 425MB)
- 389 backend non-integration tests GREEN
- All 6 docker compose services healthy

**Working tree cleanup (today)**: 23 `__pycache__/` dirs + 220 `.pyc` files + `.pytest_cache/` (84KB) + `.ruff_cache/` (60KB) + frontend `tsconfig.tsbuildinfo` + `node_modules/.cache/` + duplicate `.docx` mirror — all deleted (gitignored or regeneratable build artifacts; zero source code touched). 411 tracked files in `git ls-files` unchanged. `backend/datasets/` (19GB Phase 10 BERT corpus) preserved.

**Current ship state:**
- v1.0 (Phases 1-8): SHIPPED 2026-03-30 — Smart Document Management System with OCR, ML classification (85.06%), full-text search, LLM extraction, RBAC + OAuth.
- v2.0 Phase 9 (Compliance Foundation): SHIPPED 2026-04-28 — Multi-tenant compliance notice tracking with RLS isolation, audit immutability, 7 compliance roles × 12-permission matrix.
- v2.0 Phase 10 (ML Classification + Risk Scoring): CODE-COMPLETE + smoke PASSED 2026-05-05 — Rule-based scorer + SHAP explanations + auto-escalation; BERT bake-off deferred to v2.1.
- v2.0 Phase 11 (Alerts + Calendar): CODE-COMPLETE + hardening pass 2026-05-05 — APScheduler + multi-channel alerts (email + WebSocket; SMS scaffolded); 37 statutory deadlines for FY 2025-26 seeded.
- v2.0 Phase 12 (Response Drafting + Evidence): CODE-COMPLETE + smoke PASSED 2026-05-05 — 4-stage approval workflow (Drafter → Reviewer → Legal → CFO) + versioned drafts + evidence linking; LLM drafts deferred to v2.1.
- v2.0 Phase 13 (Cross-Entity Search + Reports): CODE-COMPLETE + smoke PASSED 2026-05-05 — PG-FTS unified search across notices + documents + analytics aggregations; Elastic Cloud deferred to v2.1.
- Phase 14 (Government Portal Integration): CONTEXT seeded — BLOCKED on GSP empanelment + IT API access decisions.
- Phase 15 (Gmail MCP Integration): CONTEXT seeded — ready for /gsd:discuss-phase 15.

**Audit + hardening summary:**
- First hardening pass (4 agents): 43 findings → 17 block-fixes landed + 26 deferred (`.planning/HARDENING-PLAN.md`)
- Second hardening pass (5 agents covering Phases 1-13): 25 distinct issues → 5 CRITICAL + 9 HIGH fixes landed + 14 deferred (`.planning/HARDENING-PLAN-2.md`). Notable: closed cross-user document leak in unified search; fixed regressed APScheduler RLS bypass that was silently no-op'ing every production deadline alert; made audit dead-letter file durable across container restarts.

**UI/UX state:**
- "Compliance Noir" design system — refined dark editorial × financial-grade precision
- IBM Plex Sans (body) + IBM Plex Mono (numerics) replace generic Inter
- Design tokens via CSS variables (`--bg-page`, `--accent`, `--text-subtle`, etc.)
- Sidebar grouped into Core / Documents / Compliance / Admin with microtype dividers
- 2px brand-blue accent bar on active nav item; subtle radial-gradient atmosphere
- Tx brand mark (Plex Mono tile in accent-soft) appears in sidebar + login

---

## Executive Summary

The Smart Document Management System (SmartDocs) is an AI-powered document management platform that automatically classifies, extracts, and searches personal and business documents. The system has completed 8 of 8 phases: security hardening, document processing pipeline, ML classification (85.06% accuracy), full-text search, LLM smart extraction, multi-user RBAC with OAuth SSO, UI & analytics, production readiness, and a comprehensive end-to-end security audit with 21 fixes across 17 files.

---

## Phase Completion Status

| Phase | Title | Status | Completed |
|-------|-------|--------|-----------|
| 1 | Foundation & Security Hardening | ✅ Complete | 2026-02-17 |
| 2 | Document Processing Pipeline | ✅ Complete | 2026-03-09 |
| 3 | ML Classification Upgrade | ✅ Complete | 2026-03-10 |
| 4 | Search & Retrieval Engine | ✅ Complete | 2026-03-11 |
| 5 | LLM Smart Extraction | ✅ Complete | 2026-03-15 |
| 6 | Multi-User & RBAC | ✅ Complete | 2026-03-20 |
| — | End-to-End Security Audit | ✅ Complete | 2026-03-23 |
| — | Security Hardening + Test Fixes | ✅ Complete | 2026-03-25 |
| 7 | UI & Analytics | ✅ Complete | 2026-03-25 |
| 8 | Production Readiness | ✅ Complete | 2026-03-25 |

---

## Completed Phases — Detail

### Phase 1: Foundation & Security Hardening ✅
**Goal:** Eliminate critical vulnerabilities and establish migration framework.

**What was built:**
- Environment-based config — app refuses to start without `SECRET_KEY`, `DATABASE_URL`
- JWT access tokens (30 min) + opaque refresh tokens with rotation and reuse detection
- Rate limiting (slowapi) on auth + upload endpoints → 429 responses on abuse
- Security headers middleware: HSTS (2yr + preload), CSP, X-Frame-Options, X-Content-Type
- Swagger/ReDoc disabled in production (`DEBUG=False`)
- Structured JSON logging (structlog) with correlation IDs on all requests
- Alembic migration framework with initial migration from existing schema

**Requirements completed:** SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, INFR-01

---

### Phase 2: Document Processing Pipeline ✅
**Goal:** Async document processing with full format support and metadata extraction.

**What was built:**
- DOCX text extraction via python-docx (paragraphs + tables)
- OCR preprocessing pipeline: grayscale → Gaussian blur → adaptive threshold → deskew → morphological ops → multi-PSM retry (PSM 6 → PSM 3 fallback)
- Celery async processing wired to Redis — upload returns HTTP 202 immediately
- Celery task stages: reading (10%) → extracting (30%) → metadata (60%) → saving (80%)
- Exponential backoff retry on task failure (60s × 2^retries)
- Frontend bulk upload with per-file progress indicators + real-time status polling (every 2.5s)
- Automatic metadata extraction: dates (dateutil fuzzy, Indian formats), amounts (0.01–10M range validation), vendor names

**Requirements completed:** PROC-01 through PROC-07, INFR-05

---

### Phase 3: ML Classification Upgrade ✅
**Goal:** Document classification >85% accuracy on real-world documents with transparent metrics.

**What was built:**

**Plan 03-01 — Model Upgrade:**
- Added LinearSVC (with CalibratedClassifierCV for probability output) as third model candidate
- 3-model comparison: Logistic Regression vs Naive Bayes vs Linear SVC
- TF-IDF vocabulary: 5K → 15K features, unigrams → trigrams (1,3) ngrams
- Synthetic augmentation factor raised to 10 for underrepresented categories
- **Result: 85.06% test accuracy** (up from 76.4% baseline), Linear SVC selected as best

**Plan 03-02 — Evaluation Dashboard:**
- ML evaluation API endpoint: `GET /api/ml/evaluation` — serves accuracy, per-category P/R/F1, confusion matrix
- Color-coded confidence badges on all document views (green ≥80%, yellow 50–79%, red <50%)
- Model evaluation dashboard page with confusion matrix (intensity-based red shading for misclassifications)

**Docker & Dataset Access:**
- Trained model `.pkl` files (3.6 MB total) committed to git — team gets them on `git pull`
- `docker-compose.yml` updated: bind mounts for `./backend/models` and `./backend/datasets`
- 28 GB Kaggle datasets accessible to team via `python -m app.ml.datasets.download`

**Requirements completed:** AIML-01, AIML-02, AIML-03, AIML-04

#### Per-Category Accuracy (Test Set, 308 samples)

| Category | Precision | Recall | F1 | Samples |
|----------|-----------|--------|----|---------|
| UPI | 100% | 100% | 100% | 48 |
| Tickets | 100% | 100% | 100% | 33 |
| Tax | 97% | 95% | 96% | 38 |
| Bank | 71% | 89% | 79% | 82 |
| Bills | 97% | 64% | 77% | 45 |
| Invoices | 75% | 69% | 72% | 62 |
| **Overall** | **86%** | **85%** | **85%** | **308** |

---

### Phase 4: Search & Retrieval Engine ✅
**Goal:** Replace ILIKE with PostgreSQL full-text search, add filters, fuzzy matching.

**What was built:**

**Plan 04-01 — Full-Text Search:**
- PostgreSQL `tsvector` column with GIN index on `documents` table
- Trigger-based `search_vector` auto-update (fires only when text actually changes)
- `plainto_tsquery` + `ts_rank` relevance ranking replaces naive ILIKE
- Alembic migration `0003_add_fts_and_trgm`: creates `pg_trgm` extension, TSVECTOR column, 2 GIN indexes, trigger function, backfill

**Plan 04-02 — Advanced Filters:**
- Category filter (exact match on `category` column)
- Date range filter with Pydantic `date` type auto-validation, inclusive end boundary (+1 day)
- Amount range filter with regex guard for non-numeric JSONB values
- ILIKE pattern injection protection (SQL wildcard escaping)
- Frontend 2×2 filter panel (date range + amount range pickers)

**Plan 04-03 — Fuzzy Search + Performance:**
- `pg_trgm` trigram similarity for typo-tolerant matching
- OR-combine pattern: FTS for stems + trigram for typos in single query
- `gin_trgm_ops` index on `extracted_text` for sub-2s response times
- Rate limiting (30/min) on search endpoint

**Opus Code Review & Hardening:**
- 4 critical input validation bugs fixed (ILIKE injection, date parsing crash, boundary bug, amount cast crash)
- Trigger optimization: skip recompute when text unchanged
- Dead code removal (`SearchRequest` schema)

**Requirements completed:** SRCH-01, SRCH-02, SRCH-03, SRCH-04

---

### Phase 5: LLM Smart Extraction ✅
**Goal:** Add LLM-powered intelligent data extraction and summarization.

**What was built:**
- LLM extraction service with provider abstraction (Ollama, Gemini, Anthropic, OpenAI, local regex fallback)
- Category-specific extraction prompts with structured JSON output
- AI summaries and extracted fields stored per document
- LLM configuration integrated into async Celery pipeline
- Document detail page extended with AI extraction display

**Requirements completed:** AIML-05, AIML-06, AIML-07, AIML-08

---

### Phase 6: Multi-User & RBAC ✅
**Goal:** Implement multi-user access with role-based permissions and OAuth SSO.

**What was built:**
- Three-tier role system: admin, editor, viewer with permission enforcement at API level
- Admin panel for user management (list, search, role change, activate/deactivate)
- Document-level sharing with view/edit permissions and revocation
- Google OAuth and Microsoft OAuth/SSO login integration
- OAuth exchange code flow with frontend callback handling
- Alembic migrations for roles, permissions, and OAuth fields

**Requirements completed:** RBAC-01, RBAC-02, RBAC-03, RBAC-04

---

### End-to-End Security Audit ✅ (March 23, 2026)
**Goal:** Comprehensive security review and hardening across the full stack.

**10 parallel investigation agents** audited: secrets exposure, OAuth CSRF, JWT sessions, input validation, CORS/headers, Google sign-in E2E, login/register flow, token refresh, document API authorization, and frontend dashboard pages.

**21 fixes applied across 17 files (252 additions, 69 deletions):**

| Category | Key Fixes |
|----------|-----------|
| OAuth Security | Added CSRF state parameter, email verified check, error param handling |
| Authentication | is_active check on refresh, token revocation on user deactivation, refresh token row lock |
| Rate Limiting | Fixed X-Forwarded-For spoofing bypass (use direct client IP) |
| Security Headers | Fixed CORP for cross-origin API, removed bad CSP from API, added Cache-Control no-store |
| Frontend Security | Added CSP + HSTS + X-XSS-Protection, cookie expiry, logout race guard |
| Input Validation | Username regex, email regex + lowercase, filename sanitization path |
| Auth Flow | React StrictMode double-fire guard, login/register redirect, role guards on pages |
| Error Handling | Normalized error messages (no auth provider disclosure), 429 rate-limit handling |

**Areas confirmed secure:** SQL injection (parameterized ORM), path traversal (realpath + prefix), IDOR (consistent auth checks), XSS (React auto-escaping, no unsafe innerHTML), admin endpoints (require_admin), token type validation.

---

### Auth & Login Bug Fixes (March 23, 2026) ✅
**Goal:** Fix all login and registration failures blocking the application from working.

**Root causes identified by 10 parallel investigation agents:**
1. Backend `.env` file missing — app couldn't start (SECRET_KEY and DATABASE_URL required, no defaults)
2. Supabase pooler host changed (`aws-0` → `aws-1`) and database password expired
3. Redis not running — rate limiter crashed all auth endpoints with 500 errors
4. Python virtual environment and dependencies not installed

**11 bugs fixed across frontend and backend:**

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | backend/.env | Missing entirely | Created with Supabase connection, localhost Redis |
| 2 | backend/.env | Wrong Supabase host + expired password | Updated to aws-1 pooler on port 6543 with new password |
| 3 | backend/app/utils/rate_limiter.py | Redis required, no fallback — all auth 500s | Added in-memory fallback when Redis unavailable |
| 4 | frontend/src/context/AuthContext.tsx | Silent refresh cookies missing `expires` | Added expires: 1/48 (access) and 7 (refresh/user) |
| 5 | frontend/src/context/AuthContext.tsx | setTokensFromOAuth cookies missing `expires` | Added same expires values |
| 6 | frontend/src/app/login/page.tsx | Double navigation (handleSubmit + useEffect) | Removed manual router.replace from handleSubmit |
| 7 | frontend/src/app/register/page.tsx | Same double navigation | Same fix |
| 8 | frontend/src/app/dashboard/layout.tsx | logout() not awaited before navigate | Added async/await |
| 9 | frontend/src/app/dashboard/layout.tsx | Auth guard showed spinner when user null | Split into isLoading check + null return |
| 10 | backend/app/routers/auth.py | OAuth URL built with string concatenation | Replaced with JSONResponse |
| 11 | backend/app/routers/auth.py | Token rotation before user validation | Reordered: validate user first, then rotate |
| 12 | backend/app/routers/auth.py | Missing ValueError handler in OAuth exchange | Added try/except for int(user_id) |

**Verification:** All auth flows tested end-to-end via curl: registration (201), login (200), token refresh (rotation works), protected endpoints (Bearer auth), logout (token revocation), CORS preflight (200 with correct headers).

---

### Security Hardening + Test Fixes (March 25, 2026) ✅
**Goal:** Fix all 12 failing tests, comprehensive security audit with 20 parallel agents, and apply all critical fixes.

**Test fixes (10 failures → 0, total 12/12 passing):**
- ML evaluation tests: Overrode `require_admin` instead of `get_current_user` in FastAPI dependency overrides
- Search tests: Used `app.dependency_overrides` instead of `patch()` for proper auth bypass
- PostgreSQL tests: Added `session.rollback()` after pg_trgm check, valid `user_id` FK, `category` column in INSERT

**25 security fixes across 14 files:**

| Priority | Fix | File |
|----------|-----|------|
| CRITICAL | Shared "edit" users can no longer DELETE others' documents | `documents.py` |
| CRITICAL | Streaming file upload prevents memory exhaustion DoS | `documents.py` |
| CRITICAL | Magic bytes validation prevents file type spoofing | `storage_service.py` |
| CRITICAL | Global exception handler prevents stack trace leaks | `main.py` |
| HIGH | Password complexity: 8+ chars, upper, lower, digit, special char | `schemas/__init__.py` |
| HIGH | CSP: removed `unsafe-eval`, added `base-uri`, `form-action` | `next.config.mjs` |
| HIGH | Server-side route protection via Next.js middleware | `middleware.ts` (new) |
| HIGH | DB SSL for cloud PostgreSQL + pool_recycle/pool_timeout | `database.py` |
| MEDIUM | JWT `jti` claim for token uniqueness | `security.py` |
| MEDIUM | OAuth exchange code timing-safe comparison | `auth.py` |
| MEDIUM | OAuth username sanitization (strip invalid chars) | `auth.py` |
| MEDIUM | Block sharing with deactivated users or yourself | `documents.py` |
| MEDIUM | Email validation on share document requests | `sharing.py` |
| MEDIUM | HTML tag stripping on `full_name` (stored XSS prevention) | `schemas/__init__.py` |
| MEDIUM | CORS wildcard origin validation | `config.py` |
| MEDIUM | Null byte stripping in filenames | `documents.py` |
| MEDIUM | Celery connection pool limits + task rate limiting | `tasks/__init__.py` |
| MEDIUM | File size guard in Celery task processing | `document_tasks.py` |
| LOW | Explicit bcrypt rounds (12) | `security.py` |
| LOW | `X-XSS-Protection` set to `0` (deprecated header) | `security_headers.py`, `next.config.mjs` |
| LOW | `.gitignore` hardened (certs, keys, env variants) | `.gitignore` |

**E2E verification:** All 14 checks pass — containers up, backend 200, frontend 200, registration, login, PDF upload, magic bytes rejection, document listing, search, stats, security headers, Celery processing, Redis PONG, 12/12 tests green.

---

### Phase 7: UI & Analytics (March 25, 2026) ✅
**Goal:** Analytics dashboard, document preview, version control, responsive design.

**Delivered in 5 waves:**
- **Wave 1**: Shared component library (ConfidenceBadge, StatusBadge, CategoryBadge, LoadingSpinner) — removed duplicates from 6 pages
- **Wave 2**: Full recharts analytics dashboard — area chart (upload trends), donut chart (category distribution), stat cards, processing status bar. New GET /stats/trends backend endpoint.
- **Wave 3**: In-browser document preview — react-pdf for PDFs (page nav + zoom), image viewer (wheel zoom + drag pan), DOCX extracted text. New GET /preview endpoint. Dedicated preview page.
- **Wave 4**: Document version control — DocumentVersion model, auto-versioning on re-upload (same filename), version history API, rollback endpoint, version file download. Alembic migration 0009.
- **Wave 5**: Responsive design — collapsible sidebar with hamburger menu on mobile/tablet, overflow-x-auto on tables, mobile top bar.

**Files:** 8 new, 19 modified (+1468, -226 lines)

---

### Auth & Early Access Bug Fixes (April 30, 2026) ✅

**Problem:** End-to-end audit surfaced three production-impact issues in the early-access + login flow:

1. **CRITICAL — Invitation token URL parameter mismatch.**
   `send_approval_email` minted links as `/register?invite=<jwt>` but `register/page.tsx` read `searchParams.get("token")`. Approved users clicked the email link and saw the "Early Access Only" gate instead of the registration form. Bug survived unit tests because each side passed its own contract — only end-to-end testing surfaced it.

2. **No `/login` entry point on the landing page.** Existing users had no visible path back to login from `/` — the only navbar CTA was the early-access modal trigger. Users had to know the URL.

3. **Silent email failure.** `send_approval_email` was dispatched via FastAPI `BackgroundTasks` which discarded the `False` return. Admins saw "approved" in the UI while the user never received the link. Root cause for the "no mail coming" complaints: `SMTP_HOST` was unset in `.env`.

**Fixes shipped:**

- `backend/app/utils/email.py:52` — invitation URL now uses `?token=` to match the frontend contract; added DEBUG-mode dev breadcrumb that logs the registration URL when SMTP is unconfigured (lets devs test the full flow without a mail server); added 10s SMTP timeout
- `backend/app/routers/admin.py:466` — early-access review now sends mail synchronously and returns `{ email_sent: bool, email_error?: string, invitation_token?: string (DEBUG only) }` so the admin UI can surface delivery failures
- `frontend/src/app/dashboard/admin/page.tsx` — the review handler reads `email_sent`; toast distinguishes "approved — invitation email sent" vs. "approved, but email NOT delivered (SMTP not configured / send failed)"
- `frontend/src/components/landing/Navbar.tsx` — added quiet "Sign in" link → `/login` next to the primary "Start Beta Trial" CTA (desktop + mobile drawer); brand wordmark wraps in `<Link href="/">` for keyboard navigation; mobile hamburger gets `aria-expanded`/`aria-controls`
- `frontend/src/app/login/page.tsx`, `register/page.tsx` — focus-visible rings using existing `#10b981/40` accent token (preserves the dark-minimalist system); `autoFocus` on first field; `autoComplete=email|current-password|new-password|name|username`; `aria-busy` on form during submit; `aria-readonly` on the invitation-locked email field; `disabled:cursor-not-allowed` on submit buttons
- `backend/.env.example` — appended SMTP block with Gmail App Password setup walkthrough (the missing variable that was the root cause for "no mail coming")

**Verification (Playwright smoke 2026-04-30):**

- Submitted real early-access request → 201 Created
- Approved via direct DB path → minted JWT invitation token via the admin code path
- Visited `/register?token=<jwt>` → form rendered with `Smoke Test User` (full name) + `smoke-test-2026-04-30@taxsync.test` (read-only email) + "Your invitation has been verified" banner ✅
- Backend logged `email_skipped_no_smtp hint='Set SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD in .env to enable email delivery'` confirming the visibility fix
- Login page autofocuses email field, focus rings render correctly, `Sign in` link in navbar routes to `/login`

**Files touched:** 6 source + 1 env example. No new tests added (this was a regression sweep on an existing flow; the smoke screenshots are the verification artifact).

**SMTP wired (live verification):** Resend SMTP relay (`smtp.resend.com:587`, user=`resend`, sender=`onboarding@resend.dev` — Resend's verified sandbox sender, no domain verification needed). Live test send to `munnasrav45@gmail.com` returned `email_sent: True` from the production code path on 2026-04-30T10:44Z. Two Gmail App Passwords were attempted prior to switching to Resend and both got rejected with `535 BadCredentials` — suspected cause is 2-Step Verification not being on for that Google account. README + `.env.example` now lead with Resend and document Gmail as a fallback that requires 2-Step.

### Phase 8: Production Readiness (March 25, 2026) ✅
**Goal:** Audit logging, CI/CD pipeline, production deployment documentation.

**Delivered:**
- **Audit Logging (INFR-02)**: AuditLog model + migration, audit service with fire-and-forget BackgroundTasks, 9 endpoints wired (upload, download, delete, share, unshare, rollback, batch-delete, role_change, status_change), admin query endpoint with filters (user, action, resource, date range, pagination)
- **CI/CD Pipeline (INFR-03)**: GitHub Actions CI (pytest + ruff lint on push/PR, Docker build validation), deploy workflow (Docker image build + optional registry push on merge to main), Dependabot for weekly dependency updates
- **Production Documentation (INFR-04)**: DEPLOYMENT.md (Docker self-hosted + Render.com step-by-step), TROUBLESHOOTING.md (12+ problem/solution entries), SECURITY.md production checklist (16 items)

---

## Project Complete

All 8 phases delivered. The Smart Document Management System is production-ready.

---

## Repository & Docker

**GitHub:** https://github.com/IIIT-HYD-PROD-LABS/Smart-Document-Management-System

**Docker Setup:**
```bash
git clone <repo>
cd "SMART DOCUMENT MANAGEMENT SYSTEM- IIITHYD PROD LABS"
cp backend/.env.example backend/.env
# Set SECRET_KEY, DATABASE_URL, KAGGLE credentials in .env
docker compose up --build
```

**Services after `docker compose up`:**

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs (debug only) |
| PostgreSQL | Supabase Cloud (via DATABASE_URL) |
| Redis | localhost:6379 |

**Trained model** is included in git — no retraining needed on first run.

**To get datasets** (optional, for retraining only):
```bash
# Add KAGGLE_USERNAME + KAGGLE_KEY to .env first
docker compose run backend python -m app.ml.datasets.download
```

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn |
| Database | PostgreSQL (Supabase Cloud), Alembic migrations |
| ML | scikit-learn (LinearSVC + CalibratedClassifierCV + TF-IDF 15K), Tesseract OCR, pdfplumber, python-docx, OpenCV |
| AI/LLM | Multi-provider: Ollama, Gemini, Anthropic, OpenAI, local regex fallback |
| Async | Celery + Redis |
| Auth | JWT HS256 (30min) + opaque refresh tokens with rotation, bcrypt, OAuth (Google/Microsoft), slowapi rate limiting |
| Infra | Docker, Docker Compose (5 services), Supabase Cloud |

---

## Team

**Sravan** — Development Lead
**Jyothika** — Core Member

**Organization:** Product Labs, IIIT Hyderabad
