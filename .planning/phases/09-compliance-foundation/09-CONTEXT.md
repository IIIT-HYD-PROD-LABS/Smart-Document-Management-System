# Phase 9: Compliance Foundation - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can manually track compliance notices end-to-end with full audit trail, multi-client support, and role-based access control. This phase builds the data models, RBAC, client architecture, and compliance dashboard UI. NO AI/ML classification, NO automated retrieval, NO alert system, NO response drafting — those are Phases 10-14.

</domain>

<decisions>
## Implementation Decisions

### Notice Data Model
- **D-01:** Authority as Python enum (GST, IT, MCA, RBI, SEBI). Notice types as a separate `notice_types` DB lookup table with authority FK — admins can add new types without code deploys.
- **D-02:** Separate `ComplianceNotice` model (not extending Document). Links to Document via FK for uploaded files. Clean separation, zero v1.0 regression risk.
- **D-03:** Status workflow enforced via state machine in Python dict. Valid transitions: Received → Under Review → Response Drafted → Submitted → Resolved/Dismissed. Every transition logged to audit trail.
- **D-04:** Notice chaining via `parent_notice_id` FK on ComplianceNotice. Recursive CTE for chain queries. Handles SCN → Assessment → Demand → Appeal hierarchy.
- **D-05:** Multiple deadline fields: `response_deadline`, `hearing_date`, `compliance_date`, `appeal_deadline`. Indian compliance notices have multi-stage timelines.
- **D-06:** Manual metadata entry only in Phase 9. AI extraction (BERT + NER) deferred to Phase 10.
- **D-07:** Regex validation per authority for notice numbers (DRC-01/ASMT-10 patterns for GST, u/s 143(2) for IT, etc.).
- **D-08:** Structured financial fields: `tax_demand`, `interest`, `penalty`, `total_liability` (all Decimal, INR). Enables audit reporting.
- **D-09:** Dedicated `NoticeActivity` table for user-facing activity timeline — separate from system audit_log. Captures status_change, note_added, file_attached, assigned.
- **D-10:** Notice-linked documents via existing Document model with `notice_id` FK. Reuses v1.0 upload/OCR pipeline for response drafts and evidence.
- **D-11:** Simple tags via `notice_tags` junction table. Custom labels for organization (branch, quarter, review round).
- **D-12:** Legal section references stored as JSON array. Displayed as badges. Placeholder links for regulation library (Phase 12).

### Client & Multi-Entity Architecture
- **D-13:** PostgreSQL RLS via `set_config('app.current_client_id')` in middleware. RLS policies on all client-scoped tables. Zero cross-client leakage guarantee (CLIENT-04).
- **D-14:** Many-to-many Client-User via `ClientMembership(user_id, client_id, compliance_role)`. CAs manage multiple clients with potentially different roles per client.
- **D-15:** Separate `ClientRegistration` table: `client_id`, `type` (GSTIN/PAN/CIN/DIN), `value`, `state` (for GSTIN), `is_active`. Multi-GSTIN per client. Notices link to `registration_id`.
- **D-16:** Multi-step client onboarding wizard: Details → Registrations → Team Assignment → Import.
- **D-17:** Per-client config overrides via `config_overrides` JSONB column on Client model. Stores alert rules, approval workflows, deadline thresholds.
- **D-18:** Real-time query aggregation for per-client dashboard. No pre-computed stats table — sufficient at early scale.
- **D-19:** On-demand report generation (user clicks → Celery computes → returns PDF/HTML). No scheduled monthly jobs yet.
- **D-20:** No client branding/logo in Phase 9. Focus on core data.
- **D-21:** v1.0 documents remain user-scoped. Only compliance notices are client-scoped. No migration of existing documents.
- **D-22:** Top-bar client switcher dropdown in dashboard header. Instant context switch. Workspace-style UX (Slack/Notion pattern).
- **D-23:** "All Clients" view available in switcher for CA/Compliance Head roles. Cross-client dashboard with client column in tables.

### Extended RBAC (7 Compliance Roles)
- **D-24:** Parallel role systems — v1.0 system roles (admin/editor/viewer) govern document management. Compliance roles govern compliance features. Users have BOTH.
- **D-25:** 7 compliance roles: Compliance Head, Legal Team, Finance Team, Auditor, CA/Consultant, Staff, CFO.
  - **Compliance Head:** View all, approve responses, reports, configure escalation
  - **Legal Team:** Draft responses, regulation library, authority-scoped notices
  - **Finance Team:** View tax notices (GST/IT), reconciliation data, no response editing
  - **Auditor:** Time-bound read-only access to notices, trails, reports
  - **CA/Consultant:** Full permissions within assigned client scope
  - **Staff:** Create notices, draft responses, escalate (no approve/submit)
  - **CFO:** Read-only across all clients, all reports/analytics, escalation endpoint for critical notices
