---
phase: 09-compliance-foundation
plan: 05
subsystem: backend-api-routers
tags: [fastapi, apirouter, depends, permission-gating, openapi, rls-passthrough, partial-failure, recursive-cte, document-reuse]

# Dependency graph
requires:
  - phase: 09-04
    provides: "TenantContextMiddleware, require_compliance_permission factory, get_active_membership dep, ComplianceRole/CompliancePermission enums, RLS fail-closed via migration 0019"
provides:
  - "7 FastAPI routers under /api/compliance (clients, memberships, notices, reports, audit, notice_types, regulatory_calendar)"
  - "18 OpenAPI paths covering full compliance HTTP surface for Plans 06-07 frontend"
  - "Status-target -> permission mapping (NOTICE_SUBMIT/APPROVE/DRAFT_RESPONSE) on PATCH /notices/{id}/status with valid_next_statuses 422 payload"
  - "Read-only audit log viewer (no POST/PUT/DELETE) honoring AUDIT-01 immutability at API surface"
  - "v1.0 storage_service + Document.notice_id FK reuse for notice file uploads (D-10) — single OCR pipeline path"
  - "Partial-failure bulk update endpoint piping into bulk_update_status service (LIFE-08)"
affects: [09-06, 09-07]

# Tech tracking
tech-stack:
  added:
    - "FastAPI APIRouter prefix-and-tag composition with mid-level mount under /api/compliance"
    - "Pydantic 2.x model_validate(...).model_dump(mode='json') for Decimal/date serialization in list endpoint"
    - "FastAPI UploadFile + multipart with content-type whitelist for notice attachment uploads"
  patterns:
    - "Permission-target dispatcher: helper _permission_for_target_status(target) maps NoticeStatus -> CompliancePermission so a single PATCH /status endpoint handles all transitions while honoring per-target permission contracts"
    - "RLS-passthrough router: routers do not filter by client_id manually; service-layer client_id filter is for query plan / pagination metadata; tenant isolation is enforced by middleware + RLS (CLIENT-04 contract)"
    - "Per-task incremental commit per atomic-commit policy (4 task commits + 1 metadata commit)"
    - "Document.notice_id back-link first-upload-wins: first uploaded file becomes the notice's primary document_id; subsequent uploads attach via NoticeActivity entries only"

key-files:
  created:
    - "backend/app/compliance/routers/__init__.py — package docstring + router inventory"
    - "backend/app/compliance/routers/clients.py — 4 endpoints (CLIENT-01..03, CLIENT-05)"
    - "backend/app/compliance/routers/memberships.py — 2 endpoints (POST add, DELETE revoke; CLIENT-05 + RBAC-04)"
    - "backend/app/compliance/routers/notices.py — 10 endpoints covering full LIFE-01..08 surface"
    - "backend/app/compliance/routers/reports.py — POST /reports/health-summary (CLIENT-07)"
    - "backend/app/compliance/routers/audit.py — GET /audit (AUDIT-01, read-only by design)"
    - "backend/app/compliance/routers/notice_types.py — GET /notice-types (D-01 lookup)"
    - "backend/app/compliance/routers/regulatory_calendar.py — GET /regulatory-calendar (INFRA-05)"
  modified:
    - "backend/app/main.py — imports + 7 include_router calls under /api/compliance prefix; placed AFTER existing v1.0 routers so TenantContextMiddleware (innermost from Plan 04) wraps every compliance route"

