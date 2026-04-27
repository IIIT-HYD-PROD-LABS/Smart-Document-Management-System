---
phase: 09-compliance-foundation
plan: 04
subsystem: backend-middleware-rbac
tags: [fastapi, sqlalchemy-events, contextvars, postgres-rls, set-config, before-cursor-execute, depends-factory, structlog, pii-redaction]

# Dependency graph
requires:
  - phase: 09-03
    provides: "ClientMembership ORM with is_active_at, RLS-bypass-then-SET-ROLE conftest fixture pattern, post-0018 SECURITY DEFINER helpers (is_cross_client_eligible, user_has_client_membership)"
provides:
  - "TenantContextMiddleware: resolves X-Client-Id header to ContextVars, listener writes to PG session vars per cursor execute"
  - "Connection-checkin listener: clears app.current_client_id / cross_client_mode / user_id when connection returns to pool — prevents leakage to next request"
  - "auditor_expiry: is_membership_active(membership, when=None) and reason_inactive helpers per RBAC-04 / D-27"
  - "structlog redact_pii processor wired into app/utils/logging.py shared chain"
  - "Compliance dependency factories: get_active_client_id, get_active_membership, require_compliance_permission(perm), require_compliance_role(*roles) — mirror v1.0 require_admin pattern"
  - "set_tenant_context_for_celery helper for Celery worker code (Pitfall 6)"
  - "Migration 0019: tenant_isolation policies on 5 of 6 client-scoped tables wrap current_setting cast in NULLIF — fail-closed when tenant context unset, no DataError exception"
affects: [09-05, 09-06, 09-07]

# Tech tracking
tech-stack:
  added:
    - "Python contextvars + Starlette ContextVar isolation for thread-and-async-safe per-request tenant state"
    - "SQLAlchemy `before_cursor_execute` event for per-statement RLS context refresh (durable across intra-request commits)"
    - "SQLAlchemy `checkin` event for connection-pool tenant-context cleanup"
  patterns:
    - "Before-cursor-execute listener for RLS context: idempotent set_config calls per statement, survives commits without re-checkout"
    - "Session-scoped (is_local=false) set_config + connection-checkin reset — production-safe replacement for transaction-local pattern that doesn't survive commits"
    - "Dependency factory pattern: require_compliance_permission(perm) -> Depends-compatible callable matches v1.0 require_admin idiom"
    - "Cross-client mode resolution: header X-Client-Id: '*' → ContextVar cross_client_mode_var=True; routes that need a specific client use is_cross_client_mode() to branch"

key-files:
  created:
    - "backend/app/compliance/middleware/__init__.py — package docstring"
    - "backend/app/compliance/middleware/tenant_context.py — TenantContextMiddleware + register_tenant_listener + set_tenant_context_for_celery + 3 ContextVars"
    - "backend/app/compliance/middleware/auditor_expiry.py — is_membership_active + reason_inactive"
    - "backend/app/compliance/dependencies.py — get_active_client_id + get_active_membership + require_compliance_permission + require_compliance_role"
    - "backend/alembic/versions/0019_rls_fail_closed_on_empty_tenant.py — NULLIF wrapping on tenant_isolation policies"
  modified:
    - "backend/app/database.py — register_tenant_listener(engine) called at module bottom"
    - "backend/app/main.py — TenantContextMiddleware added (innermost middleware), X-Client-Id added to CORS allow_headers"
    - "backend/app/utils/security.py — get_current_user populates current_user_id_var; require_compliance_permission/role delegate exports"
    - "backend/app/utils/logging.py — import + add redact_pii to shared_processors chain (after sanitize_sensitive_data, before TimeStamper)"
    - "backend/tests/conftest.py — _set_tenant_context uses is_local=false; SET ROLE replaces SET LOCAL ROLE; auditor_membership uses user_id=2 to avoid uq_client_membership_user_client collision; client_a.id captured before role-cycle"
    - "backend/tests/test_rls_isolation.py — db.flush() inside per-client INSERT loop in test_cross_client_mode_eligible (test fix for Plan 01 stub buffering bug)"
    - ".planning/phases/09-compliance-foundation/09-VALIDATION.md — Plan 04 T1-T5 + DEVIATION rows marked ✅ green"

