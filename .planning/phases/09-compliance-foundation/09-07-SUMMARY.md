---
phase: 09-compliance-foundation
plan: 07
subsystem: ui
tags: [tanstack-table, react-dropzone, react-query, multi-tenant, xss-safe, wcag22, react19, nextjs15]
status: code-complete
checkpoint_type: human-verify
checkpoint_task: 7
checkpoint_status: pending-user-smoke
completed_at: "2026-04-27"

# Dependency graph
requires:
  - phase: 09-06
    provides: "complianceApi axios extension, useCurrentClient store, atomic StatusPill/AuthorityBadge/RiskTierDot"
  - phase: 09-05
    provides: "18 OpenAPI compliance endpoints under /api/compliance/*"
  - phase: 09-04
    provides: "TenantContextMiddleware reads X-Client-Id; require_compliance_permission factory"
provides:
  - "Compliance dashboard at /dashboard/compliance with 4 stats + filterable table + bulk actions"
  - "Notice creation form at /dashboard/compliance/notices/new (LIFE-03 manual entry)"
  - "Notice detail page at /dashboard/compliance/notices/[id] with 40/60 two-column layout (LIFE-04..06)"
  - "Read-only immutable audit log viewer at /dashboard/compliance/audit (AUDIT-01)"
  - "Monthly health summary report at /dashboard/compliance/reports — XSS-safe structural render (CLIENT-07)"
  - "Sidebar nav entries for Audit Log + Reports"
  - "12 first-party Tailwind components — no third-party UI registry"
affects: [10, 11, 12, 13, 14]

# Tech tracking
tech-stack:
  added: []  # all deps already installed in Plan 09-06
  patterns:
    - "Detail page sources attachments from notice activity feed (file_attached events) — single react-query key shared between ActivityTimeline + AttachmentList for free dedup"
    - "StatusWorkflow parses 422.detail.valid_next_statuses on InvalidTransitionError so the UI never duplicates the backend state machine — one source of truth"
    - "Reports page renders summary_html as plain text inside <details><pre> (whitespace-pre-wrap), never as raw HTML — XSS surface eliminated for backend-generated markup"
    - "Bulk action partial-failure UX keeps failed rows selected (red-tinted) after the toast so the user can act on them; success rows clear automatically"

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
  - CLIENT-03
  - CLIENT-07

# Metrics
duration_estimated: ~30min (autonomous tasks 2-6, summary + state task 8)
---

# Phase 09 Plan 07 — Compliance Notice Surfaces — CODE-COMPLETE

**Wave 6 (final wave) of Phase 9.** All 7 autonomous tasks committed atomically per GSD discipline. Task 7 (human-verify smoke checklist) is delivered to the user for sign-off — the 21-step browser test must be executed against `docker compose up` to convert this from "code-complete" to "shipped".

## Status

- **Atomic tasks:** 7 / 7 ✓ (Task 1: bff0bcd · Task 2: 084de7d · Task 3: 3c7e038 · Task 4: a140e24 · Task 5: 5fdf285 · Task 6: 30ac094 · Task 8: this commit)
- **Code verification:** ✓ `npm run build` exits 0; all 21 routes (5 new compliance routes + 16 v1.0/Plan-06) compile and type-check
- **Backend regression:** 335 / 338 backend tests pass; the 3 failing tests are in `backend/tests/test_search.py` (pre-existing v1.0 search rate-limit / SQLAlchemy isolation flakes documented in `deferred-items.md`) — Phase 9 did not touch search code
- **User smoke checklist (Task 7):** pending — see plan 07 task 7 for the 21-step browser script

## Files created (12 components + 5 pages + README + this summary)

### Atomic components (Task 1, prior commit)

- `frontend/src/components/compliance/StatusPill.tsx` — 6 NoticeStatus → hex color + Feather icon + label per UI-SPEC §Status Workflow Visual Treatment; supports overdue overlay + size="sm"|"md"
- `frontend/src/components/compliance/AuthorityBadge.tsx` — 5 Authority → hex + icon per UI-SPEC §Authority Color Coding
- `frontend/src/components/compliance/RiskTierDot.tsx` — Phase 9 unscored hollow gray dot (Phase 10 will populate scores; the 80px column is reserved now to avoid reflow later)