key-decisions:
  - "Status-target -> permission dispatcher (single PATCH endpoint, not 5 separate endpoints): a single PATCH /notices/{id}/status simplifies the API surface and lets the helper _permission_for_target_status enforce the per-transition permission map. The alternative (separate /submit, /approve, /draft endpoints) would have spread the state machine across 5 routes + 5 different permission gates and made InvalidTransitionError handling harder to centralize."
  - "Plan 04 PATCH /status uses get_active_membership directly (NOT require_compliance_permission(...)): the dependency factory locks in a single permission at decoration time, but PATCH /status needs DIFFERENT permissions per target. Inlining the role->permission check after dependency resolution keeps the permission registry as the source of truth while honoring per-transition semantics."
  - "First-upload-wins for notice.document_id: when a notice is created via POST /notices the document_id is optional (typically NULL). The first POST /notices/{id}/upload sets it; subsequent uploads attach via NoticeActivity 'file_attached' entries (with document_id in details) but do NOT overwrite the primary. This preserves stable deep-links to the original notice document in the UI."
  - "Reports router uses REPORT_EXPORT (not REPORT_VIEW): REPORT_EXPORT is the more conservative choice — it grants compliance_head, ca_consultant, auditor, cfo (per registry) which matches the actual stakeholders for monthly health summaries. REPORT_VIEW would also include legal_team and finance_team; those roles get to view the underlying notice list but should not extract per-client analytics rollups."
  - "AUDIT_VIEW is auditor-exclusive: even compliance_head does NOT have AUDIT_VIEW per the registry. The audit log is the auditor's domain; making it visible to compliance_head would muddy the separation of duties (compliance_head is the subject of many audit entries — they cannot also be the inspector)."
  - "Audit endpoint has no POST/PUT/DELETE handler at all (not 'returns 405 if attempted'): the API surface itself omits write methods so attackers cannot probe what the immutability guarantees are. The DB trigger + REVOKE on app_runtime is defense in depth; the API surface decision is principle of least surprise."
  - "page_size cap of 500 on list endpoints: 50 default with hard ceiling 500 chosen so a CFO running cross-client mode reports does not pull 100k notices in a single response. Frontend will paginate; CSV export (Phase 11) will use a different streaming endpoint."

patterns-established:
  - "Mount Phase 9 routers under /api/compliance via app.include_router(router, prefix='/api/compliance') in main.py rather than baking the prefix into each router's APIRouter(prefix=...). Allows the router files to be relocated or sub-mounted under different prefixes (e.g. internal admin /api/internal/compliance) without rewriting decorators."
  - "Pydantic schema-first: every router uses Pydantic models from app.compliance.schemas/* for request/response. Avoids ad-hoc dict shapes drifting between layers; enables automatic OpenAPI examples + frontend type generation in Plans 06-07."
  - "Empty-suffix decorator pattern (@router.get('', ...)) for collection root: APIRouter prefix already provides the namespace; empty path means 'mount on the prefix root'. Confirmed via OpenAPI inspection — 18 unique paths render correctly."
  - "Pydantic model_dump(mode='json') in list_notices: NoticeOut contains Decimal and date columns; default model_dump returns Python native types that FastAPI's response serializer chokes on under nested dict response_model. mode='json' coerces to JSON-safe primitives."

requirements-completed:
  - LIFE-01
  - LIFE-02
  - LIFE-03
  - LIFE-04
  - LIFE-05
  - LIFE-06
  - LIFE-07
  - LIFE-08
  - AUDIT-01
  - AUDIT-02
  - CLIENT-01
  - CLIENT-02
  - CLIENT-03
  - CLIENT-05
  - CLIENT-06
  - CLIENT-07
  - INFRA-05

# Metrics
duration: 8min
completed: 2026-04-27
---

# Phase 9 Plan 5: Wave 4 — FastAPI Compliance Routers Summary

**Seven FastAPI APIRouter modules expose the entire Phase 9 compliance HTTP surface (clients, memberships, notices, reports, audit viewer, notice-type catalog, regulatory calendar) under `/api/compliance` with every endpoint gated by `Depends(require_compliance_permission(...))` from Plan 04, completing the backend stack for Plans 06-07 frontend consumption.**

## Performance

- **Duration:** ~8 minutes (well under the 30-min Wave 4 budget)
- **Started:** 2026-04-27T09:41:57Z
- **Completed:** 2026-04-27T09:49:44Z
- **Tasks:** 4/4
- **Files created:** 8 (7 routers + __init__.py)
- **Files modified:** 1 (backend/app/main.py)