key-decisions:
  - "before_cursor_execute over checkout for the listener: PostgreSQL set_config(..., is_local=true) doesn't survive intra-request commits. Switching to per-statement listener with is_local=false guarantees the var is set on every cursor.execute regardless of intermediate commits — at the cost of one PG round-trip per statement (sub-ms locally)"
  - "Session-scoped set_config + connection-checkin reset: avoid leaking client_id from one request to the next when the same pool connection is reused. checkin listener executes set_config('app.*', '', false) before returning the connection to the pool"
  - "PERMISSIVE (not RESTRICTIVE) tenant_isolation: original 0015 omitted AS RESTRICTIVE. Migration 0019 preserves PERMISSIVE — INSERTs need at least one PERMISSIVE policy to satisfy with-check; combining tenant_isolation as RESTRICTIVE-only with cross_client_view PERMISSIVE-for-SELECT-only would block ALL writes"
  - "user_id=2 for auditor fixture: client_a fixture creates compliance_head membership for user_id=1 to satisfy post-0018 tenant_isolation on compliance_clients. Adding an auditor membership for user_id=1 on the same client violates uq_client_membership_user_client (user_id, client_id). Using user_id=2 is the minimum-impact fix"
  - "delegate exports in security.py use deferred import: re-exporting require_compliance_permission directly would create a startup-time circular import (app.compliance.dependencies depends on app.utils.security.get_current_user). Wrapping the impl in a thin function with internal import preserves the v1.0 import idiom without the circular dependency"

patterns-established:
  - "before_cursor_execute listener for tenant context: source-of-truth ContextVar values written to PG session vars on every statement; idempotent and durable across intra-request commits"
  - "checkin listener cleanup: every connection returns to the pool with empty tenant context — prevents the next request from inheriting stale tenancy"
  - "Dependency factory pattern: require_compliance_permission(perm) returns a closure that depends on get_active_membership; mirrors v1.0 require_admin/require_editor/require_viewer; mounts onto routes via Depends() in dependencies= or in the handler signature"
  - "NULLIF for empty session vars: any RLS policy that casts current_setting to a typed value should wrap in NULLIF(..., '') to fail-closed cleanly when the var is unset"

requirements-completed:
  - RBAC-01
  - RBAC-02
  - RBAC-03
  - RBAC-04
  - RBAC-05
  - RBAC-06
  - CLIENT-04
  - INFRA-06

# Metrics
duration: 38min
completed: 2026-04-27
---

# Phase 9 Plan 4: Wave 3 — Runtime Enforcement Summary

**FastAPI middleware + SQLAlchemy event listeners + dependency factory implementing the runtime enforcement layer that turns CLIENT-04 (RLS zero-leakage) and RBAC-01..06 (84-case role/permission matrix) merge gates GREEN simultaneously, plus structlog PII redaction wiring; migration 0019 fixes a fail-closed-on-empty-tenant bug discovered during execution.**

## Performance

- **Duration:** ~38 minutes
- **Started:** 2026-04-27T09:09:29Z
- **Completed:** 2026-04-27T09:35:51Z
- **Tasks:** 5/5
- **Files created:** 5 (3 middleware/dependency modules + 1 migration + 1 deferred-items.md)
- **Files modified:** 7 (database.py, main.py, security.py, logging.py, conftest.py, test_rls_isolation.py, VALIDATION.md)

## Accomplishments

- **3 Wave 0 merge gates GREEN simultaneously** for the first time:
  - CLIENT-04: `tests/test_rls_isolation.py` — 5/5 (zero-leakage, unset-tenant fail-closed, cross-client mode for eligible roles, rejection for ineligible roles, FORCE RLS structural)
  - RBAC-01..06: `tests/test_compliance_endpoints.py` — 85/85 (84 parametrized role×permission cases + 1 sanity check)
  - AUDIT-01: `tests/test_audit_immutability.py` — 5/5 (regression — no Plan 04 changes affected the audit_logs trigger or REVOKE)