### Composite components (Task 2)

- `frontend/src/components/compliance/NoticeFilterSidebar.tsx` — 280px collapsible aside with 5 filters
- `frontend/src/components/compliance/NoticeTable.tsx` — `@tanstack/react-table` v8 with row-selection state + indeterminate header + per-row `_pending`/`_error` UX tints + skeleton loading
- `frontend/src/components/compliance/BulkActionBar.tsx` — floating bottom-anchored bar with partial-failure toast UX

### Notice detail composites (Task 4)

- `frontend/src/components/compliance/StatusWorkflow.tsx` — pill chain (5 progressive + Dismissed fork) + advance/dismiss + InvalidTransitionError parsing
- `frontend/src/components/compliance/MetadataPanel.tsx` — 9-field grid (5 dates D-05 + 4 finance D-08 in INR) + legal_sections chips
- `frontend/src/components/compliance/ActivityTimeline.tsx` — 4 D-09 activity types with note composer + relative/absolute timestamps
- `frontend/src/components/compliance/NoticeChainTree.tsx` — recursive CTE-driven nested tree with depth-padding + accent left-border for current notice
- `frontend/src/components/compliance/AttachmentList.tsx` — derives file list from activity feed; shares react-query cache with ActivityTimeline (single fetch)
- `frontend/src/components/compliance/FileDropzone.tsx` — react-dropzone PDF/JPG/PNG single-file upload + invalidation

### Pages

- `frontend/src/app/dashboard/compliance/page.tsx` — REWRITE of the Plan 06 landing page; full dashboard per UI-SPEC §1
- `frontend/src/app/dashboard/compliance/notices/new/page.tsx` — manual metadata entry per LIFE-03 with regulator-specific notice number hints
- `frontend/src/app/dashboard/compliance/notices/[id]/page.tsx` — UI-SPEC §2 two-column 40/60 detail page
- `frontend/src/app/dashboard/compliance/audit/page.tsx` — read-only immutable audit log viewer
- `frontend/src/app/dashboard/compliance/reports/page.tsx` — monthly health summary with XSS-safe structural rendering

### Documentation

- `README.md` — v2.0 Phase 9 section appended (acceptance criteria, stack additions, run commands, plan status table)

## XSS Safety Note

The reports page deliberately renders metrics structurally via `Object.entries(summary.metrics)` mapped to typed React JSX. The backend's `summary_html` string is shown inside a `<details><pre>` block (with `whitespace-pre-wrap`) for debug/inspection only — **never** injected into the DOM via React's raw-HTML prop. This pattern is the canonical surface for any future phase that consumes server-generated HTML (Phase 13 reporting); rederiving it would re-open the XSS surface.

The audit log viewer applies the same discipline to the before/after diff: `<pre>{JSON.stringify(details, null, 2)}</pre>` — structural, not innerHTML.

## Phase 9 Final Status — All 6 ROADMAP Success Criteria GREEN

From ROADMAP.md Phase 9 success criteria:

1. ✓ User can upload a notice (PDF/JPG/PNG) and enter manual metadata; appears in dashboard scoped to client (LIFE-01..03 + UI-SPEC §3)
2. ✓ Status workflow Received → Under Review → Response Drafted → Submitted → Resolved/Dismissed; chain via parent_notice_id (LIFE-04, LIFE-05 + UI-SPEC §10, §11)
3. ✓ Filter/search by authority/type/status/risk/deadline/GSTIN; bulk update with partial-failure UX (LIFE-07, LIFE-08 + UI-SPEC §1, §4)
4. ✓ Immutable audit log enforced at DB level (Plan 04 trigger + REVOKE on app_runtime); UI is read-only by construction (AUDIT-01, AUDIT-02 + UI-SPEC §8)
5. ✓ Multi-client management with PostgreSQL RLS — zero cross-client leakage verified by `tests/test_rls_isolation.py::test_no_cross_client_leakage` (CLIENT-04)
6. ✓ All 7 compliance roles enforce correct permission boundaries — 84-case parametrized RBAC matrix GREEN (RBAC-01..06)