## Accomplishments

- **18 OpenAPI compliance paths** rendered under /api/compliance covering all 17 requirements
- **20 mounted routes** (some paths serve multiple methods — POST + DELETE on /memberships, GET + POST/PATCH on /notices etc.)
- **85/85 RBAC matrix tests GREEN** — full 84-case 7×12 role/permission matrix from Wave 0 still passes after router wiring
- **9/9 Phase 9 functional tests GREEN** — test_compliance_notices, test_client_management, test_dashboard, test_reports, test_audit_capture, test_client_onboarding all passing against the new router-aware service paths
- **325/325 backend tests GREEN** in the full backend test suite (excluding pre-existing test_search.py rate-limit flake from Plan 04 deferred-items.md)
- **100/100 v1.0 regression intact** — test_admin.py + test_auth.py + test_documents.py all green; no v1.0 endpoints affected by the new compliance routers
- **Auth gate verified** — `GET /api/compliance/clients/me` without bearer token returns 401 "Not authenticated"
- **Read-only audit endpoint** — audit.py has zero POST/PUT/DELETE methods (verified by `grep -cE "@router\\.(post|put|delete)" → 0`)
- **State machine integrity preserved** — PATCH /notices/{id}/status routes through transition_notice_status (Pitfall 8: routers do NOT bypass the service for ComplianceNotice.status mutations)

## Task Commits

| Task | Name                                                    | Commit    | Type |
| ---- | ------------------------------------------------------- | --------- | ---- |
| 1    | clients + memberships routers + __init__.py             | `a33e57d` | feat |
| 2    | notices router (10 endpoints)                           | `6359acd` | feat |
| 3    | reports + audit + notice_types + regulatory_calendar    | `16c3d96` | feat |
| 4    | Mount all 7 routers under /api/compliance in main.py    | `c3532db` | feat |

**Plan metadata commit:** _appended after this SUMMARY_

## Endpoint Matrix

| Method | Path                                                 | Permission Gate                | Source                  |
|--------|------------------------------------------------------|--------------------------------|-------------------------|
| GET    | /api/compliance/clients/me                           | (auth only)                    | clients.py              |
| POST   | /api/compliance/clients                              | CLIENT_CREATE                  | clients.py              |
| GET    | /api/compliance/clients/{client_id}                  | NOTICE_VIEW                    | clients.py              |
| GET    | /api/compliance/clients/{client_id}/dashboard        | NOTICE_VIEW                    | clients.py              |
| POST   | /api/compliance/clients/{client_id}/memberships      | CLIENT_MANAGE_TEAM             | memberships.py          |
| DELETE | /api/compliance/clients/{client_id}/memberships/{id} | CLIENT_MANAGE_TEAM             | memberships.py          |
| GET    | /api/compliance/notices                              | NOTICE_VIEW                    | notices.py              |
| POST   | /api/compliance/notices                              | NOTICE_CREATE                  | notices.py              |
| GET    | /api/compliance/notices/{notice_id}                  | NOTICE_VIEW                    | notices.py              |
| PATCH  | /api/compliance/notices/{notice_id}                  | NOTICE_CREATE                  | notices.py              |
| PATCH  | /api/compliance/notices/{notice_id}/status           | (target-dependent — see below) | notices.py              |
| POST   | /api/compliance/notices/bulk                         | NOTICE_BULK_UPDATE             | notices.py              |
| GET    | /api/compliance/notices/{notice_id}/chain            | NOTICE_VIEW                    | notices.py              |
| POST   | /api/compliance/notices/{notice_id}/upload           | NOTICE_CREATE                  | notices.py              |
| GET    | /api/compliance/notices/{notice_id}/activity         | NOTICE_VIEW                    | notices.py              |
| POST   | /api/compliance/notices/{notice_id}/activity/note    | NOTICE_DRAFT_RESPONSE OR NOTICE_CREATE | notices.py      |
| GET    | /api/compliance/notice-types                         | NOTICE_VIEW                    | notice_types.py         |
| GET    | /api/compliance/regulatory-calendar                  | NOTICE_VIEW                    | regulatory_calendar.py  |
| GET    | /api/compliance/audit                                | AUDIT_VIEW                     | audit.py                |
| POST   | /api/compliance/reports/health-summary               | REPORT_EXPORT                  | reports.py              |

