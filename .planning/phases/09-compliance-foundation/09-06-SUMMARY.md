---
phase: 09-compliance-foundation
plan: 06
subsystem: ui
tags: [zustand, react-query, react-hook-form, zod, multi-tenant, axios, nextjs15, react19]
status: complete
checkpoint_type: human-verify
checkpoint_task: 6
checkpoint_approved_at: "2026-04-27T10:32:00Z"
checkpoint_approval_signal: "APPROVED"

# Dependency graph
requires:
  - phase: 09-04
    provides: TenantContextMiddleware reads X-Client-Id header from frontend
  - phase: 09-05
    provides: 18 OpenAPI compliance endpoints frontend now consumes
provides:
  - "Zustand stores: useCurrentClient (activeClientId + crossClientMode), useOnboardingWizard (4-step persist)"
  - "complianceApi axios extension that auto-attaches X-Client-Id header"
  - "Top-bar ClientSwitcher with eligibility-gated cross-client toggle"
  - "4-step onboarding wizard (Details / Registrations / Team / Import) with localStorage resume"
  - "Team management page with 7-role chips and Auditor expiry visualization"
  - "AddMemberDialog and RoleDescriptionDrawer components"
  - "Compliance + Clients nav items in dashboard sidebar"
affects: [09-07, 10, 11, 12, 13, 14]

# Tech tracking
tech-stack:
  added:
    - "zustand@5 — multi-tenant state management with persist middleware"
    - "@tanstack/react-query@5 — server state caching for compliance pages"
    - "@tanstack/react-table@8 — reserved for Plan 09-07 notice table"
    - "react-hook-form@7 — wizard step forms (using getValues() per RESEARCH Pattern 6)"
    - "@hookform/resolvers@3 + zod@3 — schema validation per step"
    - "react-day-picker@9 — date pickers (v9 NOT v8 — React 19 compat)"
    - "papaparse@5 — reserved for CSV export in Plan 09-07"
    - "date-fns@3 — reserved for Plan 09-07 deadline formatting"
    - "eslint-config-next@15 — fills v1.0 lint configuration gap"
  patterns:
    - "Hybrid URL + Zustand state — URL for detail-page IDs, Zustand for in-memory wizard data"
    - "X-Client-Id header read on every request from store (not cached) so client switches are immediate"
    - "Membership validation on switcher mount — clears stale activeClientId if user no longer has access"
    - "Resume-banner UX (WCAG 2.2 SC 3.3.7 Redundant Entry) — wizard restores from localStorage"
    - "Auditor expiry visualization tier: dimmed+red expired, amber 'expires in N days', neutral default"

key-files:
  created:
    - "frontend/src/types/compliance.ts (15 types + 3 const maps)"
    - "frontend/src/stores/currentClientStore.ts"
    - "frontend/src/stores/onboardingWizardStore.ts"
    - "frontend/src/lib/api/compliance.ts (20 API methods)"
    - "frontend/src/components/compliance/ClientSwitcher.tsx"
    - "frontend/src/components/compliance/OnboardingWizard/WizardLayout.tsx"
    - "frontend/src/components/compliance/OnboardingWizard/StepDetails.tsx"
    - "frontend/src/components/compliance/OnboardingWizard/StepRegistrations.tsx"
    - "frontend/src/components/compliance/OnboardingWizard/StepTeam.tsx"
    - "frontend/src/components/compliance/OnboardingWizard/StepImport.tsx"
    - "frontend/src/components/compliance/AddMemberDialog.tsx"
    - "frontend/src/components/compliance/RoleDescriptionDrawer.tsx"
    - "frontend/src/app/dashboard/compliance/layout.tsx"
    - "frontend/src/app/dashboard/compliance/page.tsx"
    - "frontend/src/app/dashboard/compliance/clients/page.tsx"
    - "frontend/src/app/dashboard/compliance/clients/new/page.tsx"
    - "frontend/src/app/dashboard/compliance/clients/[id]/page.tsx"
    - "frontend/src/app/dashboard/compliance/clients/[id]/team/page.tsx"
    - "frontend/.eslintrc.json"
  modified:
    - "frontend/package.json (10 new deps incl. @types/papaparse + eslint-config-next)"
    - "frontend/package-lock.json"
    - "frontend/next.config.mjs (added eslint.ignoreDuringBuilds=true)"
    - "frontend/src/app/dashboard/layout.tsx (added Compliance + Clients nav items)"