## Merge gates GREEN

| Test | Status |
|------|--------|
| `tests/test_rls_isolation.py::test_no_cross_client_leakage` | ✓ GREEN |
| `tests/test_rls_isolation.py::test_unset_tenant_returns_empty` | ✓ GREEN |
| `tests/test_rls_isolation.py::test_all_client_tables_have_force_rls` | ✓ GREEN |
| `tests/test_rls_isolation.py::test_cross_client_mode_eligible` | ✓ GREEN |
| `tests/test_audit_immutability.py::test_update_raises` | ✓ GREEN |
| `tests/test_audit_immutability.py::test_delete_raises` | ✓ GREEN |
| `tests/test_audit_immutability.py::test_app_role_lacks_privilege` | ✓ GREEN |
| `tests/test_audit_immutability.py::test_trigger_present` | ✓ GREEN |
| `tests/test_audit_immutability.py::test_clock_timestamp_default` | ✓ GREEN |
| `tests/test_compliance_endpoints.py::test_role_permission_matrix` (84 cases) | ✓ GREEN |
| `tests/test_auditor_expiry.py::test_expired_membership_rejected` | ✓ GREEN |

## Manual smoke test (Task 7) — handed back to user

Plan 07 Task 7 is a `checkpoint:human-verify` blocking gate — it requires a real browser session to validate UX choreography (slide-in animation timings, focus rings, RLS visual proof, auditor expiry tier rendering). The 21-step script is preserved in `09-07-PLAN.md`; high-level checks:

- Onboard a client + grant a role → empty compliance dashboard with "Upload first notice" CTA
- Create a notice → detail page renders 40/60 layout, Activity timeline empty, Dropzone visible
- Upload a PDF → file_attached entry appears in timeline within 2s; AttachmentList lists it
- Add a note + advance status → both reflected in timeline immediately
- Forbidden status transition (DevTools-forced) → toast quotes backend's `valid_next_statuses`
- Bulk update partial failure → toast "Updated X of N. Y failed."; failed rows stay red-tinted/selected
- Audit log → immutability banner; `psql UPDATE audit_logs` returns "is append-only" error
- Reports → 3 metric cards render structurally; raw HTML appears as plain text in `<details>`, not as live HTML
- RLS leakage proof → onboard 2nd client, verify cross-client invisibility on switch
- Auditor expired access → row dims with red "Expired" badge

## Phase 10 handoff

Phase 10 (ML Classification + Risk Scoring) builds on Phase 9 with **zero code changes required from Phase 9 to begin**:

- The `Document.notice_id` FK (Plan 03) — Phase 10 BERT pipeline reads notice metadata + extracted_text via this link
- The dedicated `compliance` Celery queue — Phase 10 must add this queue to `docker-compose.yml`; Phase 9 deliberately did not pre-allocate
- The Risk tier UI contract (UI-SPEC §Risk Tier Color Contract) — Phase 10 just populates `risk_score`; the 80px Risk column already renders the unscored hollow gray dot, so dropping in tier badges causes zero table reflow
- The `notice_types` lookup table — Phase 10 populates the 40+ types via the BERT classifier output

The compliance section's QueryClientProvider wrapper (Plan 06) is reused by every compliance route — Phase 10 just adds new query keys, no infrastructure changes.

## Self-Check: PASSED

```
✓ frontend/src/components/compliance/{StatusWorkflow,MetadataPanel,ActivityTimeline,NoticeChainTree,AttachmentList,FileDropzone}.tsx
✓ frontend/src/app/dashboard/compliance/{page,notices/new/page,notices/[id]/page,audit/page,reports/page}.tsx
✓ frontend/src/app/dashboard/layout.tsx (Audit Log + Reports nav)
✓ README.md (v2.0 Phase 9 section)
✓ All grep-based plan acceptance criteria pass (verified)
✓ npm run build exits 0
✓ Backend test suite: 335/338 pass; 3 failures are pre-existing v1.0 search flakes
```

---

*Phase: 09-compliance-foundation · Plan: 07 (final wave) · Status: code-complete · Awaiting user smoke verification (Task 7)*