- **Wave 3 mandate fully met:** all middleware + dependency primitives ready for Plan 05 routers to compose
- **TenantContextMiddleware registered as innermost middleware:** verified via `[m.cls.__name__ for m in app.user_middleware]` returning `['TenantContextMiddleware', 'CorrelationIdMiddleware', 'RequestLoggingMiddleware', 'SecurityHeadersMiddleware', 'GZipMiddleware', 'CORSMiddleware']`
- **Migration 0019 makes RLS fail-closed for empty tenant:** the test_unset_tenant_returns_empty merge gate passes cleanly without raising "invalid input syntax for integer" — instead returns empty rows
- **structlog redact_pii wired into shared chain:** GSTIN/PAN/CIN/DIN/penalty/tax_demand/total_liability fields are scrubbed before render
- **Zero v1.0 regression:** 100/100 tests in test_admin.py + test_auth.py + test_documents.py still pass
- **Zero Wave 1+2 regression:** 29/29 prior compliance tests still pass; 129/129 across all Phase 9 test files
- **Auditor expiry tests turn from ERROR to GREEN:** previously imported a missing module `app.compliance.middleware.auditor_expiry` and used `freezer` fixture that wasn't installed; both fixed

## Task Commits

| Task | Name                                                          | Commit    | Type |
| ---- | ------------------------------------------------------------- | --------- | ---- |
| 1    | tenant_context middleware + connection-checkout listener      | `f24b19f` | feat |
| 2    | auditor_expiry helper + structlog redact_pii wiring           | `0649ca4` | feat |
| 3    | require_compliance_permission Depends factory + helpers       | `eb51f00` | feat |
| 4    | Wire TenantContextMiddleware into FastAPI app                 | `0738833` | feat |
| 5    | Turn 3 Wave 0 merge gates GREEN — RLS, auditor, RBAC          | `504af53` | fix  |

**Plan metadata commit:** _appended after this SUMMARY_

## Files Created/Modified

### Created (5 files)

- `backend/app/compliance/middleware/__init__.py` — Package init + module docstring
- `backend/app/compliance/middleware/tenant_context.py` — TenantContextMiddleware + 3 ContextVars (current_client_id_var, cross_client_mode_var, current_user_id_var) + register_tenant_listener (before_cursor_execute + checkin) + set_tenant_context_for_celery
- `backend/app/compliance/middleware/auditor_expiry.py` — is_membership_active(membership, when=None) + reason_inactive helper
- `backend/app/compliance/dependencies.py` — get_active_client_id + is_cross_client_mode + get_active_membership + require_compliance_permission(perm) + require_compliance_role(*roles)
- `backend/alembic/versions/0019_rls_fail_closed_on_empty_tenant.py` — NULLIF(...) wrapping on tenant_isolation USING + WITH CHECK across 5 client-scoped tables (compliance_client_registrations, compliance_client_memberships, compliance_notices, compliance_notice_activity, compliance_notice_tags)

### Modified (7 files)

- `backend/app/database.py` — Imports + calls register_tenant_listener(engine) at module bottom (deferred import to avoid circular reference)
- `backend/app/main.py` — Adds TenantContextMiddleware to app.add_middleware stack (innermost = first executed); adds `X-Client-Id` to CORS allow_headers
- `backend/app/utils/security.py` — get_current_user populates current_user_id_var; appends require_compliance_permission and require_compliance_role delegate functions (deferred import to avoid circular)
- `backend/app/utils/logging.py` — Imports redact_pii; adds it to shared_processors after sanitize_sensitive_data and before TimeStamper
- `backend/tests/conftest.py` — `_set_tenant_context` uses set_config(..., false); all `SET LOCAL ROLE app_runtime` replaced with `SET ROLE app_runtime` so role survives intra-test commits; auditor_membership uses user_id=2 (auto-created if missing) and captures client_a.id before role/commit cycle
- `backend/tests/test_rls_isolation.py` — `test_cross_client_mode_eligible` adds db.flush() inside the per-client INSERT loop so each row's INSERT happens under its own set_config (Plan 01 stub buffering bug)
- `.planning/phases/09-compliance-foundation/09-VALIDATION.md` — Plan 04 T1-T5 marked ✅ green; DEVIATION row added for migration 0019
- `.planning/phases/09-compliance-foundation/deferred-items.md` — Created to log pre-existing test_search.py rate-limit flake (out of Plan 04 scope)

## Decisions Made

See frontmatter `key-decisions` for the full list. Highlights:

