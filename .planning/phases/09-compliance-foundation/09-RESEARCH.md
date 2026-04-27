# Phase 9: Compliance Foundation - Research

**Researched:** 2026-04-27
**Domain:** Multi-tenant compliance management on existing FastAPI + Next.js + PostgreSQL system
**Confidence:** HIGH overall (every critical pattern has verified primary-source backing; only Indian regex micro-patterns sit at MEDIUM)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Notice Data Model**
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
- **D-11:** Simple tags via `notice_tags` junction table.
- **D-12:** Legal section references stored as JSON array.

**Client & Multi-Entity Architecture**
- **D-13:** PostgreSQL RLS via `set_config('app.current_client_id')` in middleware. RLS policies on all client-scoped tables. Zero cross-client leakage guarantee (CLIENT-04).
- **D-14:** Many-to-many Client-User via `ClientMembership(user_id, client_id, compliance_role)`. CAs manage multiple clients with potentially different roles per client.
- **D-15:** Separate `ClientRegistration` table: `client_id`, `type` (GSTIN/PAN/CIN/DIN), `value`, `state` (for GSTIN), `is_active`. Multi-GSTIN per client. Notices link to `registration_id`.
- **D-16:** Multi-step client onboarding wizard: Details → Registrations → Team Assignment → Import.
- **D-17:** Per-client config overrides via `config_overrides` JSONB column on Client model.
- **D-18:** Real-time query aggregation for per-client dashboard. No pre-computed stats table.
- **D-19:** On-demand report generation (user clicks → Celery computes → returns PDF/HTML). No scheduled monthly jobs yet.
- **D-20:** No client branding/logo in Phase 9.
- **D-21:** v1.0 documents remain user-scoped. Only compliance notices are client-scoped. No migration of existing documents.
- **D-22:** Top-bar client switcher dropdown in dashboard header. Workspace-style UX (Slack/Notion pattern).
- **D-23:** "All Clients" view available in switcher for CA/Compliance Head roles. Cross-client dashboard with client column in tables.

**Extended RBAC (7 Compliance Roles)**
- **D-24:** Parallel role systems — v1.0 system roles (admin/editor/viewer) govern document management. Compliance roles govern compliance features. Users have BOTH.
- **D-25:** 7 compliance roles: Compliance Head, Legal Team, Finance Team, Auditor, CA/Consultant, Staff, CFO.
- **D-26:** Flat permissions per role — no inheritance hierarchy.
- **D-27:** Auditor time-bound access via `access_start`/`access_end` on ClientMembership. Middleware auto-checks dates. Expired = auto-revoked.
- **D-28:** Permission enforcement via FastAPI `Depends()` functions: `require_compliance_role(['compliance_head', 'legal'])`.

**Compliance Dashboard & Notice UX**
- **D-29:** Dashboard: stats cards on top + filterable notice table below.
- **D-30:** Sidebar filter panel — collapsible, with dropdowns for authority, type, status, risk level, date range, GSTIN/PAN.
- **D-31:** Notice detail page: two-column layout. Left: metadata, status workflow buttons, linked notices. Right: activity timeline, attachments.
- **D-32:** Bulk actions: checkbox selection on table rows → floating action bar with "Update Status", "Assign", "Export". Gmail/Jira pattern.

**Audit Trail**
- **D-33:** Immutable audit log with database-level enforcement — PostgreSQL triggers + REVOKE DELETE/UPDATE on audit table.

### Claude's Discretion