key-decisions:
  - "Hybrid URL + Zustand: URL holds detail-page IDs and wizard step number; Zustand holds in-memory wizard form data and the active client. Single source of truth for tenant header is the store."
  - "Used getValues() not watch() for RHF per RESEARCH Pattern 6 (React 19 + RHF v7 watch() compatibility caveat) — placeholder updates via getValues() inside JSX render."
  - "react-day-picker v9 (not v8 as plan specified) because v8 caps React peer at 18; v1.0 stack is React 19. v9 declares react>=16.8.0 and works."
  - "Added eslint.ignoreDuringBuilds=true to next.config.mjs to restore v1.0 build behavior — installing eslint-config-next caused next build to fail on PRE-EXISTING v1.0 lint errors in dashboard/upload/page.tsx (5 react-hooks/rules-of-hooks)."
  - "Membership validation pattern: when ClientSwitcher receives fresh /memberships/me, it cross-checks the persisted activeClientId; if the user no longer has access (auditor expired, membership revoked), the store clears activeClientId so subsequent requests don't 403."
  - "Cross-client mode shows 'X-Client-Id: *' header (not omitted); backend Plan 04 enforces eligibility — frontend just renders the toggle when ROLES_ELIGIBLE_FOR_CROSS_CLIENT membership exists."

patterns-established:
  - "Compliance section layout pattern: top-level QueryClientProvider in /dashboard/compliance/layout.tsx so all compliance pages share react-query cache (memberships, clients, notices) across navigations"
  - "Step-form pattern (Wizard): each step is a self-contained RHF form; on submit the validated values are pushed into the Zustand store; the next step reads from the store as defaultValues. completedSteps array drives click-back-to-edit on the progress bar."
  - "Auditor row treatment: 3-tier visualization (default / amber expires-soon / red expired+dim) computed from access_end + now()"

requirements-completed:
  - CLIENT-01
  - CLIENT-02
  - CLIENT-03
  - CLIENT-04
  - CLIENT-05
  - CLIENT-06
  - RBAC-01
  - RBAC-02
  - RBAC-03
  - RBAC-04
  - RBAC-05
  - RBAC-06

# Metrics
duration: 23min (autonomous tasks 1-5; checkpoint task 6 user-verified APPROVED)
completed: "2026-04-27T10:32:00Z"
---

# Phase 09 Plan 06: Compliance Frontend Foundation — COMPLETE

**Multi-tenant compliance frontend foundation: Zustand stores, X-Client-Id auto-attach axios extension, top-bar ClientSwitcher with eligibility-gated cross-client toggle, 4-step onboarding wizard with localStorage resume, and team management page with 7-role chips + Auditor expiry visualization.**

## Status

**All 6 tasks complete.** User performed the 16-step manual smoke test on 2026-04-27 and signed off with `APPROVED`. Plan 09-07 (Wave 6 — final notice-centric surfaces) begins next.

## Performance

- **Duration so far:** ~23 min (T1 through T5)
- **Started:** 2026-04-27T09:56:26Z
- **Tasks committed:** 5 / 6
- **Files created:** 18
- **Files modified:** 4
- **Build status:** Production build passes (`npm run build` exits 0; 5 compliance routes compile)
- **UI-SPEC token usage:** 71 instances of `#09090b`/`#3b82f6`/zinc tokens across new files

## Accomplishments

- 9 npm packages installed (zustand, react-query, react-table, react-hook-form, @hookform/resolvers, zod, react-day-picker, papaparse, date-fns) + @types/papaparse + eslint-config-next
- 2 Zustand stores with persist middleware (currentClient + onboardingWizard)
- 1 axios extension (`complianceApi`) covering 20 endpoints, auto-attaches X-Client-Id from store on every call
- 1 ClientSwitcher with eligibility-gated cross-client toggle, search, membership validation
- 4-step onboarding wizard (Details / Registrations / Team / Import) with RHF + Zod validation, useFieldArray for dynamic registrations, GSTIN/PAN/CIN/DIN regex per row, Zustand persistence + resume banner
- Team management page with 7 equal-weight role chips, Auditor 3-tier expiry visualization (default / amber / red+dim), click-chip-to-see-permissions drawer
- Compliance + Clients nav items added to dashboard sidebar
- ESLint configured (v1.0 had no eslint-config — now `npm run lint` runs and `next build` skips lint via `eslint.ignoreDuringBuilds`)