- **before_cursor_execute, not checkout, for the tenant listener.** SQLAlchemy reuses the same connection across commits within a session; PostgreSQL `set_config(..., is_local=true)` is transaction-local and is GONE after the first `COMMIT` inside a request. The plan's recommended `checkout` event would set the var once on connection borrow but lose it on the first intra-request commit. Switching to `before_cursor_execute` writes the var on every cursor.execute (idempotent, sub-ms cost).
- **session-scoped set_config + checkin reset.** With is_local=false the var persists across commits; the checkin listener clears it before the connection returns to the pool. This combination is the production-safe replacement for the plan's transaction-local recipe.
- **PERMISSIVE preserved on tenant_isolation.** Migration 0019 keeps tenant_isolation PERMISSIVE (the 0015 default). The original spec implied RESTRICTIVE; switching to RESTRICTIVE blocks INSERT/UPDATE because PostgreSQL requires at least one PERMISSIVE policy to admit a row, and cross_client_view is PERMISSIVE-for-SELECT-only.
- **NULLIF wrapping rather than policy-condition rewrite.** The bug surfaced by the test (`invalid input syntax for type integer: ""`) is solved by wrapping the cast: `NULLIF(current_setting(...), '')::integer`. Empty string yields NULL, comparison with NULL evaluates to NULL/false, RLS denies the row. Less invasive than rewriting the policy logic.
- **user_id=2 for auditor fixture.** Plan 03's `_create_client_with_rls_bypass` adds a compliance_head membership for user_id=1 on the fresh client to satisfy `tenant_isolation` (which is membership-based after migration 0018). Adding an auditor membership for the same (user_id=1, client_a) violates `uq_client_membership_user_client`. Using user_id=2 sidesteps this with a minimum-impact diff.
- **Deferred import for require_compliance_permission delegate.** `app.compliance.dependencies` already imports `app.utils.security.get_current_user`; the reverse re-export at module load would form a circular import. Wrapping the impl in a thin function with internal `from ... import` defers the import until first call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] pytest-freezer + freezegun not installed in container**
- **Found during:** Task 2 baseline pytest run (test_auditor_expiry.py)
- **Issue:** `requirements.txt` lists `pytest-freezer==0.4.9` and `freezegun==1.5.5`, but the running backend container was built before these lines existed. `from pytest_freezer import ...` raises `ModuleNotFoundError`.
- **Fix:** `docker compose exec backend pip install pytest-freezer==0.4.9 freezegun==1.5.5`. CI will pick up requirements.txt on next image build.
- **Files modified:** None in repo (transient install in running container).
- **Verification:** `pytest --fixtures | grep freezer` shows the fixture available; test_auditor_expiry.py runs without ImportError.
- **Committed in:** Side effect in container, not in repo. Documented here for the next executor.

**2. [Rule 1 — Bug] Migration 0019: tenant_isolation policies fail with type error on empty tenant context**
- **Found during:** Task 5 (running test_rls_isolation::test_unset_tenant_returns_empty)
- **Issue:** RLS policy `client_id = (current_setting('app.current_client_id', true))::integer` raises `psycopg2.errors.InvalidTextRepresentation: invalid input syntax for type integer: ""` when current_setting returns empty string. This happens after the connection-checkin listener resets the var, OR on a fresh connection that never had it set. The merge gate test asserts `rows == []` (empty list), not "raises an exception".
- **Fix:** New migration `0019_rls_fail_closed_on_empty_tenant.py` rewrites tenant_isolation USING + WITH CHECK to wrap the cast: `client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer`. Empty string → NULL → comparison evaluates to NULL/false → row is filtered out (fail-closed cleanly). Applied to 5 tables: compliance_client_registrations, compliance_client_memberships, compliance_notices, compliance_notice_activity, compliance_notice_tags. compliance_clients was rewritten in 0018 with a different mechanism (user_has_client_membership) so it does not need the NULLIF treatment.
- **Files modified:** backend/alembic/versions/0019_rls_fail_closed_on_empty_tenant.py (new, 116 lines)
- **Verification:** `alembic upgrade head` → `0019_rls_fail_closed_on_empty_tenant (head)`; `alembic downgrade -1; alembic upgrade head` cycles cleanly; test_rls_isolation passes 5/5.
- **Committed in:** `504af53` (Task 5 commit)