### Status transition permission map (PATCH /notices/{id}/status)

The PATCH /status endpoint dispatches to a single notice_service.transition_notice_status call after verifying the active membership's role has the permission corresponding to the *target* state:

| Target Status                  | Required Permission       | Roles With It                                      |
|--------------------------------|---------------------------|----------------------------------------------------|
| under_review, response_drafted | NOTICE_DRAFT_RESPONSE     | legal_team, ca_consultant, staff                   |
| submitted                      | NOTICE_SUBMIT             | compliance_head, ca_consultant                     |
| resolved, dismissed            | NOTICE_APPROVE            | compliance_head, ca_consultant                     |

Invalid transitions return 422 with payload `{"detail": {"message": "...", "valid_next_statuses": [...]}}`.

## Files Created/Modified

### Created (8 files)

- `backend/app/compliance/routers/__init__.py` — package docstring + 7-module inventory
- `backend/app/compliance/routers/clients.py` — 4 endpoints (137 lines)
- `backend/app/compliance/routers/memberships.py` — 2 endpoints (144 lines)
- `backend/app/compliance/routers/notices.py` — 10 endpoints (572 lines)
- `backend/app/compliance/routers/reports.py` — 1 endpoint (66 lines)
- `backend/app/compliance/routers/audit.py` — 1 endpoint (79 lines, read-only)
- `backend/app/compliance/routers/notice_types.py` — 1 endpoint (51 lines)
- `backend/app/compliance/routers/regulatory_calendar.py` — 1 endpoint (64 lines)

### Modified (1 file)

- `backend/app/main.py` — added 22 lines: 7 imports from app.compliance.routers, 7 include_router(...) calls with prefix='/api/compliance'

## Decisions Made

See frontmatter `key-decisions` for the full list. Highlights:

- **Status-target → permission dispatcher.** A single PATCH /notices/{id}/status endpoint handles all 5 forward transitions plus 2 back-edits, dispatching to the correct permission via `_permission_for_target_status(target) -> CompliancePermission`. Alternative (5 separate endpoints) was rejected because it would scatter the state machine across handlers, duplicate the InvalidTransitionError 422 mapping, and force the frontend to switch on target status before choosing the right URL.
- **Plan 04 dependency factory NOT used on PATCH /status.** `require_compliance_permission(perm)` locks in `perm` at decoration time. PATCH /status needs the permission to depend on the runtime payload. The handler depends on `get_active_membership` directly and inlines the role + permission check after deserialization. The permission registry is still the source of truth; only the gate-shape differs.
- **First-upload-wins for `notice.document_id`.** A notice is typically created with `document_id=NULL` then a file is uploaded. The first upload sets `notice.document_id = d.id`; subsequent uploads (response drafts, evidence) attach via NoticeActivity rows but do NOT overwrite the primary FK. The detail-page "View original" button gets a stable link.
- **Read-only audit endpoint.** audit.py has zero write decorators. The DB trigger + REVOKE on app_runtime (Plan 02 migration 0014/0017) is the authoritative defense; omitting the API surface is principle of least surprise — a future maintainer cannot accidentally add a PATCH handler that bypasses the RBAC layer expecting it to be intercepted by the trigger.
- **REPORT_EXPORT (not REPORT_VIEW) on /reports/health-summary.** REPORT_EXPORT is held by compliance_head, ca_consultant, auditor, cfo — the actual stakeholders for monthly rollups. REPORT_VIEW also grants legal_team + finance_team, who get to view the underlying notice list but should not extract per-client analytics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Pydantic model_dump for Decimal/date fields in list_notices**
- **Found during:** Task 2 unit testing of NoticeOut serialization
- **Issue:** `NoticeOut.model_validate(n).model_dump()` returns Python native types (Decimal('100.00'), datetime.date(2026, 4, 27)). FastAPI's nested response_model=dict path then serializes these via the default Python json.dumps which raises `TypeError: Object of type Decimal is not JSON serializable`.
- **Fix:** Switched to `NoticeOut.model_validate(n).model_dump(mode='json')` which coerces Decimal → string and date → ISO-format string, both JSON-safe.
- **Files modified:** backend/app/compliance/routers/notices.py (1 line in list_notices)
- **Verification:** Endpoint round-trip via TestClient against a seeded DB returns valid JSON.
- **Committed in:** `6359acd` (Task 2 commit)