## Task Commits

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Install npm packages + Zustand stores + types | `1b151e8` | package.json, package-lock.json, .eslintrc.json, types/compliance.ts, stores/currentClientStore.ts, stores/onboardingWizardStore.ts |
| 2 | complianceApi axios extension w/ X-Client-Id | `1617e51` | lib/api/compliance.ts |
| 3 | ClientSwitcher + compliance layout + dashboard nav | `6ec75f0` | components/compliance/ClientSwitcher.tsx, app/dashboard/compliance/layout.tsx, app/dashboard/layout.tsx |
| 4 | 4-step onboarding wizard | `9c33e2f` | OnboardingWizard/{WizardLayout,StepDetails,StepRegistrations,StepTeam,StepImport}.tsx, app/dashboard/compliance/clients/new/page.tsx |
| 5 | Client list + detail + team mgmt + dialog/drawer | `762c896` | app/dashboard/compliance/{page,clients/page,clients/[id]/page,clients/[id]/team/page}.tsx, components/compliance/{AddMemberDialog,RoleDescriptionDrawer}.tsx, next.config.mjs (eslint), lib/api/compliance.ts (Authority type fix), deferred-items.md |
| 6 | Manual smoke test (checkpoint) — APPROVED 2026-04-27T10:32Z | `182bc98` (partial summary commit) | 16-step smoke test executed by user; sign-off "APPROVED" |

## Files Created (18)

- `frontend/src/types/compliance.ts` — 15 type aliases + 3 const maps
- `frontend/src/stores/currentClientStore.ts` — useCurrentClient hook (persist)
- `frontend/src/stores/onboardingWizardStore.ts` — useOnboardingWizard hook (persist)
- `frontend/src/lib/api/compliance.ts` — complianceApi (20 methods)
- `frontend/src/components/compliance/ClientSwitcher.tsx`
- `frontend/src/components/compliance/AddMemberDialog.tsx`
- `frontend/src/components/compliance/RoleDescriptionDrawer.tsx`
- `frontend/src/components/compliance/OnboardingWizard/WizardLayout.tsx`
- `frontend/src/components/compliance/OnboardingWizard/StepDetails.tsx`
- `frontend/src/components/compliance/OnboardingWizard/StepRegistrations.tsx`
- `frontend/src/components/compliance/OnboardingWizard/StepTeam.tsx`
- `frontend/src/components/compliance/OnboardingWizard/StepImport.tsx`
- `frontend/src/app/dashboard/compliance/layout.tsx` — QueryClientProvider + sticky header
- `frontend/src/app/dashboard/compliance/page.tsx` — landing page (NEW — not in plan, see deviations)
- `frontend/src/app/dashboard/compliance/clients/page.tsx`
- `frontend/src/app/dashboard/compliance/clients/new/page.tsx`
- `frontend/src/app/dashboard/compliance/clients/[id]/page.tsx`
- `frontend/src/app/dashboard/compliance/clients/[id]/team/page.tsx`
- `frontend/.eslintrc.json` — minimal next/core-web-vitals config

## Files Modified (4)

- `frontend/package.json` — 10 new dependencies (incl. eslint-config-next)
- `frontend/package-lock.json` — corresponding lockfile updates
- `frontend/next.config.mjs` — added `eslint.ignoreDuringBuilds: true`
- `frontend/src/app/dashboard/layout.tsx` — added Compliance + Clients nav items + FiBriefcase import

## Decisions Made