**3. [Rule 1 — Bug] conftest._set_tenant_context used is_local=true, lost after commit**
- **Found during:** Task 5 (running test_no_cross_client_leakage)
- **Issue:** Plan 03's conftest `_set_tenant_context` uses `set_config(..., true)` (transaction-local). Test bodies that call `db.commit()` lose the tenant context, and when the next operation runs in a fresh transaction `current_setting` returns empty string. RLS then denies all rows — but more insidiously, the role also reverts because `SET LOCAL ROLE app_runtime` is also transaction-local. After commit, role drops back to `postgres` (BYPASSRLS) and the test session sees rows from ALL clients.
- **Fix:** Two-part change:
  1. `_set_tenant_context` now uses `set_config(..., false)` (session scope).
  2. All `SET LOCAL ROLE app_runtime` statements in conftest changed to `SET ROLE app_runtime` so the role survives intra-test commits.
- **Files modified:** backend/tests/conftest.py
- **Verification:** test_no_cross_client_leakage now correctly asserts `len(notices) == 10` rather than 20 (cross-tenant leak).
- **Committed in:** `504af53` (Task 5 commit)

**4. [Rule 1 — Bug] auditor_membership fixture violated unique constraint**
- **Found during:** Task 2 (running test_auditor_expiry.py first time)
- **Issue:** Plan 03's `_create_client_with_rls_bypass` creates a compliance_head ClientMembership for user_id=1 on the fresh client (so the test session can satisfy post-0018 tenant_isolation on compliance_clients). The `auditor_membership` fixture then tries to create an auditor membership for the same (user_id=1, client_a) → violates `uq_client_membership_user_client (user_id, client_id)`.
- **Fix:** auditor_membership fixture now uses user_id=2 instead of user_id=1, auto-creating the user row if missing. Also captures `client_a.id` into a local int BEFORE role/commit cycle — accessing `client_a.id` after commit while role is `app_runtime` would force an attribute reload SELECT under RLS without tenant context set, triggering ObjectDeletedError.
- **Files modified:** backend/tests/conftest.py
- **Verification:** All 3 auditor expiry tests pass.
- **Committed in:** `0649ca4` (Task 2 commit)

**5. [Rule 1 — Bug] test_cross_client_mode_eligible buffered ORM inserts under last set_config only**
- **Found during:** Task 5 (running test_rls_isolation.py)
- **Issue:** The test sets `set_config(...)` per-iteration then `db.add(notice)`, then commits at the end of the loop. SQLAlchemy ORM batches all the `db.add(...)` calls and emits a single multi-row INSERT at flush/commit time. Only the LAST `set_config` is in effect — so notices for client_a (with notice.client_id=ca_id) try to INSERT under current_setting=cb_id, failing the WITH CHECK.
- **Fix:** Add `db_as_app_runtime.flush()` inside the per-client loop in test_cross_client_mode_eligible. This forces each row's INSERT to happen under its own set_config call. Same pattern as the existing test_no_cross_client_leakage (which does inner-then-outer loop with commit-per-client).
- **Files modified:** backend/tests/test_rls_isolation.py
- **Verification:** Test passes; `len(rows) >= 2` confirms cross-client mode visibility for the eligible compliance_head user.
- **Committed in:** `504af53` (Task 5 commit)

