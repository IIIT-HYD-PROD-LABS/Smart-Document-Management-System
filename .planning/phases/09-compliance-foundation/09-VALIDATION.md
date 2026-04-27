---
phase: 9
slug: compliance-foundation
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-27
updated: 2026-04-27
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + httpx 0.25.2 + pytest-freezer 0.4.9 + freezegun 1.5.5 |
| **Config file** | `backend/tests/conftest.py` (extended in Plan 09-01 with db_as_app_runtime, client_a, client_b, audit_log_row, auditor_membership, client_with_membership fixtures) |
| **Quick run command** | `docker compose exec backend pytest -x --no-header -q` |
| **Quick run (single file)** | `docker compose exec backend pytest -x --no-header -q tests/<file>.py` |
| **Full suite command** | `docker compose exec backend pytest --tb=short tests/` |
| **Integration-only** | `docker compose exec backend pytest -m integration --tb=short tests/` |
| **Frontend lint** | `docker compose exec frontend npm run lint` |
| **Estimated runtime** | ~120 seconds (full suite, post-Plan-05); ~15 seconds (unit-only, no integration mark) |

---

## Sampling Rate

- **After every task commit:** Run `docker compose exec backend pytest -x --no-header -q tests/<scope>.py` (the file under work). Required latency budget: <30 seconds.
- **After every plan wave:** Run `docker compose exec backend pytest --tb=short tests/` — full suite must pass. Critical: must include `test_rls_isolation.py` and `test_audit_immutability.py` — these are the security gates.
- **Before `/gsd:verify-work`:** Full suite green + frontend lint green + manual smoke checklist green.
- **Pre-deploy:** Re-run RLS isolation test against actual production-shape DB (CI runs against Postgres container with `app_runtime` role created by Plan 02 migration).
- **Max feedback latency:** 60 seconds for any single task (use focused file path).

---

## Per-Task Verification Map