1. **Hybrid URL + Zustand state.** URL is the source of truth for `clientId` on detail pages and `step` is *not* in the URL but kept in localStorage so users can come back to a draft from any starting URL. Zustand owns in-memory wizard data and active client.
2. **`getValues()` not `watch()` for RHF.** Per RESEARCH Pattern 6's React 19 + RHF v7 caveat — the placeholder for `registrations.{idx}.value` is computed inside the row map via `getValues(`registrations.${idx}.type`)`, NOT by subscribing with `watch()`.
3. **react-day-picker v9 (not v8).** v8's peer-deps cap React at 18; v1.0 stack is React 19. v9 declares `react >=16.8.0` and works.
4. **Cross-client header is `*`, not omitted.** Backend Plan 04 expects either `X-Client-Id: <int>` or `X-Client-Id: *`. Cross-client mode renders the latter; backend enforces eligibility per role.
5. **Membership validation on switcher mount.** When `/memberships/me` returns, ClientSwitcher cross-checks the persisted `activeClientId`; if missing (auditor expired, revoked) the store clears it so the next request doesn't 403.
6. **Auditor 3-tier expiry visualization.** Default neutral (no warning), amber "Expires in N days" if < 7 days, red "Expired" + dim if past `access_end`. Pure derived state from `access_end` + now().

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] react-day-picker v9 instead of v8**
- **Found during:** Task 1 (`npm install`)
- **Issue:** Plan specified `react-day-picker@8` but v8's peerDependencies cap react at `^16 || ^17 || ^18` — incompatible with v1.0's React 19. Install failed with `ERESOLVE` until I switched to v9.
- **Fix:** Used `react-day-picker@9` (peerDeps `react: >=16.8.0`)
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`
- **Verification:** `npm install` exits 0; build compiles.
- **Committed in:** `1b151e8`

**2. [Rule 1 — Bug] complianceApi paths were `/api/compliance/...` (would double-prefix)**
- **Found during:** Task 2 (writing the API client)
- **Issue:** Plan's example used absolute paths like `/api/compliance/clients/me`, but the existing `api` axios instance has `baseURL = ${API_URL}/api`. Sending requests to `/api/compliance/clients/me` would resolve to `${API_URL}/api/api/compliance/clients/me` and 404.
- **Fix:** Used relative paths `/compliance/clients/me` consistent with v1.0's documentsApi/authApi convention.
- **Files modified:** `frontend/src/lib/api/compliance.ts`
- **Verification:** All 20 method paths grep-confirmed; type-check passes.
- **Committed in:** `1617e51`

**3. [Rule 2 — Missing Critical] Added /dashboard/compliance index page**
- **Found during:** Task 5
- **Issue:** Plan added `Compliance` to the sidebar nav but had no route at `/dashboard/compliance`. Clicking the nav item would 404.
- **Fix:** Created `frontend/src/app/dashboard/compliance/page.tsx` — production-grade landing page with two tiles (Clients active link, Notices "Coming in Plan 09-07"). Not a placeholder stub.
- **Files modified:** `frontend/src/app/dashboard/compliance/page.tsx`
- **Verification:** `curl -sI http://localhost:3000/dashboard/compliance` returns 307 redirect to login (correct unauth behavior).
- **Committed in:** `762c896`

**4. [Rule 1 — Bug] CreateNoticePayload type mismatch**
- **Found during:** Task 5 (build step exposed it)
- **Issue:** `CreateNoticePayload extends Partial<ComplianceNotice>` declared `authority: string`, but the parent's `authority` is `Authority | undefined` — a discriminated union of `"GST" | "IT" | "MCA" | "RBI" | "SEBI"`. TypeScript correctly rejected the widening.
- **Fix:** Tightened to `authority: Authority`.
- **Files modified:** `frontend/src/lib/api/compliance.ts`
- **Verification:** `npm run build` exits 0.
- **Committed in:** `762c896`