**Total deviations:** 5 (4 Rule 1 — Bug, 1 Rule 3 — Blocking)
**Impact on plan:** All deviations were on the critical path to turning the merge gates GREEN. Migrations 0019 is a production-facing fix — without it, any /api/compliance/* request that hits a public endpoint without setting X-Client-Id (e.g. an attacker probing) would surface a DB-level type error rather than fail-closed. Conftest fixes preserve Plan 03's RLS-aware test isolation contract while fixing transaction-scope bugs surfaced by the new merge gate exercises. Test fix is a one-line pattern correction that matches the surrounding test file's convention.

## Issues Encountered

- **Pre-existing rate-limit flake in test_search.py:** running multiple tests in test_search.py sequentially trips the slowapi 30 req/minute limit, causing 3 tests to return 429 instead of 200. Each test PASSES individually. Documented in `deferred-items.md` per the SCOPE BOUNDARY rule (no Plan 04 router changes touch /api/documents/*).
- **PytestUnknownMarkWarning: integration:** every test file using `pytestmark = pytest.mark.integration` raises this warning because conftest does not register the marker. Pre-existing from Plan 01; cosmetic only.

## Tests Status

### GREEN (Wave 0 + Wave 1 + Wave 2 + Wave 3 = 129 of 129 Phase 9 tests)

| File                                | Tests Passing                                      |
| ----------------------------------- | -------------------------------------------------- |
| test_indian_validators.py           | 6/6                                                |
| test_pii_encryption.py              | 2/2                                                |
| test_log_redaction.py               | 1/1                                                |
| test_permission_registry.py         | 4/4                                                |
| test_notice_state_machine.py        | 3/3                                                |
| test_regulatory_calendar.py         | 1/1                                                |
| test_client_management.py           | 2/2                                                |
| test_client_onboarding.py           | 1/1                                                |
| test_jsonb_query.py                 | 1/1                                                |
| test_notice_chain.py                | 2/2                                                |
| test_notice_query.py                | 1/1                                                |
| test_compliance_notices.py          | 2/2                                                |
| test_dashboard.py                   | 1/1                                                |
| test_reports.py                     | 1/1                                                |
| test_notice_service.py              | 1/1                                                |
| test_audit_capture.py               | 2/2                                                |
| test_audit_immutability.py          | 5/5                                                |
| test_compliance_endpoints.py        | 85/85 (84 parametrized + 1 sanity)                 |
| test_rls_isolation.py               | 5/5 (CLIENT-04 merge gate)                         |
| test_auditor_expiry.py              | 3/3 (RBAC-04)                                      |
| **Phase 9 total**                   | **129/129 GREEN**                                  |

### Regression baseline preserved (v1.0)

`docker compose exec backend pytest tests/test_admin.py tests/test_auth.py tests/test_documents.py` → 100/100 GREEN.

## User Setup Required

For developers continuing this work locally, the running backend container needs the freezer plugin installed (one-time):
```
docker compose exec backend pip install pytest-freezer==0.4.9 freezegun==1.5.5
```
Or rebuild the backend image (Dockerfile picks up requirements.txt).

For production deployment:
- No new external services
- Apply migration 0019 with `alembic upgrade head` — required so RLS fails-closed cleanly when tenant context is unset

## Next Phase Readiness

**Plan 09-05 (Wave 4 — FastAPI routers) — READY**

What's wired and waiting for routers:
- TenantContextMiddleware in middleware chain — every /api/compliance/* request automatically resolves X-Client-Id to PG session vars
- `Depends(require_compliance_permission(CompliancePermission.X))` is the one-liner for any new endpoint
- `Depends(get_active_membership)` returns the active ClientMembership for use inside handlers
- Cross-client mode (X-Client-Id: '*') routed through is_cross_client_mode() helper
- Migration head = 0019, all RLS policies fail-closed on empty tenant context

**Wave 3 → Wave 4 handoff:**
- Plan 05 routers compose `Depends(require_compliance_permission(...))` to enforce RBAC; RLS isolation is automatic via the middleware
- The CLIENT-04 zero-leakage merge gate is now an integration test that runs against the actual middleware path
- The 84-case RBAC matrix is structurally GREEN (permission_registry from Plan 02); Plan 05 routers will mount the factory and the matrix turns into a route-layer integration test

**Known partial-green tests (Plan 05/06/07 responsibility):**
- None. Plan 04 closed all RED tests in its scope. Plan 05's router-layer tests are not yet written; they are Wave 4 work.

## Self-Check: PASSED

- [x] All 5 created files exist on disk
  - backend/app/compliance/middleware/__init__.py
  - backend/app/compliance/middleware/tenant_context.py
  - backend/app/compliance/middleware/auditor_expiry.py
  - backend/app/compliance/dependencies.py
  - backend/alembic/versions/0019_rls_fail_closed_on_empty_tenant.py
- [x] All 5 task commits exist on main: `f24b19f, 0649ca4, eb51f00, 0738833, 504af53`
- [x] Migration head = `0019_rls_fail_closed_on_empty_tenant`: `alembic current` confirms
- [x] All 129 Phase 9 pytest tests pass
- [x] V1.0 regression: 100/100 in test_admin + test_auth + test_documents
- [x] App boots cleanly: `from app.main import app` exits 0
- [x] TenantContextMiddleware in app.user_middleware chain
- [x] No SQL syntax errors: every migration parses via ast.parse
- [x] structlog redact_pii integrated and verified end-to-end (live log emission strips gstin/penalty/etc.)

---
*Phase: 09-compliance-foundation*
*Completed: 2026-04-27*