| Plan | Task | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01 | T1 (pytest-freezer) | 0 | INFRA (test infra) | infra | `grep -E "^pytest-freezer==0\.4\.9$" backend/requirements.txt` | n/a | ⬜ pending |
| 09-01 | T2 (conftest fixtures) | 0 | INFRA (test infra) | infra | `python -c "from backend.tests.conftest import db_as_app_runtime"` | ✅ created in this plan | ⬜ pending |
| 09-01 | T3 (RLS test stubs) | 0 | CLIENT-04 | integration | `python -c "import ast; ast.parse(open('backend/tests/test_rls_isolation.py').read())"` | ✅ created in this plan | ⬜ pending |
| 09-01 | T4 (audit immutability test stubs) | 0 | AUDIT-01, INFRA-07 | integration | `python -c "import ast; ast.parse(open('backend/tests/test_audit_immutability.py').read())"` | ✅ created in this plan | ⬜ pending |
| 09-01 | T5 (RBAC matrix) | 0 | RBAC-01..06 | integration | `python -c "from backend.tests.test_compliance_endpoints import ROLE_PERMISSION_MATRIX; assert len(ROLE_PERMISSION_MATRIX)==84"` | ✅ created in this plan | ⬜ pending |
| 09-01 | T6 (other test stubs) | 0 | LIFE-01..08, CLIENT-01..07, INFRA-05/06 | integration/unit | `for f in test_notice_state_machine test_indian_validators ...; do python -c "import ast; ast.parse(open(\"backend/tests/$f.py\").read())"; done` | ✅ created in this plan | ⬜ pending |
| 09-01 | T7 (validation doc) | 0 | INFRA (validation contract) | doc | `grep -E "nyquist_compliant: true" .planning/phases/09-compliance-foundation/09-VALIDATION.md` | self | ⬜ pending |
| 09-02 | T1 (DB roles) | 1 | CLIENT-04, INFRA-07 | integration | `docker compose exec backend pytest -x tests/test_audit_immutability.py::test_app_role_lacks_privilege` | ✅ Plan 01 | ✅ green |
| 09-02 | T2 (RLS migrations) | 1 | CLIENT-04 | integration | `docker compose exec backend pytest -x tests/test_rls_isolation.py::test_all_client_tables_have_force_rls` | ✅ Plan 01 | ✅ green |
| 09-02 | T3 (audit immutability migration) | 1 | AUDIT-01, AUDIT-02, INFRA-07 | integration | `docker compose exec backend pytest -x tests/test_audit_immutability.py::test_trigger_present tests/test_audit_immutability.py::test_clock_timestamp_default` | ✅ Plan 01 | ✅ green |
| 09-02 | T4 (Indian validators) | 1 | LIFE-03 | unit | `docker compose exec backend pytest -x tests/test_indian_validators.py` | ✅ Plan 01 | ✅ green |
| 09-02 | T5 (PII encryption + log redaction) | 1 | INFRA-06 | unit | `docker compose exec backend pytest -x tests/test_pii_encryption.py tests/test_log_redaction.py` | ✅ Plan 01 | ✅ green |
| 09-02 | T6 (permission registry) | 1 | RBAC-01..06 | unit | `docker compose exec backend pytest -x tests/test_permission_registry.py` | ✅ Plan 01 | ✅ green |
| 09-02 | T7 (state machine) | 1 | LIFE-04 | unit | `docker compose exec backend pytest -x tests/test_notice_state_machine.py` | ✅ Plan 01 | ✅ green |
| 09-02 | T8 (regulatory calendar seed) | 1 | INFRA-05 | integration | `docker compose exec backend pytest -x tests/test_regulatory_calendar.py` | ✅ Plan 01 | ⚠️ partial — 12 rows seeded; ORM model from Plan 03 needed for test |
| 09-03 | T1 (Client + Registration models) | 2 | CLIENT-01, CLIENT-02, CLIENT-06 | integration | `docker compose exec backend pytest -x tests/test_client_management.py tests/test_jsonb_query.py` | ✅ Plan 01 | ✅ green |
| 09-03 | T2 (Membership model) | 2 | RBAC-04, CLIENT-04 | integration | `docker compose exec backend pytest -x tests/test_auditor_expiry.py` | ✅ Plan 01 | ⚠️ partial — model in place; auditor_expiry middleware (Plan 04) pending |
| 09-03 | T3 (Notice + activity + tags) | 2 | LIFE-01, LIFE-04, LIFE-05, LIFE-09 | integration | `docker compose exec backend pytest -x tests/test_compliance_notices.py tests/test_notice_chain.py` | ✅ Plan 01 | ✅ green |
| 09-03 | T4 (notice service + state machine wiring) | 2 | LIFE-04, LIFE-08, AUDIT-02 | integration | `docker compose exec backend pytest -x tests/test_notice_service.py tests/test_audit_capture.py` | ✅ Plan 01 | ✅ green |
| 09-03 | T5 (client + onboarding service) | 2 | CLIENT-05, CLIENT-03, CLIENT-07 | integration | `docker compose exec backend pytest -x tests/test_client_onboarding.py tests/test_dashboard.py tests/test_reports.py` | ✅ Plan 01 | ✅ green |
| 09-03 | DEVIATION (mig 0018 — RLS recursion fix) | 2 | CLIENT-04 (defense) | DDL fix | `docker compose exec backend alembic current` | new file | ✅ green (head=0018) |
| 09-03 | T6 (notice_service.py) | 2 | LIFE-04, LIFE-05, LIFE-07, LIFE-08, AUDIT-02 | integration | `docker compose exec backend pytest -x tests/test_notice_service.py tests/test_audit_capture.py tests/test_notice_chain.py tests/test_compliance_notices.py tests/test_notice_query.py` | ✅ Plan 01 | ✅ green (8/8) |
| 09-03 | T7 (client_service + report_service) | 2 | CLIENT-03, CLIENT-05, CLIENT-07 | integration | `docker compose exec backend pytest -x tests/test_client_management.py tests/test_jsonb_query.py tests/test_client_onboarding.py tests/test_dashboard.py tests/test_reports.py tests/test_regulatory_calendar.py` | ✅ Plan 01 | ✅ green (6/6) |
| 09-03 | T8 (Wave 2 verification) | 2 | (all above) | integration | full Wave 2 + regression | n/a | ✅ green (15 Wave 2 + 121 regression) |
| 09-04 | T1 (tenant context middleware) | 3 | CLIENT-04 | integration | `docker compose exec backend pytest -x tests/test_rls_isolation.py::test_no_cross_client_leakage` | ✅ Plan 01 | ✅ green |
| 09-04 | T2 (auditor expiry middleware) | 3 | RBAC-04 | integration | `docker compose exec backend pytest -x tests/test_auditor_expiry.py` | ✅ Plan 01 | ✅ green (3/3) |
| 09-04 | T3 (require_compliance_permission factory) | 3 | RBAC-01..06 | integration | `docker compose exec backend pytest -x tests/test_compliance_endpoints.py` | ✅ Plan 01 | ✅ green (85/85) |
| 09-04 | T4 (wire middleware in main.py + user_id ContextVar in security.py) | 3 | CLIENT-04, RBAC-01..06 | integration | `docker compose exec backend python -c "from app.main import app; assert 'TenantContextMiddleware' in [m.cls.__name__ for m in app.user_middleware]"` | ✅ Plan 01 | ✅ green |
| 09-04 | T5 (Wave 0 merge gates GREEN) | 3 | CLIENT-04, RBAC-01..06, AUDIT-01 | integration | `docker compose exec backend pytest tests/test_compliance_endpoints.py tests/test_rls_isolation.py tests/test_auditor_expiry.py tests/test_audit_immutability.py` | ✅ Plan 01 | ✅ green (98/98) |
| 09-04 | DEVIATION (mig 0019 — fail-closed on empty tenant) | 3 | CLIENT-04 (defense) | DDL fix | `docker compose exec backend alembic current` | new file | ✅ green (head=0019) |
| 09-05 | T1 (clients + memberships routers) | 4 | CLIENT-01, CLIENT-05 | integration | `docker compose exec backend pytest -x tests/test_client_management.py tests/test_client_onboarding.py` | ✅ Plan 01 | ⬜ pending |
| 09-05 | T2 (notices + bulk router) | 4 | LIFE-01, LIFE-07, LIFE-08 | integration | `docker compose exec backend pytest -x tests/test_compliance_notices.py tests/test_notice_query.py` | ✅ Plan 01 | ⬜ pending |
| 09-05 | T3 (reports + audit viewer router) | 4 | CLIENT-07, AUDIT-01 | integration | `docker compose exec backend pytest -x tests/test_reports.py` | ✅ Plan 01 | ⬜ pending |
| 09-06 | T1-T4 (frontend client switcher + onboarding wizard) | 5 | CLIENT-05, CLIENT-04 (UI part) | manual smoke | manual click-through, lint: `docker compose exec frontend npm run lint` | n/a (manual) | ⬜ pending |
| 09-07 | T1-T5 (frontend notice surfaces) | 6 | LIFE-01..08, AUDIT-01 (UI part) | manual smoke + lint | manual click-through, lint: `docker compose exec frontend npm run lint` | n/a (manual) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All Wave 0 dependencies for Phase 9 listed below. **Plan 09-01 creates ALL of these**, ensuring every per-task `<automated>` command in plans 09-02..09-07 has a real file/symbol to point at.