**2. [Rule 1 — Bug] Unused datetime/timezone imports in notices.py**
- **Found during:** Task 2 internal cleanup before commit
- **Issue:** Initial draft imported `datetime, timezone` for an audit log timestamp helper that was later refactored away (log_audit_event handles timestamps internally). Leftover imports trigger flake8 F401 in CI.
- **Fix:** Removed the unused names, keeping `datetime as date_t` only.
- **Files modified:** backend/app/compliance/routers/notices.py (1 line)
- **Verification:** AST parse + 10-route count unchanged.
- **Committed in:** `6359acd` (Task 2 commit)

**3. [CLAUDE.md compliance] Used `docker compose` exclusively for all test/inspection commands**
- **Per user feedback memory file feedback_docker_only.md:** All Smart-Docs services must run via docker-compose, never manual processes.
- **Application:** Every pytest invocation, FastAPI app inspection, and OpenAPI render in this plan was run via `docker compose exec -T backend ...` rather than against a host-side venv. This is documented as a behavioral note rather than a deviation; no plan instruction was changed.

**Total deviations:** 2 minor (both Rule 1 — Bug, both inside notices.py during Task 2)
**Impact on plan:** Both fixes are localized; neither changed the task structure, commit count, or file inventory. The Decimal/date fix is required for the list endpoint to serve any non-trivial notice list at all (every real notice has tax_demand or response_deadline).

## Issues Encountered

- **Pre-existing test_search.py rate-limit flake** (3 tests in test_search.py trip slowapi 30/min when run together): documented in Plan 04 deferred-items.md; out of scope per SCOPE BOUNDARY rule. No Plan 09-05 changes touch /api/documents/search; the failure pattern is identical to Plan 04 baseline.
- **`PytestUnknownMarkWarning: integration`** on every test file using `pytestmark = pytest.mark.integration`: pre-existing from Plan 01; cosmetic only.

## Tests Status

### GREEN (all Phase 9 + v1.0 baseline)

| Suite                            | Result                       |
|----------------------------------|------------------------------|
| test_compliance_endpoints.py     | 85/85 (84 RBAC + 1 sanity)   |
| test_rls_isolation.py            | 5/5 (CLIENT-04 merge gate)   |
| test_audit_immutability.py       | 5/5 (AUDIT-01 merge gates)   |
| test_auditor_expiry.py           | 3/3 (RBAC-04)                |
| test_compliance_notices.py       | 2/2 (LIFE-01, LIFE-08)       |
| test_client_management.py        | 2/2 (CLIENT-01, CLIENT-02)   |
| test_client_onboarding.py        | 1/1 (CLIENT-05)              |
| test_dashboard.py                | 1/1 (CLIENT-03)              |
| test_reports.py                  | 1/1 (CLIENT-07)              |
| test_audit_capture.py            | 2/2 (AUDIT-02)               |
| test_notice_service.py           | 1/1 (LIFE-04)                |
| test_notice_chain.py             | 2/2 (LIFE-05)                |
| test_notice_query.py             | 1/1 (LIFE-07)                |
| test_indian_validators.py        | 6/6 (LIFE-03)                |
| test_pii_encryption.py           | 2/2 (INFRA-06)               |
| test_log_redaction.py            | 1/1 (INFRA-06)               |
| test_permission_registry.py      | 4/4 (RBAC-01..06)            |
| test_notice_state_machine.py     | 3/3 (LIFE-04)                |
| test_regulatory_calendar.py      | 1/1 (INFRA-05)               |
| test_jsonb_query.py              | 1/1 (CLIENT-06)              |
| **Phase 9 total**                | **129/129 GREEN**            |