All technical implementation details (database schema specifics, API route structure, component composition, state management patterns) are at Claude's discretion within the constraints above.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. (Note: AI/ML classification, automated retrieval, alert system are explicitly Phases 10-14, not deferred — they have explicit phase assignments.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LIFE-01 | Upload compliance notice (PDF, JPG, PNG) drag-and-drop | Reuse v1.0 upload pipeline (storage_service, react-dropzone). New `notice_id` FK on Document model. |
| LIFE-02 | OCR extraction reuses existing pipeline | Existing OCR pipeline at `backend/app/ml/ocr.py` — no change needed; `notice_id` linkage on Document populates extracted_text. |
| LIFE-03 | Manual metadata entry | Pydantic schemas + Indian regex validators (Don't-Hand-Roll: GSTIN/PAN); CONTEXT D-06 explicitly defers AI extraction to Phase 10. |
| LIFE-04 | Status workflow transitions | `transitions==0.9.3` library or hand-rolled dict per CONTEXT D-03. Audit log on every transition. DB CHECK constraint as belt-and-suspenders. |
| LIFE-05 | Notice chaining | `parent_notice_id` self-FK + PostgreSQL recursive CTE with CYCLE clause (PG 14+). |
| LIFE-06 | Notice detail with activity timeline | Two-column layout (D-31). NoticeActivity (D-09) drives timeline rendering. |
| LIFE-07 | Filter/search by authority/type/status/risk/deadline/GSTIN/PAN | PostgreSQL indexes on filter columns + ILIKE for free-text. No Elasticsearch in Phase 9 (deferred to Phase 13). |
| LIFE-08 | Bulk-update notice status | Floating action bar pattern (D-32). Optimistic React updates + per-row partial-failure handling. |
| AUDIT-01 | Immutable audit log via DB triggers + REVOKE | PostgreSQL `RAISE EXCEPTION` trigger on UPDATE/DELETE. `REVOKE UPDATE, DELETE ON audit_logs FROM app_role`. Existing `audit_logs` table from migration 0010 needs hardening. |
| AUDIT-02 | Capture who, what, when, before/after | Extend existing `audit_logs.details` JSONB with `before_value`/`after_value`. Switch `created_at` default to `clock_timestamp()`. |
| RBAC-01..06 | 6 base compliance roles | Permission registry (Python dict per role). FastAPI `require_compliance_role(roles=[...])` Depends factory. |
| RBAC (CFO) | CFO role per CONTEXT D-25 | Read-only across all clients (uses RLS bypass via "All Clients" view per D-23). |
| CLIENT-01 | Create/manage client entities with GSTIN/PAN/CIN | `Client` model + `ClientRegistration` (D-15). Indian regex validators. |
| CLIENT-02 | Multi-GSTIN per client | One-to-many ClientRegistration with `(client_id, type, value)` unique constraint. |
| CLIENT-03 | Client-scoped aggregate dashboard | Real-time SQL aggregation per D-18. Indexed COUNT/GROUP BY queries; cache only if profiled hot. |
| CLIENT-04 | RLS zero cross-client leakage | `ALTER TABLE ... FORCE ROW LEVEL SECURITY`; non-table-owner DB role; `set_config('app.current_client_id')` middleware; mandatory isolation integration test. |
| CLIENT-05 | Onboarding workflow | Multi-step wizard (D-16) with React Hook Form + Zustand persistence. |
| CLIENT-06 | Per-client config overrides | JSONB `config_overrides` (D-17) with GIN index using `jsonb_path_ops` for `@>` containment queries. |
| CLIENT-07 | Monthly compliance health summary report (Phase 9 stub) | On-demand Celery report (D-19). Phase 9 ships PDF generation; scheduled monthly delivery is in Phase 11/13. |
| INFRA-05 | RegulatoryCalendar table with Indian holiday data | Schema + seed-data migration. CBDT/CBIC/state holiday CSV imported via Alembic. |
| INFRA-06 | Field-level PII encryption (Fernet) | `cryptography==46.0.7` library. Encrypted `BYTEA` columns with `_enc` suffix for GSTIN/PAN/penalty. |
| INFRA-07 | DB-level audit immutability | Same implementation as AUDIT-01 (single migration). |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

No project-level `./CLAUDE.md` exists. User-level memory provides two relevant directives:

| Source | Directive |
|--------|-----------|
| Memory `feedback_docker_only.md` | Always run Smart-Docs via `docker-compose`, not manual processes. Plans must use Docker for all integration testing and migrations. |
| Memory `feedback_update_docs_after_sessions.md` | Update README, docs, reports after every session. Phase 9 must include a docs-update task when complete. |

Existing project conventions to honor (from `.planning/codebase/CONVENTIONS.md`):
- Python: SQLAlchemy 2.0 declarative_base; Pydantic schemas; FastAPI Depends() for auth; Alembic migrations.
- Frontend: Next.js 15.5 App Router (note: codebase uses Next 15, not 14 as STACK.md states); React 19; Tailwind; "use client" for interactive; path alias `@/*`.
- Logging: structlog (already in use; see `backend/app/services/audit_service.py`).
- Testing: pytest 9.0 already installed; existing `backend/tests/conftest.py` with mock_settings fixture.

## Summary

Phase 9 builds the entire compliance vertical's data spine: 8 new SQLAlchemy models (Client, ClientRegistration, ClientMembership, ComplianceNotice, NoticeType, NoticeActivity, NoticeTag, plus the immutable hardening of `audit_logs`), a 7-role permission matrix layered alongside the existing v1.0 admin/editor/viewer system, and PostgreSQL RLS as the zero-leakage tenancy boundary. **Every architectural pattern is well-documented and has an established implementation recipe** — the work is execution discipline, not invention.

The three highest-risk areas all have explicit, testable mitigations: (1) RLS leakage requires `FORCE ROW LEVEL SECURITY` + non-owner DB role + a mandatory cross-client integration test that fails-closed; (2) audit immutability is achieved via `REVOKE UPDATE, DELETE` + a `RAISE EXCEPTION` trigger that the application cannot bypass; (3) RBAC time-bound Auditor access is enforced in middleware (not route layer) so it cannot be sidestepped by adding new endpoints. The compliance role check, RLS context-set, and Auditor expiry check are three middleware layers that compose orthogonally.

The CONTEXT decisions match canonical patterns. PostgreSQL session config (`set_config`) for RLS tenant context is the documented Atlas/Supabase/Bytebase pattern. `transitions` 0.9.3 is the right library for Python state machines but a hand-rolled dict is a defensible alternative for 5 states with simple guards (CONTEXT D-03 explicitly allows the dict approach). JSONB `config_overrides` with `jsonb_path_ops` GIN index is the canonical containment-query pattern.

**Primary recommendation:** Build in this order — (1) DB schema migrations + RLS + audit immutability triggers; (2) backend models, services, and RBAC middleware; (3) FastAPI routers; (4) frontend client switcher + onboarding wizard + notice list/detail; (5) bulk actions + activity timeline. Wave-0 must establish the RLS isolation test and audit immutability test before any business logic is built — these tests prove the security primitives are working before features depend on them.

## Standard Stack

### Core (Backend — already in v1.0, version-verified)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.104.1 (already pinned; latest 0.136.1) | REST API framework | Existing — no upgrade needed for Phase 9. |
| SQLAlchemy | 2.0.23 (already pinned; latest 2.0.49) | ORM | Existing. 2.0 declarative + `Mapped[...]` typing supports our model patterns. |
| Alembic | 1.18.4 (latest) | Migrations | Existing. Phase 9 migrations are large; review-pace alembic chains carefully. |
| psycopg2-binary | 2.9.9 | Postgres adapter | Existing. Required for `set_config()` and trigger DDL execution. |
| Pydantic | (paired with FastAPI 0.104) | Schemas | Existing. Use `pydantic.BaseModel` v2 patterns. |
| python-multipart | 0.0.22 | File uploads | Existing. |

### Core (Backend — new for Phase 9)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cryptography` | 46.0.7 (registry-verified; project pin 41.0.7 is stale) | Fernet PII encryption | INFRA-06 mandate. Fernet is symmetric AES-128-CBC + HMAC, the canonical choice for field-level encryption with rotatable keys. |
| `transitions` | 0.9.3 (registry-verified) | Optional state machine library | Provides `Machine`, callbacks, and conditional guards. CONTEXT D-03 also allows hand-rolled dict (recommended for our 5-state workflow — see Architecture Patterns). |

### Core (Frontend — new for Phase 9)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `zustand` | 5.0.12 (registry-verified) | UI state for client switcher + multi-step wizard | Lightweight (~1KB), persist middleware for wizard step recovery, no Provider boilerplate. Project research SUMMARY recommended this. |
| `@tanstack/react-query` | 5.100.5 (registry-verified) | Server state for notice lists + mutations | Optimistic updates for bulk actions, automatic refetch on tenant switch, request deduplication. |
| `@tanstack/react-table` | 8.21.3 (registry-verified) | Notice table | Headless table with built-in row selection state for bulk actions, faceted filters, virtualization-ready for 1000+ rows. |
| `react-hook-form` | 7.x (latest stable) | Multi-step onboarding wizard form state | Pairs cleanly with Zod for schema validation. **Note compatibility caveat:** `watch()` has known issues with React 19 — use `getValues()` or `useWatch` for the wizard. |
| `zod` | 3.x (latest stable) | Schema validation | Mirror Pydantic schemas server-side; validate per wizard step before advancing. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `alembic_utils` | latest | PG triggers/policies/functions in Alembic with autogenerate | If team wants autogenerated trigger diffs. Otherwise use `op.execute()` raw SQL — simpler for our scope. |
| `structlog` | already in v1.0 | Structured logging with field redaction | Required for INFRA-06 — must add a redaction filter that strips PII fields (gstin, pan, penalty) from log records. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled dict state machine | `transitions==0.9.3` library | Library adds callback wiring + diagrams; dict is 30 LOC, transparent, and easier to test. **Recommend dict** for our 5 states. CONTEXT D-03 explicitly allows it. |
| Custom RBAC `Depends()` factory | `casbin==1.43.0` (PyCasbin) | Casbin is policy-language driven (Casbin model files + adapter); overkill for 7 fixed roles with flat permissions. **Recommend custom factory** matching the v1.0 `require_admin` pattern. CONTEXT D-26 mandates flat permissions, which kills Casbin's main value-add. |
| react-hook-form + Zustand for wizard | URL-state-only wizard | URL-state survives refresh but cannot persist partial form data; wizard has 4 steps with side-effects (registrations array, team assignments). **Recommend RHF + Zustand** with localStorage persist. |
| Self-rolled sessionvar middleware | SQLAlchemy event listener (`do_orm_execute` or connection-pool checkout) | Both work. **Recommend middleware approach** (FastAPI middleware sets session var on connection retrieved from `Depends(get_db)`) — clearer request boundaries, simpler to reason about, easier to test. |

**Installation (backend):**
```bash
# Already in requirements.txt — UPGRADE pin only
# cryptography>=46.0.0  (currently 41.0.7)

# New
pip install transitions==0.9.3   # optional; only if rejecting hand-rolled dict
```

**Installation (frontend):**
```bash
npm install zustand@5 @tanstack/react-query@5 @tanstack/react-table@8 react-hook-form@7 zod@3
```

**Version verification (performed 2026-04-27 against npm/PyPI):**
- `zustand@5.0.12` — verified via `npm view zustand version`
- `@tanstack/react-query@5.100.5` — verified
- `@tanstack/react-table@8.21.3` — verified
- `transitions==0.9.3` — verified via `pip3 index versions transitions`
- `cryptography==46.0.7` — verified (latest 47.0.0 ships Nov 2025; 46.0.7 is stable LTS)
- Existing: `alembic==1.18.4` (latest), `sqlalchemy==2.0.48` (latest 2.0.49)

## Architecture Patterns

### Recommended Project Structure (additive — does NOT touch v1.0)

```
backend/app/
├── compliance/                          # NEW — self-contained vertical
│   ├── __init__.py
│   ├── models/
│   │   ├── client.py                    # Client + ClientRegistration
│   │   ├── membership.py                # ClientMembership (with access_start/end)
│   │   ├── notice.py                    # ComplianceNotice + NoticeActivity + NoticeTag
│   │   └── notice_type.py               # NoticeType lookup
│   ├── schemas/
│   │   ├── client.py
│   │   ├── notice.py
│   │   └── activity.py
│   ├── services/
│   │   ├── client_service.py
│   │   ├── notice_service.py
│   │   ├── notice_state_machine.py      # The dict-based FSM
│   │   ├── activity_service.py
│   │   └── permission_registry.py       # 7-role → permission set mapping
│   ├── routers/
│   │   ├── clients.py                   # /api/compliance/clients/*
│   │   ├── notices.py                   # /api/compliance/notices/*
│   │   ├── memberships.py               # /api/compliance/memberships/*
│   │   └── reports.py                   # /api/compliance/reports/*
│   ├── middleware/
│   │   ├── tenant_context.py            # set_config('app.current_client_id', ...)
│   │   └── auditor_expiry.py            # rejects expired Auditor memberships
│   └── utils/
│       ├── indian_validators.py         # GSTIN/PAN/CIN/DIN regex
│       ├── pii_encryption.py            # Fernet wrapper
│       └── log_redaction.py             # structlog field filter
├── models/                              # EXISTING — only audit_log.py is hardened
│   └── audit_log.py                     # add immutability (no schema change)
├── routers/                             # EXISTING — unchanged
└── utils/security.py                    # ADD require_compliance_role() factory

backend/alembic/versions/
├── 0013_compliance_foundation_schema.py # All new tables in one migration
├── 0014_audit_log_immutability.py       # REVOKE + trigger on existing audit_logs
├── 0015_compliance_rls_policies.py      # FORCE RLS + policies on client-scoped tables
└── 0016_regulatory_calendar_seed.py     # INFRA-05 holiday seed data

frontend/src/
├── app/dashboard/compliance/            # NEW route tree
│   ├── layout.tsx                       # Adds client switcher to header
│   ├── page.tsx                         # /dashboard/compliance — notice dashboard
│   ├── notices/[id]/page.tsx            # Detail (two-column)
│   ├── clients/                         # /dashboard/compliance/clients
│   │   ├── page.tsx                     # List
│   │   ├── [id]/page.tsx                # Per-client view
│   │   └── new/page.tsx                 # Onboarding wizard (4 steps)
│   └── reports/page.tsx                 # On-demand reports
├── components/compliance/               # NEW
│   ├── ClientSwitcher.tsx               # Top-bar dropdown
│   ├── NoticeTable.tsx                  # @tanstack/react-table
│   ├── BulkActionBar.tsx                # Floating action bar
│   ├── NoticeStatusButton.tsx           # State machine UI button
│   ├── ActivityTimeline.tsx
│   └── OnboardingWizard/                # Multi-step
│       ├── StepDetails.tsx
│       ├── StepRegistrations.tsx
│       ├── StepTeam.tsx
│       └── StepImport.tsx
├── stores/                              # NEW (Zustand)
│   ├── currentClientStore.ts            # active client + "all clients" mode
│   └── onboardingWizardStore.ts         # persist multi-step form state
└── lib/api/compliance.ts                # API client extensions
```

### Pattern 1: PostgreSQL RLS with `set_config` middleware

**What:** Each request sets a session-local PostgreSQL config var (`app.current_client_id`); RLS policies on client-scoped tables filter `WHERE client_id = current_setting('app.current_client_id')::int`. Zero application-layer filter required.

**When to use:** All client-scoped tables (Client, ClientRegistration, ComplianceNotice, NoticeActivity, NoticeTag, ClientMembership). Existing v1.0 tables (User, Document, audit_logs at first) are NOT under RLS — CONTEXT D-21 mandates v1.0 documents stay user-scoped.

**Implementation recipe (verified across postgresql.org docs, AWS, Atlas, Bytebase, Supabase):**

```python
# Source: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
#         https://atlasgo.io/guides/orms/sqlalchemy/row-level-security

# 1) Migration creates two DB roles
op.execute("""
    -- Migration role: owner, BYPASSRLS implicit (owners bypass by default)
    CREATE ROLE app_migrator WITH LOGIN PASSWORD :pwd CREATEDB;
    -- App role: NOT the table owner, NOT BYPASSRLS — subject to RLS
    CREATE ROLE app_runtime WITH LOGIN PASSWORD :pwd;
    GRANT CONNECT ON DATABASE smartdocs TO app_runtime;
""")

# 2) Per-table: enable AND force RLS (otherwise owner test escape)
op.execute("""
    ALTER TABLE compliance_notices ENABLE ROW LEVEL SECURITY;
    ALTER TABLE compliance_notices FORCE ROW LEVEL SECURITY;
    GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_notices TO app_runtime;
""")

# 3) Policy uses session var
op.execute("""
    CREATE POLICY tenant_isolation_select ON compliance_notices
      FOR SELECT TO app_runtime
      USING (client_id = current_setting('app.current_client_id', true)::int);
    CREATE POLICY tenant_isolation_modify ON compliance_notices
      FOR ALL TO app_runtime
      USING (client_id = current_setting('app.current_client_id', true)::int)
      WITH CHECK (client_id = current_setting('app.current_client_id', true)::int);
""")

# 4) FastAPI middleware sets the var per request
# Source pattern: https://dobken.nl/posts/rls-postgres/

@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    user = await get_user_from_request(request)
    client_id = resolve_active_client(user, request)  # from header, JWT claim, or session
    if client_id is None:
        return await call_next(request)  # public/auth endpoints

    # The DB session retrieved by Depends(get_db) inherits the connection
    # which we set the var on. Use a connection-checkout event:
    @sa_event.listens_for(engine, "checkout")
    def _set_tenant(dbapi_connection, *_):
        with dbapi_connection.cursor() as cur:
            cur.execute("SELECT set_config('app.current_client_id', %s, true)",
                        (str(client_id),))
    return await call_next(request)
```

**Critical footguns (all avoided by the recipe above):**

1. **Table owner bypass** — by default, table owners ignore RLS. Without `FORCE ROW LEVEL SECURITY`, integration tests run as the owner pass while production with `app_runtime` would also pass — but reverse the role and you discover policies were never enforced. Always `FORCE`.
2. **Superuser bypass** — only `BYPASSRLS` and superuser roles bypass RLS. Migration role (`app_migrator`) does this intentionally; runtime (`app_runtime`) does not.
3. **`current_setting('...', true)` vs `current_setting('...')`** — the second arg `true` returns NULL on missing config instead of raising. Without it, any auth-skipping endpoint that touches a client-scoped table errors.
4. **Sessionvar via Depends() vs middleware** — middleware runs once per request; Depends(get_db) yields a session whose connection MUST inherit the var. The pool checkout event listener guarantees this.
5. **CSRF / cross-tenant leakage in Celery** — Celery workers do NOT inherit middleware. Pass `client_id` as task kwarg; task must call `set_config()` itself before any query.

### Pattern 2: Audit log immutability (DB-level enforcement)

**What:** PostgreSQL trigger raises exception on UPDATE/DELETE attempts; `REVOKE UPDATE, DELETE` removes the privilege at SQL grant level (defense in depth). The existing `audit_logs` table from migration `0010` is hardened in-place — no schema change, no data loss.

**When to use:** AUDIT-01, INFRA-07. Enforce on `audit_logs` only — NOT on `notice_activity` (that table is user-modifiable: notes can be edited, activity timeline entries deleted by Compliance Head).

**Implementation recipe (verified across postgresql.org wiki, Vlad Mihalcea, EnterpriseDB, OneUptime):**

```sql
-- Migration 0014_audit_log_immutability.py op.execute()

-- 1) Trigger function: raise on UPDATE or DELETE
CREATE OR REPLACE FUNCTION reject_audit_log_modification()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only — % is forbidden', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

-- 2) Bind to BEFORE UPDATE OR DELETE
CREATE TRIGGER audit_logs_immutability
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION reject_audit_log_modification();

-- 3) REVOKE at SQL privilege level — must run AS SUPERUSER or owner
REVOKE UPDATE, DELETE ON audit_logs FROM app_runtime;
REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC;

-- 4) Add the missing immutability primitives
--    a) Use clock_timestamp() (wall clock) not now() (transaction start)
ALTER TABLE audit_logs
    ALTER COLUMN created_at SET DEFAULT clock_timestamp();
--    b) Generated identity prevents manual ID insertion
--    (skipped: existing data uses serial; migration risk too high to switch.
--     Document: integer auto-increment IDs are application-set-safe because
--     the trigger blocks UPDATE.)
```

**What this DOES enforce:**
- Application code cannot UPDATE/DELETE — both REVOKE and trigger fire.
- Even if a developer mis-grants UPDATE, the trigger still raises.
- An attacker with `app_runtime` credentials cannot tamper without superuser access.

**What this does NOT enforce (be honest with the planner):**
- Superuser (`postgres`) can drop the trigger and modify rows. Mitigation: superuser credentials live only in operator vault; `app_runtime` is what the FastAPI process uses.
- Migration role (`app_migrator`) can drop the trigger during a migration. Mitigation: code review and CI blocks any migration touching `audit_logs` schema.
- Hash chaining (PITFALLS.md) is NOT in this phase. Document as Phase 13 work — a `hash` column added later does not invalidate existing rows.

### Pattern 3: Notice status state machine (hand-rolled dict)

**What:** A 5-state workflow with a dict mapping `(current_state) → set(valid_next_states)`. Every transition writes both an `audit_logs` row AND a `notice_activity` row.

**When to use:** LIFE-04. Decided over `transitions` library because (a) only 5 states; (b) callbacks are not state-side but at the service layer (`NoticeService.transition()`); (c) testing a dict is trivial; (d) the library introduces an inheritance pattern that complicates SQLAlchemy mixin composition.

**Implementation recipe:**

```python
# backend/app/compliance/services/notice_state_machine.py

from enum import Enum

class NoticeStatus(str, Enum):
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    RESPONSE_DRAFTED = "response_drafted"
    SUBMITTED = "submitted"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"

# CONTEXT D-03: Received → Under Review → Response Drafted → Submitted → Resolved/Dismissed
ALLOWED_TRANSITIONS: dict[NoticeStatus, frozenset[NoticeStatus]] = {
    NoticeStatus.RECEIVED:        frozenset({NoticeStatus.UNDER_REVIEW, NoticeStatus.DISMISSED}),
    NoticeStatus.UNDER_REVIEW:    frozenset({NoticeStatus.RESPONSE_DRAFTED, NoticeStatus.DISMISSED}),
    NoticeStatus.RESPONSE_DRAFTED: frozenset({NoticeStatus.SUBMITTED, NoticeStatus.UNDER_REVIEW}),  # back-edit
    NoticeStatus.SUBMITTED:       frozenset({NoticeStatus.RESOLVED, NoticeStatus.UNDER_REVIEW}),
    NoticeStatus.RESOLVED:        frozenset(),  # terminal
    NoticeStatus.DISMISSED:       frozenset(),  # terminal
}

class InvalidTransitionError(Exception):
    pass

def validate_transition(current: NoticeStatus, target: NoticeStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Allowed: {sorted(s.value for s in ALLOWED_TRANSITIONS[current])}"
        )
```

**Belt-and-suspenders enforcement (DB CHECK constraint):**

PostgreSQL cannot easily express graph constraints without triggers. The recommended pattern is a row-level trigger that calls `validate_transition()` in PL/pgSQL. **Skip this for Phase 9** — the application-layer dict + audit log is sufficient; a DB trigger duplicates logic and complicates migrations. Add a regression test that asserts every `audit_logs.action='notice_status_changed'` entry has a `before_value`/`after_value` pair allowed by `ALLOWED_TRANSITIONS`.

### Pattern 4: 7-role compliance permission registry + FastAPI Depends()

**What:** Flat permission strings keyed per role. A factory `require_compliance_role([...])` extends the existing `require_admin` pattern from `backend/app/utils/security.py`.

**Implementation recipe:**

```python
# backend/app/compliance/services/permission_registry.py

from enum import Enum

class CompliancePermission(str, Enum):
    NOTICE_VIEW          = "notice:view"
    NOTICE_CREATE        = "notice:create"
    NOTICE_DRAFT_RESPONSE = "notice:draft_response"
    NOTICE_APPROVE       = "notice:approve"
    NOTICE_SUBMIT        = "notice:submit"
    NOTICE_BULK_UPDATE   = "notice:bulk_update"
    CLIENT_CREATE        = "client:create"
    CLIENT_MANAGE_TEAM   = "client:manage_team"
    REPORT_VIEW          = "report:view"
    REPORT_EXPORT        = "report:export"
    AUDIT_VIEW           = "audit:view"
    ESCALATION_TRIGGER   = "escalation:trigger"

class ComplianceRole(str, Enum):
    COMPLIANCE_HEAD = "compliance_head"
    LEGAL_TEAM      = "legal_team"
    FINANCE_TEAM    = "finance_team"
    AUDITOR         = "auditor"
    CA_CONSULTANT   = "ca_consultant"
    STAFF           = "staff"
    CFO             = "cfo"

# CONTEXT D-26: flat permissions, no inheritance
ROLE_PERMISSIONS: dict[ComplianceRole, frozenset[CompliancePermission]] = {
    ComplianceRole.COMPLIANCE_HEAD: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_CREATE,
        CompliancePermission.NOTICE_APPROVE,
        CompliancePermission.NOTICE_SUBMIT,
        CompliancePermission.NOTICE_BULK_UPDATE,
        CompliancePermission.CLIENT_MANAGE_TEAM,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
        CompliancePermission.ESCALATION_TRIGGER,
    }),
    ComplianceRole.LEGAL_TEAM: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_DRAFT_RESPONSE,
        CompliancePermission.REPORT_VIEW,
    }),
    ComplianceRole.FINANCE_TEAM: frozenset({
        CompliancePermission.NOTICE_VIEW,  # scoped to GST/IT only — enforced in service layer
        CompliancePermission.REPORT_VIEW,
    }),
    ComplianceRole.AUDITOR: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.AUDIT_VIEW,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
    }),
    ComplianceRole.CA_CONSULTANT: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_CREATE,
        CompliancePermission.NOTICE_DRAFT_RESPONSE,
        CompliancePermission.NOTICE_APPROVE,
        CompliancePermission.NOTICE_SUBMIT,
        CompliancePermission.NOTICE_BULK_UPDATE,
        CompliancePermission.CLIENT_CREATE,
        CompliancePermission.CLIENT_MANAGE_TEAM,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
    }),
    ComplianceRole.STAFF: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_CREATE,
        CompliancePermission.NOTICE_DRAFT_RESPONSE,
        CompliancePermission.ESCALATION_TRIGGER,
    }),
    ComplianceRole.CFO: frozenset({
        CompliancePermission.NOTICE_VIEW,    # read-only across all clients
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
        CompliancePermission.ESCALATION_TRIGGER,
    }),
}

def has_permission(role: ComplianceRole, perm: CompliancePermission) -> bool:
    return perm in ROLE_PERMISSIONS[role]

# backend/app/utils/security.py — extend existing patterns

def require_compliance_permission(perm: CompliancePermission):
    """FastAPI Depends factory — checks user has perm via active membership."""
    def _check(
        current_user: User = Depends(get_current_user),
        active_client_id: int = Depends(get_active_client_id),  # from header / JWT
        db: Session = Depends(get_db),
    ) -> User:
        membership = db.query(ClientMembership).filter(
            ClientMembership.user_id == current_user.id,
            ClientMembership.client_id == active_client_id,
        ).first()
        if not membership:
            raise HTTPException(403, "No membership for active client")

        # D-27: Auditor time-bound check — middleware also checks but defense in depth
        now = datetime.now(timezone.utc)
        if membership.access_end and now > membership.access_end:
            raise HTTPException(403, "Membership access has expired")
        if membership.access_start and now < membership.access_start:
            raise HTTPException(403, "Membership access has not started")

        if not has_permission(membership.compliance_role, perm):
            raise HTTPException(403, f"Role {membership.compliance_role} lacks {perm.value}")
        return current_user
    return _check

# Usage in router
@router.post("/notices", dependencies=[
    Depends(require_compliance_permission(CompliancePermission.NOTICE_CREATE)),
])
def create_notice(...):
    ...
```

**Why permissions instead of role-name checks:** The existing pattern `require_admin(role == 'admin')` becomes brittle once you have 7 roles × 12 permissions. Permission strings let routes declare intent (`require_compliance_permission(NOTICE_APPROVE)`) without coupling to role names. CONTEXT D-26 (flat permissions) is preserved.

### Pattern 5: Recursive CTE for notice chain (parent_notice_id)

**What:** PostgreSQL recursive CTE with `CYCLE` clause (PostgreSQL 14+, supported by Phase 9 stack since psycopg2-binary 2.9.9 + PG 14+).

**When to use:** LIFE-05 — fetch full chain (SCN → Assessment → Demand → Appeal) for the detail page's "Linked notices" panel.

**Implementation recipe (verified against postgresql.org docs):**

```python
# backend/app/compliance/services/notice_service.py

from sqlalchemy import text

def get_notice_chain(db: Session, notice_id: int, max_depth: int = 10) -> list[dict]:
    """
    Returns ancestors + descendants for a notice. CYCLE clause (PG 14+)
    auto-detects loops; max_depth provides additional safety.
    """
    sql = text("""
        WITH RECURSIVE
        ancestors AS (
            SELECT id, parent_notice_id, notice_number, status, 0 AS depth
              FROM compliance_notices WHERE id = :nid
            UNION ALL
            SELECT n.id, n.parent_notice_id, n.notice_number, n.status, a.depth - 1
              FROM compliance_notices n
              JOIN ancestors a ON n.id = a.parent_notice_id
              WHERE a.depth > -:max_depth
        ),
        descendants AS (
            SELECT id, parent_notice_id, notice_number, status, 0 AS depth
              FROM compliance_notices WHERE id = :nid
            UNION ALL
            SELECT n.id, n.parent_notice_id, n.notice_number, n.status, d.depth + 1
              FROM compliance_notices n
              JOIN descendants d ON n.parent_notice_id = d.id
              WHERE d.depth < :max_depth
        )
        SELECT * FROM ancestors WHERE depth < 0
        UNION
        SELECT * FROM descendants
        ORDER BY depth;
    """)
    result = db.execute(sql, {"nid": notice_id, "max_depth": max_depth})
    return [dict(r._mapping) for r in result]
```

**Cycle prevention:** The depth-limit `WHERE a.depth > -:max_depth` doubles as cycle protection (any cycle would loop until depth exceeds max). For belt-and-suspenders use the `CYCLE` clause if you want PG 14+ behavior:

```sql
WITH RECURSIVE chain AS (...) CYCLE id SET is_cycle USING path
```

**Don't:** Eager-load chain via SQLAlchemy relationship loading — N+1 catastrophe at depth 5.

### Pattern 6: Multi-step onboarding wizard (Zustand + RHF + Zod)

**What:** Four-step wizard (Details → Registrations → Team → Import) with `react-hook-form` per step, `zod` validation per step, Zustand persist middleware to localStorage so a refresh doesn't lose state.

**When to use:** CLIENT-05 — onboarding flow only. Don't apply this pattern to single-step forms.

**Implementation recipe:**

```typescript
// frontend/src/stores/onboardingWizardStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type WizardState = {
  step: 1 | 2 | 3 | 4;
  details: { name: string; type: string } | null;
  registrations: Array<{ type: 'GSTIN'|'PAN'|'CIN'|'DIN'; value: string; state?: string }>;
  team: Array<{ user_id: number; compliance_role: string }>;
  setStep: (s: 1 | 2 | 3 | 4) => void;
  setDetails: (d: WizardState['details']) => void;
  setRegistrations: (r: WizardState['registrations']) => void;
  setTeam: (t: WizardState['team']) => void;
  reset: () => void;
};

export const useOnboardingWizard = create<WizardState>()(
  persist(
    (set) => ({
      step: 1,
      details: null,
      registrations: [],
      team: [],
      setStep: (step) => set({ step }),
      setDetails: (details) => set({ details }),
      setRegistrations: (registrations) => set({ registrations }),
      setTeam: (team) => set({ team }),
      reset: () => set({ step: 1, details: null, registrations: [], team: [] }),
    }),
    { name: 'compliance-onboarding-wizard' }
  )
);
```

**Per-step component pattern:**

```typescript
// frontend/src/components/compliance/OnboardingWizard/StepRegistrations.tsx
"use client";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useOnboardingWizard } from "@/stores/onboardingWizardStore";

const GSTIN_RX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
const PAN_RX   = /^[A-Z]{5}[0-9]{4}[A-Z]$/;

const schema = z.object({
  registrations: z.array(z.object({
    type: z.enum(['GSTIN', 'PAN', 'CIN', 'DIN']),
    value: z.string(),
    state: z.string().optional(),
  })).superRefine((arr, ctx) => {
    arr.forEach((reg, i) => {
      if (reg.type === 'GSTIN' && !GSTIN_RX.test(reg.value))
        ctx.addIssue({ code: 'custom', path: [i, 'value'], message: 'Invalid GSTIN' });
      if (reg.type === 'PAN' && !PAN_RX.test(reg.value))
        ctx.addIssue({ code: 'custom', path: [i, 'value'], message: 'Invalid PAN' });
    });
  }),
});
// ... rest of component uses useFieldArray for dynamic registration list
```

**Critical compatibility note:** React Hook Form v7's `watch()` has known issues with React 19. **Use `getValues()` for static reads or `useWatch()` with a stable selector.** Confirmed via Markus Oberlehner's RHF + React 19 + Next 15 article (2025-2026).

### Pattern 7: Top-bar client switcher with "All Clients" view

**What:** Dropdown in dashboard header (positioned next to logo or in top-right). Shows current client name; clicking reveals search/list + "All Clients" option (visible only to CA/Compliance Head/CFO per D-23).

**When to use:** D-22, D-23. Replace dashboard `layout.tsx` header with a new compliance-aware header that mounts `<ClientSwitcher>`.

**Implementation pattern (Slack-inspired, adapted to single-app context):**

```typescript
// frontend/src/components/compliance/ClientSwitcher.tsx
"use client";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useCurrentClient } from "@/stores/currentClientStore";

export function ClientSwitcher() {
  const { activeClientId, setActiveClientId, mode, setMode } = useCurrentClient();
  const { data: memberships } = useQuery({
    queryKey: ['memberships', 'mine'],
    queryFn: () => api.get('/compliance/memberships/me').then(r => r.data),
  });

  // Restore from localStorage on mount, validate against current memberships
  useEffect(() => {
    if (activeClientId && !memberships?.some(m => m.client_id === activeClientId)) {
      setActiveClientId(null);  // Membership revoked while away
    }
  }, [memberships, activeClientId, setActiveClientId]);

  // Render dropdown with: search box, list of clients, divider, "All Clients" (if eligible)
  // Eligibility: any membership has compliance_role IN (compliance_head, ca_consultant, cfo)
  ...
}
```

**Session persistence:**
- Active client ID lives in Zustand with `persist` to localStorage.
- Backend MUST validate active client on EVERY request (middleware).
- Switching clients invalidates the React Query cache: `queryClient.invalidateQueries({ queryKey: ['notices'] })`.
- HTTP header convention: `X-Client-Id: 42` (or special value `*` for "All Clients" mode — only accepted if user has eligible role).

**"All Clients" mode (D-23):** When the active mode is `*`, the middleware sets `app.current_client_id` to a sentinel that matches no policy AND grants the request a separate role with `BYPASSRLS`. Alternative (simpler): set `current_client_id` to NULL and write RLS policies as `client_id = current_setting('app.current_client_id', true)::int OR (current_setting('app.cross_client_mode', true) = 'true' AND <role check>)`. **Recommend the second approach** — keeps a single `app_runtime` role.

### Pattern 8: Bulk action floating action bar with optimistic + partial-failure UX

**What:** `@tanstack/react-table` provides built-in row selection state. Selection > 0 mounts a floating `<BulkActionBar>` at the bottom of the viewport. Actions fire individual API calls with `Promise.allSettled` and show per-row success/failure.

**When to use:** D-32, LIFE-08.

**Implementation pattern (verified against shadcn/ui todo-list-bulk-actions block, eleken.co bulk-actions UX guidelines):**

```typescript
// Single-endpoint bulk update: POST /compliance/notices/bulk
// Returns: { results: [{ id, success, error? }], summary: { ok: 4, failed: 1 } }

async function bulkUpdateStatus(ids: number[], status: string) {
  // Optimistic: queryClient.setQueryData updates rows immediately
  const ctx = await queryClient.cancelQueries({ queryKey: ['notices'] });
  queryClient.setQueryData(['notices'], (old: Notice[]) =>
    old.map(n => ids.includes(n.id) ? { ...n, status, _pending: true } : n)
  );

  try {
    const { data } = await api.post('/compliance/notices/bulk', { ids, status });
    // On partial failure, revert pending rows that failed
    queryClient.setQueryData(['notices'], (old: Notice[]) =>
      old.map(n => {
        const result = data.results.find(r => r.id === n.id);
        if (result?.success) return { ...n, status, _pending: false };
        if (result?.error) return { ...n, _pending: false, _error: result.error };
        return n;
      })
    );
    if (data.summary.failed > 0) {
      toast.error(`${data.summary.failed} of ${ids.length} updates failed. See row indicators.`);
    } else {
      toast.success(`Updated ${data.summary.ok} notices.`);
    }
  } catch (err) {
    queryClient.setQueryData(['notices'], ctx);  // full rollback on network error
    toast.error('Bulk update failed.');
  }
}
```

**Key UX rules (eleken.co):**
- The bar slides up from bottom; doesn't cover content (offset by viewport - 80px).
- Stays persistent during scroll; expands when selection grows.
- Overflow actions go into a "More" menu after 3 visible buttons.
- Each row gets a `_pending` indicator (spinner) and `_error` indicator (red badge) when partial failures occur.
- Always tell the user what happened: "Updated 4 of 5 notices. 1 failed (see row indicator)."

### Pattern 9: JSONB config_overrides with GIN index (jsonb_path_ops)

**What:** `client.config_overrides` JSONB column with a `jsonb_path_ops` GIN index for fast `@>` containment queries. SQLAlchemy 2.0 uses `JSONB` from `sqlalchemy.dialects.postgresql`.

**When to use:** D-17 — per-client overrides for alert thresholds, approval workflows, deadline buffers.

**Implementation recipe:**

```python
# backend/app/compliance/models/client.py
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, Integer, Index

class Client(Base):
    __tablename__ = "compliance_clients"
    id = Column(Integer, primary_key=True)
    # ...
    config_overrides = Column(JSONB, nullable=False, server_default='{}')

    __table_args__ = (
        # jsonb_path_ops: smaller index, faster @>; trade off: only @> works (not ?, ?&, ?|)
        Index('ix_clients_config_overrides_gin', 'config_overrides',
              postgresql_using='gin',
              postgresql_ops={'config_overrides': 'jsonb_path_ops'}),
    )

# Query example: find clients with auto_escalate enabled for high-risk
db.query(Client).filter(
    Client.config_overrides.contains({"escalation": {"auto_high_risk": True}})
).all()
```

**Critical correctness note (verified against pganalyze and PostgreSQL docs):**
- `jsonb_ops` indexes support `@>`, `?`, `?&`, `?|`. Larger index, more flexible.
- `jsonb_path_ops` supports ONLY `@>`. Smaller, faster for the common case.
- **GIN does NOT accelerate `->>` extraction.** If you query `config_overrides->>'key' = 'value'`, the planner does a sequential scan. Use containment (`@>`) or add a B-tree expression index on the specific path.

**Schema validation (Pydantic):** Always validate `config_overrides` against a Pydantic model on write — JSONB will accept anything. Schema-on-write is essential.

### Anti-Patterns to Avoid

- **Filtering by `client_id` in application code AND relying on RLS** — pick one. Doing both means a forgotten filter feels safe (RLS will catch it) but masks bugs in tests where RLS is bypassed (table-owner runs).
- **Application-level audit log without DB-level enforcement** — application can be bypassed via direct DB access. CONTEXT D-33 explicitly mandates DB-level.
- **Role hierarchies (admin > manager > staff)** — CONTEXT D-26 forbids inheritance. Flat permissions per role.
- **Eager-loading notice chains via SQLAlchemy** — N+1 query at depth 5+. Use recursive CTE.
- **Sharing the v1.0 admin/editor/viewer role with compliance roles** — CONTEXT D-24 explicitly mandates parallel role systems. A user has both a `system_role` and a `compliance_role` (per ClientMembership).
- **JSONB `->>` operator with GIN index** — not accelerated. Use `@>` containment or expression B-tree index.
- **`set_config()` in service-layer functions** — must run at connection-checkout (or middleware), not per-query, otherwise some queries fire before the var is set.
- **Trust table-owner for RLS testing** — owners bypass RLS by default. Always run integration tests as `app_runtime` role.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-tenant data isolation | Custom `WHERE client_id = ?` repository filter | PostgreSQL RLS with `set_config` | Application filter has 100% miss-prone surface area; one missing filter = leakage. RLS is enforced at the planner. |
| Audit log immutability | Application-level "soft-delete" or "is_archived" | DB trigger + REVOKE | Anyone with DB credentials can mutate without triggers. Triggers + REVOKE = legal-grade. |
| GSTIN/PAN/CIN/DIN format validation | Hand-rolled string-length checks | Documented Indian regex patterns (see Code Examples) | Indian formats have embedded checksums and state codes. Use canonical regex from `tk120404/gst` or government-published patterns. |
| Recursive parent-child traversal | Loop in Python issuing N queries | PostgreSQL recursive CTE | N+1 at depth 5+. CTE is one query, indexed. |
| Multi-step form state | useState across 4 components + manual coordination | React Hook Form per step + Zustand persist | RHF gives validation + dirty tracking + async submit. Zustand persist gives refresh-survival. |
| Bulk action UI | useState + custom selection logic | `@tanstack/react-table` row selection API | Built-in selection state, header indeterminate checkbox, keyboard nav, virtualization-ready. |
| Server state caching | Manual axios + setState | `@tanstack/react-query` | Optimistic updates, query invalidation, stale-while-revalidate, request deduplication on tenant switch. |
| Field-level encryption | XOR or simple symmetric without HMAC | `cryptography.fernet.Fernet` | Fernet is AES-128-CBC + HMAC-SHA256 + URL-safe encoding + key rotation support. INFRA-06 mandates Fernet specifically. |
| State machine | If-else chain with cross-cutting validation | Hand-rolled dict (5 states) OR `transitions==0.9.3` (10+ states) | At 5 states, dict is clearer. CONTEXT D-03 allows dict. |
| RBAC | Per-route `if user.role == "admin"` | Permission registry + `require_compliance_permission` factory | Fewer routes break when adding a role. Centralized audit of who-can-what. |
| JSONB indexing | Generic GIN | `jsonb_path_ops` for containment, B-tree expression for fixed paths | `jsonb_path_ops` is half the size, faster for `@>`. |

**Key insight:** Phase 9 is a "use the boring stack" phase. The compliance domain has so many invariants (legal, regulatory, multi-tenant, immutable) that custom solutions create attack surfaces. Every "Don't Hand-Roll" item maps to a documented PostgreSQL or library feature.

## Runtime State Inventory

> Not applicable — Phase 9 is a greenfield extension (new tables, new code paths). No rename, refactor, or migration of existing v1.0 state. The ONLY pre-existing artifact touched is `audit_logs`, which is hardened in-place (REVOKE + trigger added; no schema change, no data loss).

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — all new tables. Existing `audit_logs` rows untouched. | None. |
| Live service config | None. | None. |
| OS-registered state | None. | None. |
| Secrets/env vars | NEW: `FERNET_KEY` for INFRA-06. NEW: `app_migrator` and `app_runtime` DB passwords. | Add to `.env` template; document key-rotation runbook. |
| Build artifacts | None — npm install adds new dependencies, no rebuild risk for existing v1.0 features. | None. |

**Verified by:** existing `backend/app/models/audit_log.py` schema is preserved; `0010_add_audit_logs.py` migration creates the table; new migration `0014_audit_log_immutability.py` ONLY adds trigger + REVOKE.

## Common Pitfalls

### Pitfall 1: RLS bypass via test database role

**What goes wrong:** Integration tests run as the table owner or superuser; RLS policies appear to filter correctly but in production with `app_runtime` role they may be too restrictive (or test data was wrong). Worse: a missing `FORCE ROW LEVEL SECURITY` means owner-role tests pass while production fails open in a different scenario.

**Why it happens:** PostgreSQL grants table owners and superusers RLS bypass by default. Test fixtures often use the migration role (which is the owner).

**How to avoid:**
- ALL integration tests run as the `app_runtime` role.
- A test fixture creates a second test client and confirms `db.query(ComplianceNotice).all()` returns ZERO when `set_config('app.current_client_id', '<other_client>')` is set.
- `ALTER TABLE ... FORCE ROW LEVEL SECURITY` on every client-scoped table.
- CI grep guard: any new `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` migration MUST be paired with `FORCE`.

**Warning signs:** RLS test that creates two clients but then queries as the migration role — test passes, production leaks.

### Pitfall 2: Audit log trigger dropped during a routine migration

**What goes wrong:** Developer writes a migration that adds a column to `audit_logs`. The migration uses `op.alter_column` which drops and recreates the trigger as a side effect. After deploy, audit immutability is silently disabled.

**Why it happens:** Some Alembic operations recreate table dependencies. Triggers attached via raw `op.execute()` are not re-applied unless the migration explicitly does so.

**How to avoid:**
- All `audit_logs` migrations include an explicit "verify trigger present" step at the end: `SELECT 1 FROM pg_trigger WHERE tgrelid = 'audit_logs'::regclass AND tgname = 'audit_logs_immutability'` raises if missing.
- A pytest fixture asserts this on every test run that touches `audit_logs` (smoke test).
- Code review checklist: any migration touching `audit_logs` requires a +1 from a second reviewer.

**Warning signs:** A `SELECT count(*) FROM pg_trigger WHERE tgname = 'audit_logs_immutability'` returns 0 in production after a deploy.

### Pitfall 3: Compliance role check at the route layer (bypassable)

**What goes wrong:** New endpoint added without `Depends(require_compliance_permission(...))`. RBAC is bypassed by anyone authenticated.

**How to avoid:**
- Default-deny pattern: a global FastAPI middleware checks that every `/api/compliance/*` route includes a compliance permission dependency, otherwise rejects.
- Test: a parametrized pytest enumerates all routes under the compliance prefix and asserts each has either `require_compliance_permission` OR is whitelisted as public (e.g., health checks).

**Warning signs:** A new compliance endpoint accepts requests from unauthorized roles.

### Pitfall 4: Auditor membership not revoked when access_end passes

**What goes wrong:** Auditor's `access_end = 2026-04-30`. On 2026-05-01, the auditor still has read access because the check is only at membership creation, not on every request.

**How to avoid:**
- Middleware (`AuditorExpiryMiddleware`) checks `access_end` on EVERY request that resolves a `ClientMembership`.
- Cached membership objects (Redis) include TTL not exceeding `access_end - now()`.
- Background job daily flags expired memberships and emits an audit log entry.

**Warning signs:** An auditor whose `access_end` is in the past is still able to retrieve notices.

### Pitfall 5: Client switcher allows switching to a client the user has no membership for

**What goes wrong:** Frontend sends `X-Client-Id: 999` for a client the user doesn't belong to. Backend trusts the header.

**How to avoid:**
- Middleware looks up `(user_id, client_id) → membership` and rejects with 403 if not found OR membership expired.
- Frontend Zustand store cross-checks `activeClientId` against fresh `/memberships/me` response on mount and on focus.

### Pitfall 6: Cross-client SQL aggregation queries miss RLS

**What goes wrong:** D-23 "All Clients" view runs a dashboard query like `SELECT client_id, COUNT(*) FROM notices GROUP BY 1`. If "all clients" mode is implemented by setting `app.current_client_id` to NULL, the policy `client_id = NULL::int` is FALSE — query returns ZERO rows.

**How to avoid:**
- Use a separate policy `OR (current_setting('app.cross_client_mode', true) = 'true' AND <role-allows>)` (see Pattern 7).
- OR: route "All Clients" queries through a separate endpoint that swaps to a `BYPASSRLS` role. Document the security implications.

### Pitfall 7: PII in Celery task arguments and Render logs

**What goes wrong:** Celery task `send_notice_summary(notice_dict)` passes the full notice with GSTIN/PAN/penalty in cleartext. The Redis broker queue stores it. Render logs catch task arg dumps.

**How to avoid:**
- Celery tasks accept ONLY notice IDs. Workers fetch fresh data inside the task using `client_id` context (set via `set_config()` at task start).
- structlog redaction filter strips fields named `gstin`, `pan`, `cin`, `din`, `penalty`, `tax_demand`, `interest`, `total_liability` before any log output.
- Pre-deploy grep: any logger.info/debug call passing a Pydantic dict triggers a code review flag.

**Warning signs:** `redis-cli LRANGE celery 0 5` shows notice content.

### Pitfall 8: State machine bypass via direct ORM update

**What goes wrong:** A developer writes `notice.status = NoticeStatus.SUBMITTED; db.commit()` instead of `notice_service.transition(notice, NoticeStatus.SUBMITTED)`. The transition is logged as undefined; no activity entry created.

**How to avoid:**
- SQLAlchemy `validates` decorator on `ComplianceNotice.status` raises if the new value isn't reached via `transition()`. Use a thread-local flag set by the service layer.
- Easier alternative: never expose `notice.status = ...` — the `status` column has no public setter; service layer is the only path.
- Integration test: every `audit_logs.action='notice_status_changed'` row has a paired `notice_activity` row.

## Code Examples

Verified patterns from official sources.

### RLS migration

```python
# Source: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
#         https://atlasgo.io/guides/orms/sqlalchemy/row-level-security

# alembic/versions/0015_compliance_rls_policies.py
from alembic import op

def upgrade():
    op.execute("""
        ALTER TABLE compliance_notices ENABLE ROW LEVEL SECURITY;
        ALTER TABLE compliance_notices FORCE ROW LEVEL SECURITY;

        CREATE POLICY tenant_isolation ON compliance_notices
          FOR ALL TO app_runtime
          USING (client_id = current_setting('app.current_client_id', true)::int)
          WITH CHECK (client_id = current_setting('app.current_client_id', true)::int);

        CREATE POLICY cross_client_view ON compliance_notices
          FOR SELECT TO app_runtime
          USING (
            current_setting('app.cross_client_mode', true) = 'true'
            AND current_setting('app.user_id', true)::int IN (
              SELECT user_id FROM compliance_client_memberships
              WHERE compliance_role IN ('compliance_head', 'ca_consultant', 'cfo')
              AND (access_end IS NULL OR access_end > now())
            )
          );
    """)
```

### Audit immutability migration

```python
# Source: https://wiki.postgresql.org/wiki/Audit_trigger
#         https://vladmihalcea.com/postgresql-audit-logging-triggers/

# alembic/versions/0014_audit_log_immutability.py
from alembic import op

def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_audit_log_modification()
        RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'audit_logs is append-only — % is forbidden', TG_OP
            USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER audit_logs_immutability
          BEFORE UPDATE OR DELETE ON audit_logs
          FOR EACH ROW EXECUTE FUNCTION reject_audit_log_modification();

        REVOKE UPDATE, DELETE ON audit_logs FROM app_runtime;
        REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC;

        ALTER TABLE audit_logs
          ALTER COLUMN created_at SET DEFAULT clock_timestamp();
    """)
```

### Indian identifier validators

```python
# Source: https://github.com/tk120404/gst (community-maintained canonical regex)
#         https://www.regextester.com/102594 (cross-verified)

# backend/app/compliance/utils/indian_validators.py
import re
from pydantic import BaseModel, validator

GSTIN_RX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PAN_RX   = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
CIN_RX   = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
DIN_RX   = re.compile(r"^[0-9]{8}$")

# CGST notice number patterns (D-07)
NOTICE_NUMBER_PATTERNS = {
    "GST": [
        re.compile(r"^DRC-0[1-7]/[0-9]+/[0-9]{4}-[0-9]{2}$"),  # demand
        re.compile(r"^ASMT-1[0-7]/[0-9]+/[0-9]{4}-[0-9]{2}$"),  # assessment
    ],
    "IT": [
        re.compile(r"u/s\s*(143\(2\)|148|156|271)"),  # IT Act sections
    ],
    # ... MCA, RBI, SEBI patterns
}

def validate_gstin(value: str) -> bool:
    if not GSTIN_RX.match(value):
        return False
    # State code check: first 2 chars are 01-37 (valid state codes 2026)
    state_code = int(value[:2])
    return 1 <= state_code <= 37 or state_code in (97, 99)  # 97=Other Territory, 99=Center

def validate_pan_in_gstin(gstin: str) -> bool:
    """PAN is embedded in chars 3-12 of GSTIN."""
    if not GSTIN_RX.match(gstin):
        return False
    return PAN_RX.match(gstin[2:12]) is not None
```

### State machine integration with audit log

```python
# backend/app/compliance/services/notice_service.py

def transition_notice_status(
    db: Session, notice_id: int, new_status: NoticeStatus,
    user: User, reason: str | None = None,
) -> None:
    notice = db.query(ComplianceNotice).filter_by(id=notice_id).with_for_update().one()
    old_status = notice.status

    validate_transition(old_status, new_status)  # raises InvalidTransitionError

    notice.status = new_status
    notice.status_changed_at = datetime.now(timezone.utc)

    # User-facing activity (D-09)
    db.add(NoticeActivity(
        notice_id=notice.id, user_id=user.id, type="status_change",
        details={"from": old_status, "to": new_status, "reason": reason},
    ))

    db.commit()

    # Immutable system audit (AUDIT-02). BackgroundTask pattern from existing code.
    log_audit_event(
        user_id=user.id, action="notice_status_changed",
        resource_type="ComplianceNotice", resource_id=notice.id,
        details={"before_value": old_status.value, "after_value": new_status.value, "reason": reason},
    )
```

### Bulk actions endpoint with partial-failure semantics

```python
# backend/app/compliance/routers/notices.py

class BulkUpdateRequest(BaseModel):
    notice_ids: list[int]
    new_status: NoticeStatus

class BulkResult(BaseModel):
    id: int
    success: bool
    error: str | None = None

@router.post("/bulk", response_model=dict)
def bulk_update_status(
    payload: BulkUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_compliance_permission(CompliancePermission.NOTICE_BULK_UPDATE)),
):
    results: list[BulkResult] = []
    for nid in payload.notice_ids:
        try:
            transition_notice_status(db, nid, payload.new_status, user)
            results.append(BulkResult(id=nid, success=True))
        except InvalidTransitionError as e:
            results.append(BulkResult(id=nid, success=False, error=str(e)))
        except Exception as e:
            results.append(BulkResult(id=nid, success=False, error="Internal error"))
    ok = sum(1 for r in results if r.success)
    return {"results": [r.model_dump() for r in results],
            "summary": {"ok": ok, "failed": len(results) - ok}}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Application-layer tenant filter (`WHERE client_id = ?`) | PostgreSQL RLS with `set_config` | Stable since PG 9.5 (2016); FORCE since 9.5; mature in production at AWS, Supabase scale | Required for CLIENT-04 zero-leakage guarantee |
| Application-level audit log | DB triggers + REVOKE | Standard since PostgreSQL 9.x | Required for regulatory inspection readiness (PITFALLS Pitfall 4) |
| `transitions` library | Hand-rolled dict for ≤5 states | No change — both still valid | Choose by complexity: 5 states = dict; 10+ states = library |
| React Hook Form `watch()` | `getValues()` / `useWatch()` | React 19 introduced compatibility issues | Affects multi-step wizard implementation |
| Casbin / OSO for RBAC | Custom `Depends()` factory for ≤10 roles | No change — both still valid | CONTEXT D-26 (flat permissions) tips toward custom |
| `jsonb_ops` GIN index | `jsonb_path_ops` for containment-only | PostgreSQL 9.4 (2014) | Half the size, 2-3x faster for `@>` |
| Recursive CTE without CYCLE clause | CTE with `CYCLE id SET is_cycle USING path` | PostgreSQL 14 (2021) | Built-in cycle detection; depth limit still recommended |

**Deprecated/outdated:**
- `now()` for audit timestamps: use `clock_timestamp()` (transaction-start vs wall-clock; documented in PITFALLS Pitfall 4).
- `bert-base-uncased` (in research SUMMARY): not Phase 9 concern — NER deferred to Phase 10.
- `requests.Session` for portal auth (research PITFALLS Pitfall 1): not Phase 9 concern — portal integration is Phase 14.

## Open Questions

### Q1: "All Clients" mode RLS strategy — single role + dual policy, or role-swap?

**What we know:** Two viable patterns exist (verified at AWS RLS docs and Bytebase guide):
- **Pattern A:** Single `app_runtime` role with two policies (per-tenant + cross-tenant gated by config var). Simpler ops, single connection pool.
- **Pattern B:** Two roles (`app_runtime`, `app_cross_tenant`); middleware switches `SET ROLE` per request. Cleaner permission boundary.

**What's unclear:** Performance of Pattern A under load — every query evaluates both policies. At Phase 9 scale (<1000 clients per CA, <10K notices per client) this is irrelevant; at scale, may need to switch.

**Recommendation:** **Pattern A for Phase 9** (simpler, single role). Document the migration path to Pattern B in a `docs/compliance/RLS_DESIGN.md` for a future scale phase.

### Q2: Should `notice_activity` be append-only?

**What we know:** D-09 says "captures status_change, note_added, file_attached, assigned" — these are user actions, not system events. Users may legitimately want to edit notes ("typo fix") or remove erroneous attachments.

**What's unclear:** CONTEXT doesn't explicitly say activity is append-only OR mutable.

**Recommendation:** **Mutable for Phase 9** (no triggers). Rationale: activity timeline is user-facing and conversation-like (Slack thread), not regulatory record. The immutable audit log captures the underlying truth. Document in plan and confirm with user during plan-check.

### Q3: Should `compliance_role` on ClientMembership be stored as enum or string?

**What we know:** v1.0 `users.role` is stored as `String(20)` not Enum (see `backend/app/models/user.py:25`). Comment-thread evidence in the existing code suggests the team chose string for migration flexibility.

**What's unclear:** Should we follow that convention for consistency, or use a proper Postgres ENUM type?

**Recommendation:** **Follow v1.0 convention — `String(20)` with Python Enum at the application layer** (already established pattern). Adding a CHECK constraint at DB level provides validation without Postgres ENUM migration friction.

### Q4: Should the active client switcher mutate URL or only Zustand state?

**What we know:** Slack uses URL-state; Notion uses workspace-state in the host. URL-state has the advantage of shareable links per-client.

**What's unclear:** Does the user want shareable URLs like `/dashboard/compliance/clients/42/notices`?

**Recommendation:** **Hybrid**: detail pages embed `client_id` in URL (`/compliance/clients/[id]/notices/[notice_id]`); list/dashboard pages use Zustand only (URL stays at `/dashboard/compliance` for cleanliness). Confirm during plan-check.

## Environment Availability

> Probed via shell on 2026-04-27.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Per memory directive — all dev runs in docker-compose | ✓ | 29.3.1 | — |
| Docker Compose | Existing v1.0 stack | ✓ | (Docker bundled) | — |
| Node.js | Frontend builds | ✓ | 24.14.0 (well above Next.js 15 requirement) | — |
| Python 3 | Backend | ✓ | 3.12.3 (≥ 3.8 required) | — |
| pytest | Backend tests | ✓ | 9.0.3 | — |
| PostgreSQL (host) | Production | ✓ | 16.2.4 (psql client) | Docker postgres image (already in compose) |
| `pg_isready` | Health checks | ✓ | bundled | — |
| Redis CLI (host) | Manual broker checks | ✗ | — | Docker container (`docker exec -it smartdocs-redis redis-cli`) |
| Tesseract OCR | LIFE-02 reuses v1.0 OCR | ✓ (assumed in backend Dockerfile) | inherited | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- `redis-cli` on host — fallback is `docker exec`. Not blocking; only used for ad-hoc inspection.

**New env vars Phase 9 introduces (no current value, must be added):**
- `FERNET_KEY` — INFRA-06 PII encryption key. Generated once via `Fernet.generate_key()`; rotated via `MultiFernet`.
- `DATABASE_URL_RUNTIME` — `app_runtime` connection string (RLS-subject role).
- `DATABASE_URL_MIGRATOR` — `app_migrator` connection string (RLS-bypass role for migrations).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + httpx (already installed) |
| Config file | `backend/tests/conftest.py` (existing — needs extension for Phase 9 fixtures) |
| Quick run command | `cd backend && pytest -x --no-header -q` |
| Full suite command | `cd backend && pytest --tb=short && cd ../frontend && npm run lint` |
| Per-test marker for slow integration | `@pytest.mark.integration` (decision for Phase 9 — currently unused) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIFE-01 | Notice upload accepts PDF/JPG/PNG, links to Document.notice_id | integration | `pytest tests/test_compliance_notices.py::test_notice_upload_links_document` | ❌ Wave 0 |
| LIFE-03 | Manual metadata accepts valid GSTIN, rejects invalid | unit | `pytest tests/test_indian_validators.py -x` | ❌ Wave 0 |
| LIFE-04 | Status transition Received→Under Review allowed; Received→Submitted blocked | unit | `pytest tests/test_notice_state_machine.py -x` | ❌ Wave 0 |
| LIFE-04 | Every status change writes paired audit_log + notice_activity rows | integration | `pytest tests/test_notice_service.py::test_transition_writes_both_records` | ❌ Wave 0 |
| LIFE-05 | Recursive CTE returns full chain ancestors+descendants | integration | `pytest tests/test_notice_chain.py::test_chain_returns_ancestors_and_descendants` | ❌ Wave 0 |
| LIFE-05 | Cycle in parent_notice_id terminates within max_depth | integration | `pytest tests/test_notice_chain.py::test_chain_terminates_on_cycle` | ❌ Wave 0 |
| LIFE-07 | Filter by authority/status returns only matching | integration | `pytest tests/test_notice_query.py::test_filter_combinations` | ❌ Wave 0 |
| LIFE-08 | Bulk update returns per-row success/failure with partial errors | integration | `pytest tests/test_compliance_notices.py::test_bulk_update_partial_failure` | ❌ Wave 0 |
| **AUDIT-01** | **DB rejects UPDATE on audit_logs (RAISE EXCEPTION)** | **integration** | `pytest tests/test_audit_immutability.py::test_update_raises` | ❌ Wave 0 |
| **AUDIT-01** | **DB rejects DELETE on audit_logs** | **integration** | `pytest tests/test_audit_immutability.py::test_delete_raises` | ❌ Wave 0 |
| **AUDIT-01** | **app_runtime role lacks UPDATE/DELETE privilege (REVOKE verified)** | **integration** | `pytest tests/test_audit_immutability.py::test_app_role_lacks_privilege` | ❌ Wave 0 |
| AUDIT-02 | audit_logs.details captures before_value/after_value for status changes | integration | `pytest tests/test_audit_capture.py::test_status_change_captures_diff` | ❌ Wave 0 |
| AUDIT-02 | audit_logs.created_at uses clock_timestamp (monotonic across transactions) | integration | `pytest tests/test_audit_capture.py::test_clock_timestamp_monotonic` | ❌ Wave 0 |
| RBAC-01..06 | Each role has correct permission set per registry | unit | `pytest tests/test_permission_registry.py -x` | ❌ Wave 0 |
| RBAC-01..06 | require_compliance_permission rejects role without perm | integration | `pytest tests/test_compliance_endpoints.py::test_role_permission_matrix` (parametrized 7 roles × 12 endpoints) | ❌ Wave 0 |
| **RBAC-04** | **Auditor with expired access_end is rejected on every request (not just login)** | **integration** | `pytest tests/test_auditor_expiry.py::test_expired_membership_rejected` | ❌ Wave 0 |
| RBAC-04 | Future access_start blocks early access | integration | `pytest tests/test_auditor_expiry.py::test_future_access_start_blocked` | ❌ Wave 0 |
| CLIENT-01 | Create client + multiple registrations (GSTIN/PAN/CIN) | integration | `pytest tests/test_client_management.py::test_create_with_registrations` | ❌ Wave 0 |
| CLIENT-02 | Multi-GSTIN per client (different states) | integration | `pytest tests/test_client_management.py::test_multi_gstin` | ❌ Wave 0 |
| CLIENT-03 | Per-client dashboard aggregates count notices correctly | integration | `pytest tests/test_dashboard.py::test_client_dashboard_aggregates` | ❌ Wave 0 |
| **CLIENT-04** | **Zero cross-client leakage — query as Client A returns no Client B notices** | **integration** | `pytest tests/test_rls_isolation.py::test_no_cross_client_leakage` (mandatory; runs as `app_runtime` role) | ❌ Wave 0 |
| **CLIENT-04** | **RLS test fails-closed when set_config not set** | **integration** | `pytest tests/test_rls_isolation.py::test_unset_tenant_returns_empty` | ❌ Wave 0 |
| **CLIENT-04** | **FORCE ROW LEVEL SECURITY is set on every client-scoped table (CI grep guard)** | **integration** | `pytest tests/test_rls_isolation.py::test_all_client_tables_have_force_rls` | ❌ Wave 0 |
| CLIENT-04 | "All Clients" mode returns rows from all eligible client memberships | integration | `pytest tests/test_rls_isolation.py::test_cross_client_mode_eligible` | ❌ Wave 0 |
| CLIENT-04 | "All Clients" mode is rejected for ineligible roles (Staff, Auditor, Legal, Finance) | integration | `pytest tests/test_rls_isolation.py::test_cross_client_mode_rejected_for_ineligible_roles` | ❌ Wave 0 |
| CLIENT-05 | Onboarding wizard creates Client + N Registrations + M Memberships atomically | integration | `pytest tests/test_client_onboarding.py::test_atomic_creation` | ❌ Wave 0 |
| CLIENT-06 | config_overrides JSONB containment query uses GIN index | integration | `pytest tests/test_jsonb_query.py::test_containment_uses_gin` (EXPLAIN check) | ❌ Wave 0 |
| CLIENT-07 | Monthly health summary report generated on demand | integration | `pytest tests/test_reports.py::test_health_summary_pdf` | ❌ Wave 0 |
| INFRA-05 | RegulatoryCalendar contains seeded 2026 holidays | integration | `pytest tests/test_regulatory_calendar.py::test_2026_holidays_seeded` | ❌ Wave 0 |
| INFRA-06 | Fernet roundtrip encrypt/decrypt for GSTIN field | unit | `pytest tests/test_pii_encryption.py::test_fernet_roundtrip` | ❌ Wave 0 |
| INFRA-06 | Log redaction strips PII fields before output | unit | `pytest tests/test_log_redaction.py::test_pii_stripped` | ❌ Wave 0 |
| INFRA-07 | (same as AUDIT-01) | (same) | (same) | (same) |

**Frontend tests (smoke-level for Phase 9):**

| Behavior | Test Type | Automated Command | Wave |
|----------|-----------|-------------------|------|
| Onboarding wizard validates GSTIN per step | manual smoke | Manual click-through | Phase 9 verification |
| Client switcher persists across page refresh | manual smoke | Manual click-through | Phase 9 verification |
| Bulk action bar appears on row selection | manual smoke | Manual click-through | Phase 9 verification |
| Notice detail two-column layout | visual smoke | Manual screenshot review | Phase 9 verification |

(Frontend has no Jest setup in v1.0; adding it for one phase is overkill. Phase 9 ships manual smoke tests; comprehensive frontend testing is a Phase 11+ infrastructure task.)

### Empirical Verification Approaches (per high-risk requirement)

**CLIENT-04 — Zero cross-client leakage (the most critical empirical test):**

The test fixture creates two clients (`client_a`, `client_b`), three users (`user_in_a`, `user_in_b`, `user_in_both`), and 10 notices in each client. The test runs as the `app_runtime` role (NOT the migrator/owner role). Then:

```python
def test_no_cross_client_leakage(db_as_app_runtime, client_a, client_b, user_in_a):
    # Set tenant context to client_a
    db_as_app_runtime.execute(text("SELECT set_config('app.current_client_id', :cid, true)"),
                              {"cid": str(client_a.id)})
    # All queries — direct, joined, aggregated
    notices = db_as_app_runtime.query(ComplianceNotice).all()
    assert all(n.client_id == client_a.id for n in notices)
    assert len(notices) == 10  # exactly client_a's notices
    # Try ad-hoc raw SQL bypass attempt
    rows = db_as_app_runtime.execute(text(
        "SELECT * FROM compliance_notices WHERE client_id = :other"),
        {"other": client_b.id}).all()
    assert rows == []  # RLS enforces even with explicit WHERE
```

This single test asserts CLIENT-04 holds for the most-attacked surface. Run on every CI build; failure blocks merge.

**AUDIT-01 — Immutability under attack:**

```python
def test_update_raises(db_as_app_runtime, audit_log_row):
    with pytest.raises(InternalError) as exc_info:
        db_as_app_runtime.execute(text(
            "UPDATE audit_logs SET action = 'tampered' WHERE id = :id"),
            {"id": audit_log_row.id})
    assert "append-only" in str(exc_info.value)

def test_delete_raises(db_as_app_runtime, audit_log_row):
    with pytest.raises(InternalError) as exc_info:
        db_as_app_runtime.execute(text(
            "DELETE FROM audit_logs WHERE id = :id"),
            {"id": audit_log_row.id})
    assert "append-only" in str(exc_info.value)

def test_app_role_lacks_privilege(db_as_app_runtime):
    """REVOKE check — even if trigger were dropped, REVOKE blocks."""
    rows = db_as_app_runtime.execute(text("""
        SELECT privilege_type FROM information_schema.role_table_grants
        WHERE table_name = 'audit_logs' AND grantee = 'app_runtime'
    """)).all()
    privs = {r[0] for r in rows}
    assert 'UPDATE' not in privs
    assert 'DELETE' not in privs
    assert 'INSERT' in privs  # required for logging
```

**RBAC role boundaries — parametrized matrix:**

```python
@pytest.mark.parametrize("role,permission,expect", [
    (ComplianceRole.STAFF, CompliancePermission.NOTICE_CREATE, True),
    (ComplianceRole.STAFF, CompliancePermission.NOTICE_APPROVE, False),
    (ComplianceRole.AUDITOR, CompliancePermission.NOTICE_VIEW, True),
    (ComplianceRole.AUDITOR, CompliancePermission.NOTICE_CREATE, False),
    (ComplianceRole.CFO, CompliancePermission.NOTICE_APPROVE, False),
    (ComplianceRole.CFO, CompliancePermission.REPORT_VIEW, True),
    # ... full 7 × 12 matrix
])
def test_role_permission_matrix(client_with_membership, role, permission, expect):
    user = client_with_membership(compliance_role=role)
    response = api_call_requiring(user, permission)
    if expect:
        assert response.status_code != 403
    else:
        assert response.status_code == 403
```

**Auditor expiry — time-based:**

```python
def test_expired_membership_rejected(freezer, db, auditor_membership):
    auditor_membership.access_end = datetime(2026, 4, 30, tzinfo=timezone.utc)
    db.commit()
    freezer.move_to("2026-05-01")  # past access_end
    response = client.get("/compliance/notices",
                         headers={"Authorization": f"Bearer {auditor_token}"})
    assert response.status_code == 403
    assert "expired" in response.json()["detail"].lower()
```

### Sampling Rate

- **Per task commit:** `pytest -x --no-header -q tests/test_<scope>.py` (single test file under work)
- **Per wave merge:** `pytest --tb=short` (full suite). Critical: must include `test_rls_isolation.py` and `test_audit_immutability.py` — these are the security gates.
- **Phase gate:** Full backend suite + frontend lint + manual smoke checklist green before `/gsd:verify-work`.
- **Pre-deploy gate:** Re-run RLS isolation test against actual production-shape DB (in CI, against a Postgres container with `app_runtime` role created).

### Wave 0 Gaps

- [ ] `tests/conftest.py` — extend with: `db_as_app_runtime` fixture (creates `app_runtime` role + connection), `client_a/client_b` fixtures (two-tenant setup), `auditor_membership` fixture (with parametrizable access_start/end), `freezer` fixture (uses `pytest-freezer` or `freezegun`).
- [ ] `tests/test_rls_isolation.py` — RLS tests as described above.
- [ ] `tests/test_audit_immutability.py` — trigger + REVOKE tests.
- [ ] `tests/test_notice_state_machine.py` — pure unit tests on the dict.
- [ ] `tests/test_permission_registry.py` — pure unit tests on the matrix.
- [ ] `tests/test_indian_validators.py` — regex unit tests with golden samples.
- [ ] `tests/test_compliance_endpoints.py` — parametrized 7-role × N-endpoint matrix.
- [ ] `tests/test_auditor_expiry.py` — middleware tests with `freezegun`/`pytest-freezer`.
- [ ] `tests/test_pii_encryption.py` — Fernet roundtrip.
- [ ] `tests/test_log_redaction.py` — structlog filter tests.
- [ ] Framework install: `pip install pytest-freezer` — for time-based Auditor tests.

## Sources

### Primary (HIGH confidence)
- [PostgreSQL Documentation: Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) — RLS, FORCE, BYPASSRLS, table owner bypass semantics
- [PostgreSQL Documentation: WITH Queries (CTEs)](https://www.postgresql.org/docs/current/queries-with.html) — recursive CTE syntax, CYCLE clause
- [PostgreSQL Documentation: Trigger Functions](https://www.postgresql.org/docs/current/plpgsql-trigger.html) — RAISE EXCEPTION, BEFORE triggers
- [PostgreSQL Documentation: GIN Indexes](https://www.postgresql.org/docs/current/gin.html) — jsonb_ops vs jsonb_path_ops
- [PostgreSQL Wiki: Audit Trigger](https://wiki.postgresql.org/wiki/Audit_trigger) — append-only audit pattern
- [SQLAlchemy 2.0 PostgreSQL Dialect](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html) — JSONB, postgresql_using, postgresql_ops
- [Atlas Guide: Using Row-Level Security in SQLAlchemy](https://atlasgo.io/guides/orms/sqlalchemy/row-level-security) — set_config + middleware pattern
- [AWS: Multi-tenant data isolation with PostgreSQL RLS](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/) — production multi-tenant patterns
- [Bytebase: Common Postgres RLS footguns](https://www.bytebase.com/blog/postgres-row-level-security-footguns/) — FORCE, owner bypass, testing pitfalls
- [pytransitions/transitions GitHub](https://github.com/pytransitions/transitions) — state machine library reference
- [pganalyze: Understanding Postgres GIN Indexes](https://pganalyze.com/blog/gin-index) — operator class trade-offs
- [Vlad Mihalcea: PostgreSQL audit logging using triggers](https://vladmihalcea.com/postgresql-audit-logging-triggers/) — production audit patterns
- Existing project files verified directly: `backend/app/models/audit_log.py`, `backend/app/models/user.py`, `backend/app/utils/security.py`, `backend/alembic/versions/0010_add_audit_logs.py`, `backend/app/services/audit_service.py`, `backend/requirements.txt`, `frontend/package.json`

### Secondary (MEDIUM confidence)
- [olirice/alembic_utils](https://github.com/olirice/alembic_utils) — alternate trigger management (chosen NOT to use for Phase 9 simplicity)
- [Markus Oberlehner: react-hook-form + React 19 + Next.js 15 App Router](https://markus.oberlehner.net/blog/using-react-hook-form-with-react-19-use-action-state-and-next-js-15-app-router) — RHF compatibility
- [Build with Matija: React Hook Form Multi-Step Tutorial — Zustand + Zod](https://www.buildwithmatija.com/blog/master-multi-step-forms-build-a-dynamic-react-form-in-6-simple-steps) — wizard pattern
- [Eleken: Bulk action UX guidelines](https://www.eleken.co/blog-posts/bulk-actions-ux) — floating action bar UX
- [shadcn/ui: Todo List Bulk Actions Block](https://www.shadcn.io/blocks/todo-list-bulk-actions) — React + tanstack-table bulk pattern
- [Permit.io: FastAPI RBAC Tutorial](https://www.permit.io/blog/fastapi-rbac-full-implementation-tutorial) — Depends factory patterns
- [tk120404/gst GitHub](https://github.com/tk120404/gst) — community canonical GSTIN regex
- [B S Sridhar & Co: Difference Between ASMT-10 and DRC-01](https://www.bssridhar.com/difference-between-asmt-10-and-drc-01-under-gst-know-about-this-for-correct-compliance/) — CGST notice format domain knowledge
- [The GST Calculator India: GSTIN Validator/Decoder](https://thegstcalculator.in/tools/gst-number-validator) — state code validation reference

### Tertiary (LOW confidence — needs validation before implementation)
- Specific holiday data for INFRA-05 RegulatoryCalendar seed — must source CBDT/CBIC official 2026 holiday lists from `cbic.gov.in` and `incometax.gov.in` before writing seed migration.
- Notice number regex micro-patterns for IT/MCA/RBI/SEBI (D-07) — only GST DRC-01/ASMT-10 patterns are well-established; IT u/s 143(2) format is documented; MCA/RBI/SEBI patterns need empirical samples from real notices.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every package version verified against PyPI/npm on 2026-04-27.
- Architecture (RLS, audit immutability, state machine, recursive CTE, JSONB GIN): HIGH — all patterns verified against postgresql.org primary docs + multiple secondary sources.
- RBAC permission registry: HIGH — extends existing v1.0 `require_admin` pattern; no novel invention.
- Multi-step wizard, bulk actions, client switcher: MEDIUM-HIGH — community-documented patterns; the React 19 + RHF compatibility is the only watch-item.
- Indian regex patterns: MEDIUM — GSTIN/PAN are HIGH (canonical); CIN/DIN MEDIUM; notice number patterns LOW for non-GST authorities.
- Pitfalls: HIGH — derived from existing `.planning/research/PITFALLS.md` (which has primary-source backing) plus Phase-9-specific checks.

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (30 days — stack is stable; only RHF + React 19 watch-item could shift). Re-verify package versions if planning extends beyond.

## RESEARCH COMPLETE

**Phase:** 9 - Compliance Foundation
**Confidence:** HIGH

### Key Findings

1. **PostgreSQL RLS with `set_config('app.current_client_id')` is the canonical pattern for CLIENT-04 zero-leakage.** Critical: `ALTER TABLE ... FORCE ROW LEVEL SECURITY` is required (otherwise table owner bypasses RLS during testing); the application must use a non-owner non-BYPASSRLS DB role (`app_runtime`); the session var is set at connection-checkout (or middleware), not per-query.
2. **Audit immutability requires both REVOKE and a trigger** — REVOKE blocks at SQL grant level; the trigger blocks attempts even if a future grant accidentally restores UPDATE/DELETE. The existing `audit_logs` table from migration 0010 is hardened in-place with a single new migration; no schema change, no data loss.
3. **State machine for 5 notice statuses is best implemented as a hand-rolled dict** — the `transitions==0.9.3` library adds inheritance complexity that doesn't pay off at this scale. CONTEXT D-03 explicitly allows the dict approach.
4. **7-role compliance RBAC fits a custom `Depends()` factory pattern** — Casbin/OSO are overkill for flat permissions per role (CONTEXT D-26). The factory extends the existing v1.0 `require_admin` pattern. Auditor time-bound access (D-27) is enforced in middleware, not just at membership-creation time.
5. **The Validation Architecture mandates three security tests as merge gates** — `test_rls_isolation.py::test_no_cross_client_leakage` (CLIENT-04), `test_audit_immutability.py::test_update_raises` + `test_delete_raises` (AUDIT-01), and `test_role_permission_matrix` (RBAC-01..06). Wave 0 must establish these before any business logic is built.

### File Created
`/home/sraav/Desktop/Smart_Docs_Prod_Labs/Smart-Document-Management-System/.planning/phases/09-compliance-foundation/09-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All versions verified against PyPI/npm 2026-04-27 |
| Architecture (RLS, audit, state machine, RBAC, RTC) | HIGH | Every pattern has postgresql.org or equivalent primary-source backing |
| Pitfalls | HIGH | Derived from existing PITFALLS.md plus Phase-9-specific checks |
| Indian regex (GSTIN/PAN) | HIGH | Canonical community-maintained patterns |
| Indian regex (notice numbers) | MEDIUM | GST DRC-01/ASMT-10 well-established; other authorities need empirical samples |
| Frontend wizard/switcher/bulk | MEDIUM-HIGH | Patterns verified; React 19 + RHF compatibility is sole watch-item |
| INFRA-05 holiday data | LOW | Needs sourcing from CBDT/CBIC publications before seed migration |

### Open Questions

1. "All Clients" mode RLS strategy — single-role + dual-policy (recommended) vs. role-swap (cleaner but ops-heavier). Recommendation: Pattern A for Phase 9.
2. Should `notice_activity` be append-only? CONTEXT silent. Recommendation: mutable for Phase 9 (it's user-facing conversation, not regulatory record); confirm during plan-check.
3. `compliance_role` storage — Postgres ENUM vs `String(20)` + Python Enum? Recommendation: `String(20)` for consistency with v1.0 `users.role`.
4. Client switcher — URL-state vs Zustand-only? Recommendation: hybrid (URL for detail pages, Zustand for list/dashboard).

### Ready for Planning

Research complete. Planner can now create PLAN.md with confidence in: (1) stack choices (registry-verified versions), (2) architecture patterns (primary-source backing), (3) test architecture (CLIENT-04, AUDIT-01, RBAC parametrized matrix), and (4) the Wave 0 test infrastructure that must precede business logic. The four open questions are non-blocking — they have recommendations and can be confirmed during plan-check.