- [x] `backend/tests/test_rls_isolation.py` — stubs for CLIENT-04 (5 tests including merge gate `test_no_cross_client_leakage`)
- [x] `backend/tests/test_audit_immutability.py` — stubs for AUDIT-01, INFRA-07 (5 tests including merge gates `test_update_raises`, `test_delete_raises`)
- [x] `backend/tests/test_compliance_endpoints.py` — stubs for RBAC-01..06 (parametrized 7×12=84 case matrix; merge gate `test_role_permission_matrix`)
- [x] `backend/tests/test_notice_state_machine.py` — stubs for LIFE-04
- [x] `backend/tests/test_indian_validators.py` — stubs for LIFE-03
- [x] `backend/tests/test_pii_encryption.py` — stubs for INFRA-06
- [x] `backend/tests/test_log_redaction.py` — stubs for INFRA-06
- [x] `backend/tests/test_permission_registry.py` — stubs for RBAC-01..06
- [x] `backend/tests/test_auditor_expiry.py` — stubs for RBAC-04
- [x] `backend/tests/test_audit_capture.py` — stubs for AUDIT-02
- [x] `backend/tests/test_notice_chain.py` — stubs for LIFE-05
- [x] `backend/tests/test_notice_query.py` — stubs for LIFE-07
- [x] `backend/tests/test_compliance_notices.py` — stubs for LIFE-01, LIFE-08
- [x] `backend/tests/test_client_management.py` — stubs for CLIENT-01, CLIENT-02
- [x] `backend/tests/test_client_onboarding.py` — stubs for CLIENT-05
- [x] `backend/tests/test_jsonb_query.py` — stubs for CLIENT-06
- [x] `backend/tests/test_dashboard.py` — stubs for CLIENT-03
- [x] `backend/tests/test_reports.py` — stubs for CLIENT-07
- [x] `backend/tests/test_regulatory_calendar.py` — stubs for INFRA-05
- [x] `backend/tests/test_notice_service.py` — stubs for LIFE-04, AUDIT-02
- [x] `backend/tests/conftest.py` — shared fixtures: `db_as_app_runtime`, `client_a`, `client_b`, `audit_log_row`, `auditor_membership`, `client_with_membership`
- [x] Framework install: `pytest-freezer==0.4.9`, `freezegun==1.5.5` (added to backend/requirements.txt)

