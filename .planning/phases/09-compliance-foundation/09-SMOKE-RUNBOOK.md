# Phase 9 — Manual Smoke Test Runbook

**Status:** Phase 9 codebase is complete; this runbook is the **user-executed** verification gate (Task 7 of Plan 09-07). Once all sections pass, Phase 9 ships.

**Time budget:** 30-40 minutes if everything works first try; 60-90 if you find regressions.

---

## Pre-flight

### 1. Resolve the test infrastructure blocker (one-time, ~30 seconds)

Automated merge-gate tests currently fail with:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.InsufficientPrivilege)
permission denied to set role "app_runtime"
```

**Cause:** the connecting role `postgres.qogzcbxbcszheftinwdv` (Supabase pooler) is not a member of `app_runtime`, so `SET ROLE app_runtime` in the test conftest is denied.

**Fix:** on Supabase SQL Editor, run:

```sql
GRANT app_runtime TO "postgres.qogzcbxbcszheftinwdv";
GRANT app_migrator TO "postgres.qogzcbxbcszheftinwdv";
```

(The double quotes are required because the role name contains a `.`.)

**Verify the fix:**

```bash
docker compose exec backend pytest -x --no-header tests/test_rls_isolation.py::test_no_cross_client_leakage
```

Expected: `1 passed`. If still failing with permission denied, the GRANT didn't apply — re-run on Supabase and retry.

### 2. Bring the stack up

```bash
docker compose up -d
docker compose ps
```

All five services should show `healthy`: `smartdocs-db`, `smartdocs-redis`, `smartdocs-backend`, `smartdocs-celery`, `smartdocs-frontend`.

### 3. Seed test users (if you don't have them already)

You need at least **two distinct users** to verify cross-client isolation, and ideally a third with the **Auditor** role for time-bound expiry checks.

- User A: CA Consultant managing 2 clients
- User B: Compliance Head on Client A only
- User C: Auditor on Client A with `access_end` set to "in 7 days"

Use the `/dashboard/compliance/clients/new` wizard for User A → onboard 2 distinct clients with different GSTINs. Then assign User B and User C via the team management page.

---

## Section A: Notice Lifecycle (LIFE-01..08)

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| A1 | Login as User A. Navigate to `/dashboard/compliance/notices/new`. Upload a sample PDF (any compliance-style PDF) and fill the form: authority=GST, type=DRC-01, notice_number=`DRC-01/2026/A1`, received=today, deadline=today+30, tax_demand=10000, interest=500, penalty=2000. Submit. | Redirects to notice detail. Total liability = ₹12,500 displayed. PDF attachment visible. | |
| A2 | On notice detail, click "Mark Under Review" CTA. | Status pill fills with amber within 200ms. Activity timeline shows new entry. | |
| A3 | Try to advance status to "Submitted" via DevTools fetch (skip "Response Drafted"). | Backend returns 403; UI shows error toast listing valid next states. | |
| A4 | Walk the full chain: Received → Under Review → Response Drafted → Submitted → Resolved. | Each transition succeeds; activity timeline grows by one row per transition. | |
| A5 | Create a 2nd notice and link it to the 1st via parent_notice_id. | Detail page shows "Linked notices" section with chain. | |
| A6 | On dashboard, filter by authority=GST, status=Resolved. | Only the resolved notice from A4 appears. | |
| A7 | Select 2 notices via row checkboxes. Click "Update Status" → "Under Review". | Bar slides up from bottom <200ms. After submit, toast shows "Updated 2 of 2". | |
| A8 | Same as A7 but select one notice in `received` and one in `resolved` (resolved cannot transition to under_review). | Toast shows "Updated 1 of 2". Resolved row gets a red error indicator. | |

---

## Section B: Cross-Client Isolation (CLIENT-04, the security gate)

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| B1 | Login as User A. Switch to Client A. Note the dashboard's notice count. | Count = number of notices for Client A only. | |
| B2 | Switch to Client B via top-bar dropdown. | Notice list refreshes within 1 second; shows only Client B's notices. URL updates. | |
| B3 | DevTools → Network tab. Make a fetch to `/api/compliance/notices` with `X-Client-Id: <Client-A-ID>` while UI is on Client B. | Either 200 with Client A notices (if user has access) OR 403 (if user lacks Client A membership). NEVER mixed results from both clients. | |
| B4 | Login as User B (Compliance Head on Client A only). | Switcher shows only Client A. Client B is invisible. | |
| B5 | DevTools: try `X-Client-Id: <Client-B-ID>`. | 403 — "client membership required". | |

---

## Section C: Audit Trail Immutability (AUDIT-01, the legal gate)

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| C1 | Login as User A. Navigate to `/dashboard/compliance/audit`. | Audit log viewer renders. Immutability banner is visible at top: "These records are append-only and database-enforced." | |
| C2 | Inspect the page DOM/source. | NO edit buttons, NO delete buttons, NO inline-edit affordances anywhere. | |
| C3 | DevTools: try `fetch('/api/compliance/audit/1', { method: 'PUT', body: JSON.stringify({...}) })`. | 405 Method Not Allowed (router has no PUT/DELETE handler). | |
| C4 | DevTools: try `fetch('/api/compliance/audit/1', { method: 'DELETE' })`. | 405 Method Not Allowed. | |
| C5 | (Advanced — Supabase SQL editor) Connect as `app_runtime` (use the runtime password). Run `DELETE FROM audit_log WHERE id = 1;`. | Permission denied (`REVOKE DELETE ON audit_log FROM app_runtime`). | |

---

## Section D: RBAC Boundaries (RBAC-01..06)

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| D1 | Login as User C (Auditor). | Top-bar shows Auditor role chip. Most CTAs (Create Notice, Bulk Update, Approve) are disabled or hidden. | |
| D2 | User C: navigate to `/dashboard/compliance`. | Notice table renders read-only. Row hover shows "Read-only" tooltip on action affordances. | |
| D3 | Wait until User C's `access_end` passes (or change it to `now() - 1 hour` via SQL for instant test). Refresh dashboard. | "Access expired" banner appears. Notice list is empty / 403 from API. | |
| D4 | Login as a Staff role user. Try to approve a response. | Approve button is disabled / hidden. Direct API call returns 403 with permission name. | |
| D5 | Login as Legal Team. Try to approve a response. | Same — approve is reserved for Compliance Head. | |

---

## Section E: Onboarding Wizard (CLIENT-05)

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| E1 | Login as User A. Visit `/dashboard/compliance/clients/new`. | Wizard step 1 of 4 renders. Continue button disabled until name + type filled. | |
| E2 | Step 2: enter GSTIN `INVALID`. | Inline error appears below field within 200ms. Continue stays disabled. | |
| E3 | Step 2: enter `27AAAAA0000A1Z5`. | Error clears. Continue enables. | |
| E4 | Reload the page mid-wizard. | "Resume" banner appears with restored values. Step number persists. | |
| E5 | Complete all 4 steps. Submit. | Redirects to client detail page. New client appears in switcher dropdown. | |

---

## Section F: Visual Smoke (CSS / Layout)

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| F1 | Open notice detail at `>=lg` breakpoint (≥1024px). | Layout is 40/60 LEFT/RIGHT. Metadata + status workflow on left; activity timeline + attachments on right. | |
| F2 | Resize to mobile (`<md`, ~640px). | Single column. LEFT content (metadata + workflow) appears first. | |
| F3 | Open notice detail. Click status workflow CTA. | Optimistic UI: pill changes immediately, syncs to server within 1s. | |
| F4 | Audit viewer: verify color tokens use zinc/neutral (no hard-coded hex). | DevTools color picker on a row shows tokens like `bg-zinc-900` not raw hex. | |

---

## Sign-off

When all sections pass:

1. Update `.planning/STATE.md` `status` field to: `Phase 9 manual smoke verified by user — milestone v2.0 Phase 9 SHIPPED.`
2. Update `.planning/ROADMAP.md` Phase 9 row to `7/7 ✅ Shipped` with today's date in `Completed`.
3. Commit with `docs(09): manual smoke complete — Phase 9 shipped` (no Claude trailer per project rule).

Then Phase 10 is unblocked for `/gsd:research-phase 10`.

---

## What to do if something fails

- **Section A failure** → likely a regression in `notice_service` or router (Plan 09-05). Open an issue, isolate the failing transition, write a regression test before fixing.
- **Section B failure** → CRITICAL. Cross-client leakage is the security gate. Do not ship. Roll back to last known-good commit and re-investigate Plan 09-04 RLS middleware.
- **Section C failure** → CRITICAL. Audit immutability is the legal gate. Do not ship. Re-verify migration 0017 trigger + REVOKE statement; check no SECURITY DEFINER functions bypass it.
- **Section D failure** → permission registry regression. Re-run `tests/test_compliance_endpoints.py::test_role_permission_matrix` (84 cases) — it should fail in the same way.
- **Section E failure** → frontend regression. Run `docker compose exec frontend npm run lint` then `npm run dev` and check console.
- **Section F failure** → cosmetic, not a ship-blocker. File a Phase 11+ polish issue.

---

*Runbook created: 2026-04-28*
*Source: `.planning/phases/09-compliance-foundation/09-VALIDATION.md` "Manual-Only Verifications" section + Plan 09-07 Task 7*