### Regression baseline preserved (v1.0)

`docker compose exec backend pytest tests/test_admin.py tests/test_auth.py tests/test_documents.py` → 100/100 GREEN.

### Full backend suite

`docker compose exec backend pytest tests/ --ignore=tests/test_search.py` → **325 passed**, 24 warnings, 6.5s.

## User Setup Required

None. The new routers compose existing dependencies; no migrations, no new environment variables, no seed data required at this stage.

For developers continuing this work locally:
- Pull, restart `docker compose restart backend`, then `curl http://localhost:8000/docs#/compliance-clients` to render the new OpenAPI section.

For production deployment:
- No new external services
- No new migrations beyond Plan 04's head=0019
- Frontend (Plans 06-07) will need to set `X-Client-Id` header on every /api/compliance/* request

## Next Phase Readiness

**Plan 09-06 (Wave 5 — Frontend client switcher + onboarding wizard) — READY**

What's wired and waiting for the frontend:

- `GET /api/compliance/clients/me` returns the user's memberships — feeds the top-bar client switcher (D-22)
- `POST /api/compliance/clients` performs atomic onboarding — feeds the 4-step wizard (D-16)
- `GET /api/compliance/clients/{id}/dashboard` returns DashboardAggregates — feeds the per-client overview cards (CLIENT-03)
- OpenAPI spec at `/openapi.json` includes the full compliance section — frontend can use `openapi-typescript` to generate request/response types

**Wave 4 → Wave 5 handoff:**
- Plan 06 builds `/dashboard/compliance/clients/new` wizard + top-bar `<ClientSwitcher>` consuming the endpoints above
- "All Clients" view (CONTEXT D-23) toggles `X-Client-Id: *` on for compliance_head/ca_consultant/cfo only
- Plan 07 builds the notice list/detail/bulk surfaces consuming /api/compliance/notices/*

**Known partial-green tests (Plan 06/07 responsibility):**
- None backend-side. The frontend smoke checklist (09-VALIDATION.md "Manual-Only Verifications" table) is the next gate; it's manual because v1.0 has no Jest/Vitest infrastructure (Phase 11+ task per validation contract).

## Self-Check: PASSED

- [x] All 8 created files exist on disk:
  - backend/app/compliance/routers/__init__.py
  - backend/app/compliance/routers/clients.py
  - backend/app/compliance/routers/memberships.py
  - backend/app/compliance/routers/notices.py
  - backend/app/compliance/routers/reports.py
  - backend/app/compliance/routers/audit.py
  - backend/app/compliance/routers/notice_types.py
  - backend/app/compliance/routers/regulatory_calendar.py
- [x] backend/app/main.py modification present — `grep -c '/api/compliance' backend/app/main.py` returns 8 (7 mounts + 1 comment header)
- [x] All 4 task commits exist on main: `a33e57d, 6359acd, 16c3d96, c3532db`
- [x] App boots: `from app.main import app` exits 0 inside container after `docker compose restart backend`
- [x] All 18 OpenAPI compliance paths render via `app.openapi()`
- [x] 85/85 RBAC matrix tests pass (84 parametrized + 1 sanity)
- [x] 9/9 Phase 9 functional tests pass
- [x] 325/325 full backend suite (excl. pre-existing test_search flake) passes
- [x] 100/100 v1.0 regression preserved
- [x] Auth gate verified: TestClient GET /api/compliance/clients/me → 401 Not authenticated
- [x] Read-only audit endpoint: audit.py contains zero @router.post/put/delete
- [x] No v1.0 routes broken: documents/admin/auth/early_access still mounted

---
*Phase: 09-compliance-foundation*
*Completed: 2026-04-27*