---

## Manual-Only Verifications

Frontend smoke tests (Plans 09-06, 09-07) are MANUAL because v1.0 has no Jest/Vitest infrastructure and adding it for one phase is overkill. Phase 9 ships manual smoke tests; comprehensive frontend testing is a Phase 11+ infrastructure task.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Onboarding wizard validates GSTIN/PAN per step | CLIENT-05 | No frontend test runner in v1.0 | (1) Visit `/dashboard/compliance/clients/new`. (2) Step 2: enter GSTIN `INVALID` → error appears below the field. (3) Enter `27AAAAA0000A1Z5` → error clears, "Continue" button enables. |
| Wizard state persists across refresh | CLIENT-05 | Browser-only test | (1) Onboard wizard step 2: enter 1 GSTIN. (2) Reload page. (3) Resume banner appears with restored values. |
| Client switcher shows correct memberships | CLIENT-04 (UI) | Browser-only | (1) Login as user with 2 client memberships. (2) Click switcher dropdown. (3) Both clients appear. (4) Switch to Client B. (5) Notice list updates without page refresh. |
| "All Clients" mode visible only to eligible roles | CLIENT-04 (UI) | Browser-only | (1) Login as Staff (ineligible). (2) Open switcher. (3) "View all clients" toggle is NOT visible. (4) Login as CA Consultant. (5) Toggle IS visible. |
| Bulk action bar mounts on row selection | LIFE-08 (UI) | Visual smoke | (1) Visit `/dashboard/compliance`. (2) Click checkbox on a row. (3) Bar slides up from bottom within 200ms. (4) Click "Clear selection" — bar slides down. |
| Bulk action partial failure UX | LIFE-08 (UI) | Visual smoke | (1) Select 2 notices: one in "received", one in "resolved". (2) Bulk update to "under_review". (3) Toast shows "Updated 1 of 2". (4) Resolved notice row shows red error indicator. |
| Notice detail two-column layout | LIFE-06 (UI) | Visual smoke | (1) Open any notice detail. (2) Layout is 40/60 LEFT/RIGHT on lg+. (3) On <md, collapses to single column with LEFT first. |
| Status workflow advance button | LIFE-04 (UI) | Browser-only | (1) Open notice in "received" status. (2) Primary CTA reads "Mark Under Review" in accent blue. (3) Click → optimistic update, pill fills with amber. (4) Activity timeline shows new entry within 200ms. |
| Forbidden status transition feedback | LIFE-04 (UI) | Visual smoke | (1) Notice in "received". (2) DevTools: try to dispatch transition to "submitted" via API call. (3) Backend rejects (403); frontend shows error toast with valid next states. |
| Audit log viewer is read-only | AUDIT-01 (UI) | Visual smoke | (1) Open `/dashboard/compliance/audit`. (2) No edit/delete buttons exist. (3) Immutability banner is visible at top. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (each plan has unit/integration commands at Wave 1+)
- [x] Wave 0 covers all MISSING references (every test file referenced in plan `<verify>` blocks exists in Plan 09-01)
- [x] No watch-mode flags
- [x] Feedback latency < 60s per task (using focused test file)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (Plan 09-01 establishes Wave 0; downstream plans reference these test files in their verify commands)

**Test merge gates (must pass before any feature plan merges):**
1. `tests/test_rls_isolation.py::test_no_cross_client_leakage` — CLIENT-04 zero-leakage
2. `tests/test_audit_immutability.py::test_update_raises` — AUDIT-01 trigger blocks UPDATE
3. `tests/test_audit_immutability.py::test_delete_raises` — AUDIT-01 trigger blocks DELETE
4. `tests/test_audit_immutability.py::test_app_role_lacks_privilege` — REVOKE verified
5. `tests/test_compliance_endpoints.py::test_role_permission_matrix` — RBAC-01..06 (84 parametrized cases)