**5. [Rule 3 — Blocking] next build fails on pre-existing v1.0 lint errors**
- **Found during:** Task 5 (build step)
- **Issue:** I installed `eslint-config-next` to make `npm run lint` work. Side effect: `next build` started running lint AND treats errors as fatal. There are 5 pre-existing v1.0 errors in `dashboard/upload/page.tsx` (react-hooks/rules-of-hooks — hooks declared inside an early-return guard). These predate Phase 09 and are scope-out per the SCOPE BOUNDARY rule.
- **Fix:** Added `eslint: { ignoreDuringBuilds: true }` to `frontend/next.config.mjs`. This restores v1.0's pre-existing build behavior (v1.0 never ran lint at build because no eslint-config was installed). `npm run lint` still works for new code review.
- **Files modified:** `frontend/next.config.mjs`, `.planning/phases/09-compliance-foundation/deferred-items.md` (logged the v1.0 errors for backlog)
- **Verification:** `npm run build` exits 0; 5 compliance routes compile.
- **Committed in:** `762c896`

---

**Total deviations:** 5 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing critical, 2 Rule 3 blocking)
**Impact on plan:** All deviations were necessary. No scope creep — the index page is the minimum needed for the nav item to function; the v1.0 lint errors are documented in deferred-items.md and not "fixed" (out of scope).

## Issues Encountered

- **Frontend container has no source bind-mount.** The `npm install` initially ran inside the running container but didn't persist to host disk. Worked around by using `docker cp` to extract the modified `package.json` + `package-lock.json` from the container, then running build/lint in a one-off `node:20-alpine` container with `-v /home/.../frontend:/app`. Final verification rebuilds the frontend image so the running container has the new code.

## Self-Check: PASSED

All 19 created/modified files exist on disk; all 5 task commits present in `git log`.

```
FOUND: frontend/src/types/compliance.ts
FOUND: frontend/src/stores/currentClientStore.ts
FOUND: frontend/src/stores/onboardingWizardStore.ts
FOUND: frontend/src/lib/api/compliance.ts
FOUND: frontend/src/components/compliance/ClientSwitcher.tsx
FOUND: frontend/src/components/compliance/AddMemberDialog.tsx
FOUND: frontend/src/components/compliance/RoleDescriptionDrawer.tsx
FOUND: frontend/src/components/compliance/OnboardingWizard/WizardLayout.tsx
FOUND: frontend/src/components/compliance/OnboardingWizard/StepDetails.tsx
FOUND: frontend/src/components/compliance/OnboardingWizard/StepRegistrations.tsx
FOUND: frontend/src/components/compliance/OnboardingWizard/StepTeam.tsx
FOUND: frontend/src/components/compliance/OnboardingWizard/StepImport.tsx
FOUND: frontend/src/app/dashboard/compliance/layout.tsx
FOUND: frontend/src/app/dashboard/compliance/page.tsx
FOUND: frontend/src/app/dashboard/compliance/clients/page.tsx
FOUND: frontend/src/app/dashboard/compliance/clients/new/page.tsx
FOUND: frontend/src/app/dashboard/compliance/clients/[id]/page.tsx
FOUND: frontend/src/app/dashboard/compliance/clients/[id]/team/page.tsx
FOUND: frontend/.eslintrc.json

FOUND: 1b151e8 (T1)
FOUND: 1617e51 (T2)
FOUND: 6ec75f0 (T3)
FOUND: 9c33e2f (T4)
FOUND: 762c896 (T5)
```

## User Verification — APPROVED

Task 6 (`checkpoint:human-verify`) PASSED. The 16-step manual smoke test from the plan was executed by the user at http://localhost:3000 on 2026-04-27 and signed off with `APPROVED`. Plan 09-07 (Wave 6 — notice-centric surfaces) begins immediately.

## Next Phase Readiness

**Ready for Plan 09-07** — the user has approved the checkpoint:
- Same `complianceApi` will be reused for notices/activity/audit/reports
- Same Zustand `useCurrentClient` store will drive the notice table tenant filter
- TanStack Table v8 is installed and ready for the notice table
- date-fns v3 + react-day-picker v9 are ready for deadline date pickers
- papaparse v5 is ready for CSV export of notices

**Carries forward to future phases:**
- All 7 ComplianceRole color tokens are locked in `COMPLIANCE_ROLE_COLORS` and reused everywhere
- `tenantHeaders()` pattern (read-on-each-call from store) is the canonical multi-tenant header pattern for future API methods

---
*Phase: 09-compliance-foundation*
*Status: complete — user APPROVED checkpoint on 2026-04-27T10:32Z; Plan 09-07 begins*
