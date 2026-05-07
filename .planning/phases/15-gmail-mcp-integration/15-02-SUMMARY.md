---
phase: 15-gmail-mcp-integration
plan: 02
subsystem: database
tags: [alembic, postgres, sqlalchemy, pydantic, rls, fernet, gmail, supabase]

requires:
  - phase: 09-compliance-foundation
    provides: app_runtime DB role, RLS policy pattern (tenant_isolation + cross_client_view), is_cross_client_eligible() SECURITY DEFINER helper, audit immutability triggers
  - phase: 11-alerts-and-calendar
    provides: VALID_ALERT_TYPES tuple (extended here with bill_t3/bill_t1/bill_overdue), Phase 11 alert pipeline slot
  - phase: 14-portal-integration
    provides: PortalFetchLog three-state status pattern (mirrored by GmailFetchLog)
  - phase: 15-gmail-mcp-integration
    provides: Plan 01 RED-state stubs that gate Plan 02 schema-level facts (test_filter_rules priority column, test_scanner_dedup composite UNIQUE, test_fetch_log three-state CHECK, test_bill_recurrence partial unique index)

provides:
  - Alembic migration 0025 creating 5 new tables (gmail_credentials, gmail_filter_rules, gmail_message_log, gmail_fetch_log, bills) with RLS enabled+forced and tenant_isolation + cross_client_view policies
  - documents.source_email_id BIGINT FK to gmail_message_log.id (nullable, ON DELETE SET NULL) for Gmail attachment provenance
  - 5 ORM models under backend/app/email/models/ matching migration column types exactly
  - 4 Pydantic schema modules (credential, filter_rule, bill, fetch_log) with Literal-validated enums (RouteTo, PaymentMethod, BillerCategory)
  - email_integration:use permission registered + granted to compliance_head/ca_consultant/cfo/staff (D-05 gate for OAuth + MCP tool calls)
  - VALID_ALERT_TYPES tuple extended with bill_t3, bill_t1, bill_overdue (BILL-04 prep for Phase 11 alert pipeline)
  - Plan 01 RED-state stubs flipped to GREEN for 4 schema-level facts: priority column (open Q #5), composite UNIQUE on message_log dedup, three-state CHECK on fetch_log, partial unique index ux_bills_recurrence_key

affects: [15-03-services, 15-04-mcp-tools, 15-05-routers, 15-06-frontend, 15-07-smoke]

tech-stack:
  added: []  # Plan 01 already added fastmcp + google-api-python-client + google-auth-oauthlib + pytest-asyncio. Plan 02 is pure schema/ORM.
  patterns:
    - "Migration revision id naming: 4-digit prefix + descriptive slug (matches existing convention 0017_db_roles, 0021_phase11_alert_tables, 0024_supabase_security_advisor_fixes); plan literal '0025' would have broken convention"
    - "DO $$ IF EXISTS $$ wrapper around app_runtime grants/policies (mirrors migration 0024) — migration runs cleanly on fresh CI Postgres without Phase 9 role chain AND on Supabase production"
    - "RLS policy split by scoping shape: client-id-scoped tables (gmail_credentials, bills) use direct USING/WITH CHECK on client_id; credential-scoped tables (gmail_filter_rules, gmail_message_log, gmail_fetch_log) use credential_id IN (SELECT id FROM gmail_credentials WHERE client_id = ...) subquery"
    - "Plan 01 stub flip pattern: schema-level facts (column existence, constraint presence, index DDL) flip to GREEN at Plan 02; service-level + router-level behavioral assertions remain skipped for Plans 03-05 to land"
    - "Pydantic Literal types mirror migration CHECK constraints exactly (RouteTo, PaymentMethod, BillerCategory, RecurrencePeriod) — single source of truth, type-safe DB-API boundary"
    - "Bill hybrid model encoding (D-19): source_document_id NULLABLE (text-only bills have no PDF), source_email_id always set for provenance — captured cleanly via two independent FKs"

key-files:
  created:
    - backend/alembic/versions/0025_phase15_gmail_mcp.py
    - backend/app/email/__init__.py
    - backend/app/email/models/__init__.py
    - backend/app/email/models/credential.py
    - backend/app/email/models/filter_rule.py
    - backend/app/email/models/fetch_log.py
    - backend/app/email/models/message_log.py
    - backend/app/email/models/bill.py
    - backend/app/email/schemas/__init__.py
    - backend/app/email/schemas/credential.py
    - backend/app/email/schemas/filter_rule.py
    - backend/app/email/schemas/bill.py
    - backend/app/email/schemas/fetch_log.py
  modified:
    - backend/app/models/document.py (add source_email_id BigInteger column + relationship)
    - backend/app/models/__init__.py (register email models so SQLAlchemy resolves Document.source_email)
    - backend/app/compliance/services/permission_registry.py (add EMAIL_INTEGRATION_USE; grant to 4 roles)
    - backend/app/compliance/models/alert.py (extend VALID_ALERT_TYPES with bill_t3, bill_t1, bill_overdue)
    - backend/tests/compliance/email/test_filter_rules.py (flip priority column stub to assertion)
    - backend/tests/compliance/email/test_scanner_dedup.py (flip composite UNIQUE stub to assertion)
    - backend/tests/compliance/email/test_fetch_log.py (flip three-state CHECK stub to assertion)
    - backend/tests/compliance/email/test_bill_recurrence.py (flip partial unique index stub to assertion)

key-decisions:
  - "Migration revision id is '0025_phase15_gmail_mcp' (descriptive slug suffix), not the plan-literal '0025' — matches existing convention in 0024_supabase_security_advisor_fixes / 0023_phase13_search_vector_on_notices / 0021_phase11_alert_tables. Plan literal would have broken the chain visually."
  - "RLS policies on credential-scoped tables (filter_rules, message_log, fetch_log) use credential_id IN (SELECT id FROM gmail_credentials WHERE client_id = NULLIF(current_setting('app.current_client_id'), '')::int) subquery — no client_id column on these tables, but tenant isolation still enforced via the scope-up join."
  - "Bill.children + Bill.parent both use foreign_keys=[parent_bill_id] explicitly to disambiguate the self-FK relationship from the source_document_id / source_email_id FKs (SQLAlchemy could not infer)."
  - "Pydantic literal types (RouteTo, PaymentMethod, BillerCategory, RecurrencePeriod) defined at module top-level for re-use; matched exactly against migration CHECK constraints for single-source-of-truth on enum values."
  - "Stub-flip discipline: only the 4 SCHEMA-level Plan 01 stubs flip to GREEN at Plan 02 (priority column, composite UNIQUE, three-state CHECK, partial unique index). The other 37 stubs that test SERVICE/ROUTER behavior remain skipped for Plan 03-05 to land — keeps RED-state discipline working."

patterns-established:
  - "Migration portability via DO $$ IF EXISTS $$: every app_runtime GRANT, every CREATE POLICY ... TO app_runtime, and every cross_client_view (which references is_cross_client_eligible() from migration 0018) wrapped so the migration executes cleanly on fresh CI Postgres without Phase 9 role chain"
  - "RLS subquery for credential-scoped tables: tenant_isolation joins through gmail_credentials.client_id when the table has no direct client_id column — pattern reusable for any future per-credential-scoped table"
  - "Class constants on ORM models for enum-equivalent string columns (GmailCredential.STATUS_*, GmailFilterRule.ROUTE_*, GmailFetchLog.STATUS_*, Bill.CATEGORIES/PAYMENT_METHODS/RECURRENCE_PERIODS) — services and tests reference these constants instead of bare strings, enabling rename refactors with grep"
  - "Bill hybrid FK pattern: source_document_id (nullable, text-only bills) + source_email_id (always set) — analytics joins can filter on source_document_id IS NULL for the 'no-attachment biller' cohort"

requirements-completed:
  - EMAIL-03  # Encrypted refresh-token storage column (refresh_token_enc BYTEA + Fernet helper from Phase 9 INFRA-06; full encrypt-on-write lands in Plan 03)
  - EMAIL-04  # Filter rules table with priority column (open Q #5 resolved)
  - EMAIL-05  # Document.source_email_id provenance link (column + relationship)
  - EMAIL-07  # GmailFetchLog three-state CHECK constraint
  - EMAIL-08  # GmailMessageLog composite UNIQUE for dedup
  - EMAIL-09  # email_integration:use permission registered (audit log row pattern lands in Plan 04)
  - BILL-01   # bills table schema (biller_name, amount_due, due_date, etc.)
  - BILL-02   # bills.amount_due Numeric(14,2) + due_date Date columns
  - BILL-03   # BillFilterParams Pydantic schema for dashboard buckets
  - BILL-05   # BillMarkPaidRequest Pydantic schema (payment_date/reference/method)
  - BILL-06   # bills.parent_bill_id self-FK + ux_bills_recurrence_key partial unique index

duration: 15m
completed: 2026-05-07
---

# Phase 15 Plan 02: DB Foundations Summary

**Alembic migration 0025 creates 5 Gmail+Bill tables with RLS, ORM models with class-constant enums, Pydantic schemas with Literal types, and adds documents.source_email_id FK + email_integration:use permission + 3 bill alert types.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-07T17:25:37Z
- **Completed:** 2026-05-07T17:40:37Z
- **Tasks:** 3
- **Files created:** 13 (1 migration + 5 model files + 5 schema files + 2 package __init__)
- **Files modified:** 8 (Document ORM + models __init__ + permission_registry + alert.py + 4 stub flips)

## Accomplishments

- Migration 0025 applied cleanly to Supabase (single round-trip downgrade -> upgrade verified)
- All 5 new tables (gmail_credentials, gmail_filter_rules, gmail_message_log, gmail_fetch_log, bills) created with RLS enabled+forced and 2 PERMISSIVE policies each (tenant_isolation + cross_client_view)
- documents.source_email_id BIGINT FK column added with index ix_documents_source_email_id
- Composite UNIQUE on (credential_id, gmail_message_id) enforces D-13 dedup; INSERT duplicate raises IntegrityError
- Partial UNIQUE index ux_bills_recurrence_key WHERE account_number_last4 IS NOT NULL — bills with last4 collide on (client_id, biller_name_normalized, last4); bills without last4 coexist freely (Pitfall 8)
- gmail_filter_rules.priority Integer column resolves open question #5 — lower priority value wins when multiple rules match (service-layer logic lands Plan 03)
- gmail_fetch_log CHECK constraint pins three-state enum (SUCCESS_EMPTY / SUCCESS_WITH_RESULTS / FETCH_FAILED) matching Phase 14 PortalFetchLog pattern
- 5 ORM models with class constants for enum-equivalent string columns; Bill self-FK relationship (parent / children) disambiguated via explicit foreign_keys=[parent_bill_id]
- 4 Pydantic schema modules with Literal types for RouteTo / PaymentMethod / BillerCategory / RecurrencePeriod / BillStatusBucket — single source of truth on enum values, mirrored from migration CHECK constraints
- email_integration:use permission registered + granted to 4 roles (compliance_head / ca_consultant / cfo / staff); denied to 3 roles (auditor / legal_team / finance_team)
- VALID_ALERT_TYPES tuple in alert.py extended with bill_t3 / bill_t1 / bill_overdue without removing or reordering existing types — BILL-04 alert plumbing lands in Plan 03 unchanged
- 4 Plan 01 RED-state stubs flipped to GREEN at the schema level; 37 stubs remain skipped for Plans 03-05 (services + routers + smoke)
- All 19 existing test_permission_registry.py unit tests still pass; round-trip alembic downgrade -1 && alembic upgrade head succeeds

## Task Commits

1. **Task 1: Alembic migration 0025 — 5 tables + documents.source_email_id + RLS** — `8213c0f` (feat)
2. **Task 2: ORM models — credential, filter_rule, fetch_log, message_log, bill** — `ea99e62` (feat)
3. **Task 3: Pydantic schemas + permission_registry edit + alert types extension** — `2e8af1e` (feat)

## Files Created/Modified

### Created (13)

- `backend/alembic/versions/0025_phase15_gmail_mcp.py` — Migration creating 5 tables + documents.source_email_id + RLS policies + GRANTs
- `backend/app/email/__init__.py` — Phase 15 package marker
- `backend/app/email/models/__init__.py` — Re-exports 5 ORM model classes
- `backend/app/email/models/credential.py` — GmailCredential ORM (refresh_token_enc BYTEA, status enum, cadence_minutes 5..1440)
- `backend/app/email/models/filter_rule.py` — GmailFilterRule ORM with priority column (open Q #5)
- `backend/app/email/models/fetch_log.py` — GmailFetchLog ORM (three-state CHECK)
- `backend/app/email/models/message_log.py` — GmailMessageLog ORM (composite UNIQUE dedup)
- `backend/app/email/models/bill.py` — Bill ORM (hybrid model with source_document_id + source_email_id FKs, parent_bill_id self-FK)
- `backend/app/email/schemas/__init__.py` — Re-exports all 11 schemas
- `backend/app/email/schemas/credential.py` — GmailCredentialCreate/Update/Response (refresh_token never in Response)
- `backend/app/email/schemas/filter_rule.py` — GmailFilterRuleCreate/Update/Response with RouteTo Literal
- `backend/app/email/schemas/bill.py` — BillResponse/MarkPaidRequest/FilterParams with PaymentMethod + BillerCategory Literals
- `backend/app/email/schemas/fetch_log.py` — GmailFetchLogResponse

### Modified (8)

- `backend/app/models/document.py` — Add `BigInteger` import, source_email_id Column + source_email relationship
- `backend/app/models/__init__.py` — Register 5 email models so SQLAlchemy resolves Document.source_email
- `backend/app/compliance/services/permission_registry.py` — Add EMAIL_INTEGRATION_USE permission; grant to 4 roles
- `backend/app/compliance/models/alert.py` — Extend VALID_ALERT_TYPES with bill_t3 / bill_t1 / bill_overdue
- `backend/tests/compliance/email/test_filter_rules.py` — Flip priority column stub to schema-level assertion
- `backend/tests/compliance/email/test_scanner_dedup.py` — Flip composite UNIQUE stub to schema-level assertion
- `backend/tests/compliance/email/test_fetch_log.py` — Flip three-state CHECK stub to constraint-text assertion
- `backend/tests/compliance/email/test_bill_recurrence.py` — Flip partial unique index stub to pg_indexes-query assertion

## Decisions Made

- **Migration revision id `0025_phase15_gmail_mcp`** (descriptive slug) instead of plan literal `0025`. Reason: matches the existing project convention in 0024_supabase_security_advisor_fixes / 0023_phase13_search_vector_on_notices / 0021_phase11_alert_tables. The literal `revision = "0025"` would have broken the visual chain. `down_revision` had to follow the same convention (`"0024_supabase_security_advisor_fixes"` not `"0024"`) for alembic to find the parent migration. The grep acceptance criterion would have failed on the bare `"0025"` form, but the migration's behavior is identical and the convention compliance is the right trade-off.

- **RLS subquery pattern for credential-scoped tables.** gmail_filter_rules / gmail_message_log / gmail_fetch_log have no client_id column — they reference gmail_credentials.id via credential_id FK. The tenant_isolation policy filters via `credential_id IN (SELECT id FROM gmail_credentials WHERE client_id = ...)` subquery. Equivalent isolation guarantee, no schema bloat. The cross_client_view policy uses is_cross_client_eligible() (Phase 9 migration 0018 SECURITY DEFINER helper) to avoid recursion through the membership table.

- **Bill.children relationship needs explicit foreign_keys=[parent_bill_id].** Without it, SQLAlchemy raises AmbiguousForeignKeysError because Bill has 3 FKs (parent_bill_id, source_document_id, source_email_id). The plan's snippet only specified foreign_keys on `parent` (the side with remote_side); children needed it too.

- **Stub-flip granularity.** Plan acceptance criteria asked specifically for the priority-column test to flip GREEN. I flipped 4 stubs total — every Plan 01 stub whose assertion is purely schema-level (column exists, constraint name present, partial index DDL contains expected predicate). The other 37 stubs assert service-level or router-level behavior (e.g., `lower-priority rule wins when two match`, `2x FETCH_FAILED triggers alert`) which Plan 03+ implements; flipping them prematurely would have created false GREEN tests. Documented in the test file diffs (kept the original module docstring comments referencing the deferred work).

- **DO $$ IF EXISTS $$ portability wrapper.** Mirrors migration 0024's pattern. Every CREATE POLICY ... TO app_runtime is wrapped in a DO block that checks `pg_roles WHERE rolname = 'app_runtime'`. Every cross_client_view also checks for the existence of `is_cross_client_eligible()` SECURITY DEFINER function. The migration runs identically on Supabase production (where app_runtime + the helper exist) and on fresh CI Postgres without the Phase 9 chain (where they don't — the policy creation is silently skipped). Defense in depth: the migration is also additive only (no DROP / ALTER on existing tables) so failure on a fresh DB does not corrupt anything.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Installed pytest-asyncio in the running container**

- **Found during:** Task 2 verification
- **Issue:** Plan 01 SUMMARY noted: "pytest-asyncio is in requirements.txt but not yet installed in the local venv. Plan 02 pip install -r requirements.txt resolves it." Without it, the async test `test_in_memory_client_invokes_gmail_search` failed with `async def functions are not natively supported` instead of cleanly skipping.
- **Fix:** `docker compose exec backend pip install pytest-asyncio` (resolved to pytest-asyncio==1.3.0). Already in requirements.txt — this only refreshed the running container's installed packages.
- **Files modified:** None (in-container installation only; requirements.txt already lists it from Plan 01)
- **Verification:** `docker compose exec backend pytest tests/compliance/email/` returns `4 passed, 37 skipped, 0 failed` (vs. previous `1 failed`).
- **Committed in:** N/A (no source change; just an environment refresh per Plan 01's documented handoff)

**2. [Rule 3 — Blocking] Migration revision id naming convention**

- **Found during:** Task 1 (writing the migration)
- **Issue:** Plan acceptance criterion specified `grep -c '^revision = "0025"$' ... returns 1` and `grep -c '^down_revision = "0024"$' ... returns 1`. But the existing migration chain uses descriptive slug suffixes (`0024_supabase_security_advisor_fixes`, `0023_phase13_search_vector_on_notices`, etc.). Using the bare `"0025"` form would have:
  - Made the new migration visually inconsistent with the chain
  - Required setting `down_revision = "0024"` (bare), but the actual current head is `"0024_supabase_security_advisor_fixes"` — alembic would fail to find the parent
- **Fix:** Used `revision = "0025_phase15_gmail_mcp"` and `down_revision = "0024_supabase_security_advisor_fixes"`. The migration applies cleanly. Acceptance grep `^revision = "0025"$` does not match (returns 0) but the more behavior-relevant `alembic upgrade head` succeeds.
- **Files modified:** `backend/alembic/versions/0025_phase15_gmail_mcp.py`
- **Verification:** `alembic upgrade head` succeeds; round-trip downgrade -> upgrade succeeds; `alembic current` shows `0025_phase15_gmail_mcp (head)`.
- **Committed in:** `8213c0f` (Task 1 commit)

**3. [Rule 2 — Missing Critical] Bill.children relationship needs explicit foreign_keys**

- **Found during:** Task 2 (mapper compile verification)
- **Issue:** Plan's snippet specified `foreign_keys=[parent_bill_id]` only on the `parent` relationship. Without it on `children`, SQLAlchemy raises `AmbiguousForeignKeysError: Could not determine join condition between parent/child tables on relationship Bill.children — there are multiple foreign key paths linking the tables` because Bill has 3 FKs (parent_bill_id, source_document_id, source_email_id).
- **Fix:** Added `foreign_keys=[parent_bill_id]` to the `children` relationship. Mapper compiles cleanly.
- **Files modified:** `backend/app/email/models/bill.py:155-158`
- **Verification:** `from sqlalchemy.orm import configure_mappers; configure_mappers()` returns without error. `Bill.parent` and `Bill.children` both resolve.
- **Committed in:** `ea99e62` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking environment, 1 blocking convention, 1 missing critical functionality)
**Impact on plan:** All three were correctness/stability fixes that did not change scope. The convention rename trades a literal grep-acceptance-failure for migration-chain consistency that any future planner will appreciate.

## Issues Encountered

- **Pre-existing infra issue:** `tests/test_compliance_endpoints.py::test_role_permission_matrix` 84-case parametrized test reports `91 passed, 91 errors` due to Supabase pooler refusing `SET ROLE app_runtime` with `permission denied to set role "app_runtime"`. Verified via `git stash` that the errors exist BEFORE my changes — not caused by Plan 02. Out of scope per scope-boundary rule. Logged for future investigation; the plan-relevant unit-level `test_permission_registry.py` 19 tests all GREEN.

- **Pytest config warning:** `PytestConfigWarning: Unknown config option: asyncio_mode` persists; pytest-asyncio is now installed but pytest itself doesn't appear to be reading the config option from `pyproject.toml`. Tests still run correctly (auto-mode works in-process). Non-blocking, leaves a single warning per run.

## User Setup Required

None — no external service configuration in this plan. Plans 03-04 will require Google OAuth client setup in Google Cloud Console (deferred to that wave).

## Next Phase Readiness

- **Plan 03 (Wave 2 — Services)** can immediately import every model + schema needed: `from app.email.models import GmailCredential, GmailFilterRule, GmailFetchLog, GmailMessageLog, Bill` resolves; `from app.email.schemas import GmailCredentialCreate, BillMarkPaidRequest, ...` resolves. The 8 service modules referenced in Plan 03 (oauth_service, credential_vault, classifier, bill_extractor, scanner_service, bill_service, ingestion_service, lifespan_service) all have their persistence layer ready.

- **Plan 04 (Wave 3 — MCP tools)** has the `email_integration:use` permission gate ready (`require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)` works). The 6 MCP tools can call into services and persist GmailMessageLog rows with composite-UNIQUE dedup for free.

- **Plan 05 (Wave 4 — Routers)** has Pydantic schemas with full Literal validation — POST /email/credentials, POST /email/filter-rules, GET /bills, POST /bills/{id}/mark-paid all just bind body to the schema and let Pydantic raise 422 on invalid input.

- **Plan 06 (Wave 5 — Frontend)** has BillFilterParams.status buckets (upcoming/due_soon/overdue/paid) defined as a Literal; the dashboard chip set matches exactly.

- **Plan 07 (Wave 6 — Smoke)** can hit the migration's RLS policies in the multi-tenant smoke; tenant_isolation is enforced when set_config('app.current_client_id') is set, fail-closed when empty (NULLIF guard).

- **Reconciliation contracts locked in DB schema:**
  - Open Q #5 (priority column on filter rules) — column + index exist
  - D-13 (composite UNIQUE for dedup) — uq_gmail_message_log_dedup enforced
  - D-15 (three-state fetch_log) — ck_gmail_fetch_log_status enforced
  - D-19 (hybrid Bill model) — source_document_id nullable, source_email_id available
  - D-22 (max-3 reminders) — reminder_count INT NOT NULL DEFAULT 0 ready
  - D-23 (recurrence dedup with last4) — ux_bills_recurrence_key partial unique
  - BILL-04 alert types — bill_t3 / bill_t1 / bill_overdue in VALID_ALERT_TYPES

---

*Phase: 15-gmail-mcp-integration*
*Plan: 02 — DB Foundations (Wave 1)*
*Completed: 2026-05-07*

## Self-Check: PASSED

All 13 created files exist on disk. All 3 task commits exist in git history (`8213c0f`, `ea99e62`, `2e8af1e`). 4 modified files carry the required additions (Document.source_email_id, models __init__ registration, EMAIL_INTEGRATION_USE permission, VALID_ALERT_TYPES extension). `docker compose exec backend pytest tests/compliance/email/ tests/test_permission_registry.py` returns `23 passed, 37 skipped, 0 failed`. Round-trip `alembic downgrade -1 && alembic upgrade head` succeeds. RLS enabled+forced on all 5 new tables with 2 policies each (verified via pg_class + pg_policies queries on Supabase).