- **D-26:** Flat permissions per role — no inheritance hierarchy. Each role has an explicit permission set. Easier to audit.
- **D-27:** Auditor time-bound access via `access_start`/`access_end` on ClientMembership. Middleware auto-checks dates. Expired = auto-revoked.
- **D-28:** Permission enforcement via FastAPI `Depends()` functions: `require_compliance_role(['compliance_head', 'legal'])`. Consistent with existing `require_admin` pattern.

### Compliance Dashboard & Notice UX
- **D-29:** Dashboard: stats cards on top (total, overdue, by authority, by risk) + filterable notice table below. Consistent with v1.0 admin dashboard pattern.
- **D-30:** Sidebar filter panel — collapsible, with dropdowns for authority, type, status, risk level, date range, GSTIN/PAN.
- **D-31:** Notice detail page: two-column layout. Left: metadata, status workflow buttons, linked notices. Right: activity timeline, attachments.
- **D-32:** Bulk actions: checkbox selection on table rows → floating action bar with "Update Status", "Assign", "Export". Gmail/Jira pattern.

### Audit Trail
- **D-33:** Immutable audit log with database-level enforcement — PostgreSQL triggers + REVOKE DELETE/UPDATE on audit table. Application cannot alter audit records.

### Claude's Discretion
All technical implementation details (database schema specifics, API route structure, component composition, state management patterns) are at Claude's discretion within the constraints above.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — LIFE-01 through LIFE-08 (Notice Lifecycle), AUDIT-01/02 (Audit Trail), RBAC-01 through RBAC-06 (Extended RBAC), CLIENT-01 through CLIENT-07 (Client Management), INFRA-05/06/07
- `.planning/milestones/v1.0-ROADMAP.md` — v1.0 architecture decisions and phase summaries

### Existing Codebase
- `backend/app/models/user.py` — Existing User model with role field (admin/editor/viewer)
- `backend/app/models/document.py` — Existing Document model (user-scoped, status enum)
- `backend/app/models/audit_log.py` — Existing audit log model (needs hardening to immutable)
- `backend/app/utils/security.py` — Existing auth utilities (require_admin, hash_password, JWT)
- `backend/app/routers/admin.py` — Existing admin RBAC pattern to follow
- `backend/app/database.py` — Existing database setup (SQLAlchemy, session factory)
- `frontend/src/app/dashboard/layout.tsx` — Existing dashboard layout with role-based nav
- `frontend/src/lib/api.ts` — Existing API client with token refresh

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — Layered architecture overview
- `.planning/codebase/CONVENTIONS.md` — Coding conventions to follow
- `.planning/codebase/STACK.md` — Technology stack reference

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/models/audit_log.py` — Existing audit log model, needs hardening with DB triggers for immutability
- `backend/app/utils/security.py` — `require_admin` dependency pattern to extend for compliance roles
- `backend/app/routers/admin.py` — Admin RBAC + user management pattern to follow
- `frontend/src/app/dashboard/admin/page.tsx` — Tab-based admin UI with table, search, pagination, stat cards
- `frontend/src/components/StatusBadge.tsx` — Reusable badge component for notice status display
- `frontend/src/components/CategoryBadge.tsx` — Reusable badge for authority/type display
- Existing Celery + Redis setup for async report generation

### Established Patterns
- FastAPI routers with `Depends()` for auth/role guards
- SQLAlchemy models with Alembic migrations
- Pydantic schemas for request/response validation
- Axios API client with token refresh interceptor
- React context for auth state (`AuthContext.tsx`)
- Dark theme UI with zinc/neutral tokens throughout

### Integration Points
- Dashboard layout (`layout.tsx`) — add compliance nav items, role-gated
- Client switcher in dashboard header — new component
- New `/dashboard/compliance/*` route tree for all compliance pages
- New `/api/compliance/*` API route prefix for backend
- Existing `/api/auth/*` and user model extended with client membership

</code_context>

<specifics>
## Specific Ideas

- CFO role added per user request — sits atop escalation chain, read-only across all clients
- Indian regulatory authorities are fixed (GST, IT, MCA, RBI, SEBI) — enum, not user-configurable
- Multi-GSTIN per client is a hard requirement (one per state registration)
- "All Clients" cross-client view is critical for CAs managing 20-100+ clients

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-compliance-foundation*
*Context gathered: 2026-03-31*
