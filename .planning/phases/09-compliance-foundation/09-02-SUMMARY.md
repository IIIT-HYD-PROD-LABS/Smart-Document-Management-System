---
phase: 09-compliance-foundation
plan: 02
subsystem: database
tags: [postgres, alembic, rls, force-rls, audit-immutability, triggers, db-roles, fernet, structlog, rbac, state-machine, cryptography]

# Dependency graph
requires:
  - phase: 09-01
    provides: "Wave 0 RED-state test infrastructure (test_audit_immutability, test_rls_isolation, test_indian_validators, test_pii_encryption, test_log_redaction, test_permission_registry, test_notice_state_machine, test_regulatory_calendar) and 6 conftest fixtures (db_as_app_runtime, app_runtime_engine, client_a, client_b, audit_log_row, auditor_membership, client_with_membership)"
provides:
  - "5 Alembic migrations 0013-0017 forming the Phase 9 data spine: 8 compliance tables + audit hardening + RLS policies + DB roles + 2026 calendar seed"
  - "PostgreSQL roles app_migrator (CREATEDB owner) and app_runtime (RLS-subject FastAPI process role)"
  - "audit_logs immutability: trigger raising EXCEPTION on UPDATE/DELETE + REVOKE on app_runtime + clock_timestamp() default"
  - "FORCE ROW LEVEL SECURITY with tenant_isolation + cross_client_view policies on 6 client-scoped tables"
  - "12-row 2026 regulatory calendar seed (6 filing deadlines + 6 holidays)"
  - "app.compliance package: indian_validators, pii_encryption (Fernet), log_redaction (structlog processor)"
  - "permission_registry: ComplianceRole×CompliancePermission 7×12 matrix with has_permission()"
  - "notice_state_machine: NoticeStatus enum + ALLOWED_TRANSITIONS dict + validate_transition()"
  - "Local Postgres docker-compose service (db) for Phase 9 RLS testing — Supabase pooler in transaction mode cannot support FORCE RLS / CREATE ROLE / trigger DDL reliably"
affects: [09-03, 09-04, 09-05, 09-06, 09-07]

# Tech tracking
tech-stack:
  added:
    - "postgres:16-alpine docker service (local DB)"
  patterns:
    - "Migration chain re-ordered: 0012→0013→0017→0014→0015→0016 (head=0016) — CREATE POLICY ... TO role requires role to exist; PG has no IF NOT EXISTS for the role reference. Plan-specified order would fail on upgrade."
    - "Idempotent CREATE ROLE via DO block with EXISTS check on pg_roles"
    - "Idempotent trigger via DROP TRIGGER IF EXISTS before CREATE TRIGGER"
    - "JSONB GIN index using jsonb_path_ops (half size, 2-3x faster for @> containment)"
    - "alembic_version column auto-widened to varchar(64) in env.py to accept descriptive 33-char revision ids"
    - "Fernet cipher cache via lru_cache on (active_key, old_key) tuple — monkeypatch.setenv naturally invalidates without explicit reset_cipher_cache()"
    - "Two-policy pattern (Pattern A from 09-RESEARCH): tenant_isolation (RESTRICTIVE per-tenant) + cross_client_view (PERMISSIVE for compliance_head/ca_consultant/cfo with cross_client_mode setting)"

key-files:
  created:
    - "backend/alembic/versions/0013_compliance_foundation_schema.py — 8 compliance tables + JSONB GIN index + documents.notice_id FK"
    - "backend/alembic/versions/0014_audit_log_immutability.py — trigger + REVOKE + clock_timestamp default"
    - "backend/alembic/versions/0015_compliance_rls_policies.py — FORCE RLS + tenant_isolation + cross_client_view on 6 tables"
    - "backend/alembic/versions/0016_regulatory_calendar_seed.py — 12 rows of 2026 deadlines + holidays"
    - "backend/alembic/versions/0017_db_roles.py — CREATE ROLE app_migrator + app_runtime"
    - "backend/app/compliance/__init__.py — package init"
    - "backend/app/compliance/utils/__init__.py — utils package init"
    - "backend/app/compliance/utils/indian_validators.py — GSTIN/PAN/CIN/DIN regex + validate_gstin/validate_pan_in_gstin/validate_notice_number"
    - "backend/app/compliance/utils/pii_encryption.py — Fernet/MultiFernet encrypt_field/decrypt_field/reset_cipher_cache"
    - "backend/app/compliance/utils/log_redaction.py — redact_pii structlog processor + PII_FIELDS"
    - "backend/app/compliance/services/__init__.py — services package init"
    - "backend/app/compliance/services/permission_registry.py — ComplianceRole + CompliancePermission + ROLE_PERMISSIONS + has_permission"
    - "backend/app/compliance/services/notice_state_machine.py — NoticeStatus + ALLOWED_TRANSITIONS + validate_transition + InvalidTransitionError"
  modified:
    - "backend/app/config.py — added FERNET_KEY, FERNET_KEY_OLD, APP_RUNTIME_PASSWORD, APP_MIGRATOR_PASSWORD, DATABASE_URL_RUNTIME, DATABASE_URL_MIGRATOR settings"
    - "backend/.env.example — appended Phase 9 section with Fernet key + role password + connection URL templates"
    - "docker-compose.yml — added local Postgres `db` service + postgres_data volume + backend depends_on db"
    - "backend/app/database.py — skip sslmode=require for local docker hostname `db`"
    - "backend/alembic/env.py — auto-widen alembic_version column to varchar(64) before migrations run"
    - ".env — switched DATABASE_URL to local docker postgres; added APP_RUNTIME_PASSWORD, DATABASE_URL_RUNTIME (per Supabase auto-pause memory)"
    - ".planning/phases/09-compliance-foundation/09-VALIDATION.md — flipped 7 of 8 Plan 02 task statuses to ✅ green; T8 marked ⚠️ partial (needs Plan 03 ORM model)"

key-decisions:
  - "Local Postgres docker service required: Supabase pooler in transaction mode does not reliably support session-state-dependent operations (SET LOCAL ROLE, FORCE RLS testing, trigger DDL). 09-RESEARCH already assumed `Docker postgres image (already in compose)` — added it as a Rule 3 deviation"
  - "Migration chain re-ordered 0012→0013→0017→0014→0015→0016 (head=0016): plan order 0014/0015 referenced app_runtime which is created in 0017. PostgreSQL CREATE POLICY ... TO role has no IF NOT EXISTS escape hatch for the role reference; therefore 0017 must run BEFORE 0014/0015"
  - "alembic_version column widened to varchar(64) via idempotent ALTER TABLE in env.py: revision id `0013_compliance_foundation_schema` is 33 chars; default is varchar(32)"
  - "Fernet cache strategy: outer _get_cipher() reads env each call and delegates to lru_cached _build_cipher_for_key(active_key, old_key). monkeypatch.setenv produces a different cache key, so test_decrypt_with_wrong_key_raises works without explicit cache resets"
  - "compliance_regulatory_calendar created in 0013 (not 0016): plan listed it as one of 8 tables in 0013; 0016 only seeds data into the existing table (DELETE FROM ... WHERE year=2026 in downgrade)"
  - "Phase 9 FORCE RLS uses USING + WITH CHECK on tenant_isolation policies (write isolation), USING-only on cross_client_view (read-only)"
  - "Notice activity/tags policies JOIN through compliance_notices.client_id since they have no direct client_id column — pattern matches 09-RESEARCH guidance for indirect tenant filtering"

patterns-established:
  - "DB role pre-requisite migration: always run CREATE ROLE BEFORE migrations that REVOKE/GRANT/CREATE POLICY referencing that role. PostgreSQL fails-loudly on missing roles with no IF NOT EXISTS clause for role references in DDL."
  - "Idempotent migration upgrade: use DROP TRIGGER IF EXISTS, DO blocks with EXISTS check on pg_roles, DROP INDEX IF EXISTS — every Phase 9 migration is safely re-runnable."
  - "Two-policy access pattern: per-tenant RESTRICTIVE policy (tenant_isolation) + role-gated PERMISSIVE policy (cross_client_view) compose at the planner level so the cross-client check is a single COALESCE-able OR rather than two separate code paths."

requirements-completed: [LIFE-03, LIFE-04, AUDIT-01, AUDIT-02, RBAC-01, RBAC-02, RBAC-03, RBAC-04, RBAC-05, RBAC-06, CLIENT-04, CLIENT-06, INFRA-05, INFRA-06, INFRA-07]

# Metrics
duration: 21min
completed: 2026-04-27
---

# Phase 9 Plan 2: Wave 1 — Compliance Foundation Schema Summary

**5 Alembic migrations (0013-0017) building 8 compliance tables, FORCE RLS on 6 client-scoped tables, audit_logs trigger+REVOKE immutability, app_runtime+app_migrator DB roles, 2026 calendar seed; 8 utility/service modules implementing GSTIN/PAN regex, Fernet PII encryption, structlog redaction, 7-role 12-permission RBAC registry, and notice state machine — all 22 affected pytest tests GREEN**

## Performance

- **Duration:** ~21 minutes
- **Started:** 2026-04-27T08:06:51Z
- **Completed:** 2026-04-27T08:28:05Z
- **Tasks:** 8 / 8
- **Commits:** 9 (8 task commits + 1 setup chore commit; final docs commit follows)
- **Files created:** 13 (5 migrations + 8 Python modules incl. 3 __init__.py)
- **Files modified:** 7 (config.py, .env.example, docker-compose.yml, database.py, env.py, .env, VALIDATION.md)

## Accomplishments

- **Wave 0 → Wave 1 mandate fully met:** all 5 audit immutability merge gate tests turn GREEN (test_update_raises, test_delete_raises, test_app_role_lacks_privilege, test_trigger_present, test_clock_timestamp_default)
- **22/22 affected pytest tests pass:** 5 audit immutability + 6 indian_validators + 2 pii_encryption + 1 log_redaction + 4 permission_registry + 3 notice_state_machine + 1 RLS structural
- **Zero v1.0 regression:** all 100 v1.0 tests still pass (75 admin/auth + 25 documents)
- **Migration chain applies + downgrades cleanly:** `alembic downgrade -3 && alembic upgrade head` completes without errors
- **DB-level enforcement verified:** 6 compliance_* tables show relrowsecurity AND relforcerowsecurity = TRUE in pg_class; audit_logs_immutability trigger present; app_runtime lacks UPDATE/DELETE on audit_logs (verified via information_schema.role_table_grants)
- **Local Postgres docker service operational:** smartdocs-db container healthy, accepting connections; postgres_data volume persists across restarts
- **84-case RBAC matrix sanity test passes:** test_matrix_covers_all_roles_and_permissions confirms ROLE_PERMISSIONS encodes the canonical 7×12 grid

## Task Commits

Each task was committed atomically:

1. **Setup (chore): add local Postgres service** — `70ab86c` (chore)
2. **Task 1: Migration 0017 — DB roles** — `1d7aa48` (feat)
3. **Task 2: Migration 0013 — compliance schema (8 tables)** — `496e9f8` (feat)
4. **Task 3: Migration 0014 — audit_logs immutability** — `a61b463` (feat)
5. **Task 4: Migration 0015 — RLS policies (FORCE + tenant + cross-client)** — `11423ca` (feat)
6. **Task 5: Migration 0016 — calendar seed + re-chain 0017** — `1f3599a` (feat)
7. **Task 6: compliance package + 3 utility modules + config + env** — `cbae234` (feat)
8. **Task 7: permission_registry + notice_state_machine services** — `7a4152b` (feat)
9. **Task 8: Re-chain migrations + widen alembic_version** — `9132d5f` (fix)

**Plan metadata commit:** _to be added by final docs commit_

## Files Created/Modified

### Created (13 files)

**Migrations (5):**
- `backend/alembic/versions/0013_compliance_foundation_schema.py` — 449 lines; 8 tables + documents.notice_id FK + GIN index
- `backend/alembic/versions/0014_audit_log_immutability.py` — 53 lines; trigger + REVOKE + clock_timestamp default
- `backend/alembic/versions/0015_compliance_rls_policies.py` — 227 lines; FORCE RLS + tenant_isolation + cross_client_view on 6 tables
- `backend/alembic/versions/0016_regulatory_calendar_seed.py` — 57 lines; 12-row 2026 seed
- `backend/alembic/versions/0017_db_roles.py` — 66 lines; CREATE ROLE app_migrator + app_runtime

**Compliance package (5 modules + 3 __init__):**
- `backend/app/compliance/__init__.py`
- `backend/app/compliance/utils/__init__.py`
- `backend/app/compliance/utils/indian_validators.py` — GSTIN/PAN/CIN/DIN regex + validate functions
- `backend/app/compliance/utils/pii_encryption.py` — Fernet roundtrip with rotation support
- `backend/app/compliance/utils/log_redaction.py` — structlog processor stripping 9 PII fields
- `backend/app/compliance/services/__init__.py`
- `backend/app/compliance/services/permission_registry.py` — 7-role × 12-permission flat registry
- `backend/app/compliance/services/notice_state_machine.py` — 6-status state machine

### Modified (7 files)

- `backend/app/config.py` — Phase 9 section: FERNET_KEY, FERNET_KEY_OLD, APP_RUNTIME_PASSWORD, APP_MIGRATOR_PASSWORD, DATABASE_URL_RUNTIME, DATABASE_URL_MIGRATOR
- `backend/.env.example` — Phase 9 section with template values + generation instructions
- `docker-compose.yml` — added local `db` service (postgres:16-alpine) + postgres_data volume + backend depends_on db
- `backend/app/database.py` — extended local-host detection to include `@db:` and `@db/` patterns to skip sslmode=require
- `backend/alembic/env.py` — idempotent ALTER TABLE alembic_version to varchar(64) before migrations run
- `.env` — switched DATABASE_URL to local docker postgres; added Phase 9 role passwords and DATABASE_URL_RUNTIME
- `.planning/phases/09-compliance-foundation/09-VALIDATION.md` — flipped Plan 02 row statuses ⬜→✅ (T8 ⚠️ partial)

## Decisions Made

- **Migration chain re-ordering** (deviation Rule 3): final order 0012→0013→0017→0014→0015→0016 with head=0016 because PG CREATE POLICY ... TO role has no IF NOT EXISTS escape hatch; the role MUST exist before 0014 REVOKEs and 0015 CREATE POLICYs reference it
- **Local Postgres in docker-compose** (deviation Rule 3): 09-RESEARCH explicitly assumed `Docker postgres image (already in compose)` as the testing fallback for FORCE RLS scenarios. The Supabase pooler (transaction mode) cannot reliably support `SET LOCAL ROLE`, `set_config`, and trigger DDL needed by the test suite. Local DB is dev/test-only — production keeps using Supabase via DATABASE_URL override
- **alembic_version column widened to varchar(64)** (deviation Rule 3): plan-specified revision id `0013_compliance_foundation_schema` is 33 chars but default column is varchar(32). Plan acceptance criteria require this exact name; widening the column is the only way to satisfy both
- **compliance_regulatory_calendar table created in 0013, not 0016**: plan listed it as one of the 8 tables in Task 2 / migration 0013. 0016 only INSERTs seed data; downgrade DELETEs by year=2026
- **Fernet cache via lru_cache on inner builder** (rather than env-reading wrapper): monkeypatch.setenv produces different cache keys naturally, so test_decrypt_with_wrong_key_raises works without explicit reset_cipher_cache() calls

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Local Postgres `db` docker-compose service added**
- **Found during:** Pre-Task 1 environment probe
- **Issue:** docker-compose.yml had no `db` service — plan's verification commands like `docker compose up -d db` and `docker compose exec db psql -U postgres` cannot work. Project uses Supabase (cloud) via DATABASE_URL pointing to `aws-1-ap-south-1.pooler.supabase.com:6543`. The pooler runs in transaction mode which does not reliably support session-state-dependent operations needed by Phase 9 tests (SET LOCAL ROLE, set_config persistence, FORCE RLS testing). Per memory `project_supabase_config.md`, Supabase project also auto-pauses on inactivity (was paused at start of session — `Tenant or user not found`).
- **Fix:** Added `db` service (postgres:16-alpine) to docker-compose.yml + postgres_data volume + backend depends_on db. Switched `.env` DATABASE_URL to `postgresql://postgres:postgres@db:5432/postgres` for local development; preserved Supabase URL as a comment for prod toggling. Updated `backend/app/database.py` to skip sslmode=require for the local docker hostname `db`.
- **Files modified:** docker-compose.yml, .env, backend/app/database.py
- **Verification:** `docker compose exec backend python -c "from app.database import engine; engine.connect()"` succeeds with local DB; `alembic upgrade head` applies all v1.0 migrations + Phase 9 migrations cleanly; existing v1.0 tests continue to pass (no regression).
- **Committed in:** `70ab86c` (chore setup commit before Task 1)

**2. [Rule 3 — Blocking] Migration chain re-ordered to put 0017 before 0014/0015**
- **Found during:** Task 8 (`alembic upgrade head`)
- **Issue:** Plan-specified chain `0012 → 0013 → 0014 → 0015 → 0016 → 0017` fails because:
  - 0014 `REVOKE UPDATE, DELETE ON audit_logs FROM app_runtime` — fails: role doesn't exist yet
  - 0015 `CREATE POLICY tenant_isolation ON ... FOR ALL TO app_runtime` — fails: role doesn't exist yet
  - PostgreSQL `CREATE POLICY` does NOT have an `IF NOT EXISTS` escape hatch for the role reference (verified via `CREATE POLICY p ON _test FOR ALL TO nonexistent_role` → `ERROR: role "nonexistent_role" does not exist`)
- **Fix:** Re-chain so 0017 (CREATE ROLE) runs immediately after 0013:
  - `0017_db_roles.down_revision`: `0016_regulatory_calendar_seed` → `0013_compliance_foundation_schema`
  - `0014_audit_log_immutability.down_revision`: `0013_compliance_foundation_schema` → `0017_db_roles`
  - Final chain: `0012 → 0013 → 0017 → 0014 → 0015 → 0016` (head = 0016)
- **Files modified:** backend/alembic/versions/0017_db_roles.py, backend/alembic/versions/0014_audit_log_immutability.py
- **Verification:** `alembic upgrade head` applies all 5 migrations cleanly; `alembic downgrade -3 && alembic upgrade head` cycles cleanly; all 22 Phase 9 tests pass.
- **Committed in:** `9132d5f` (Task 8 fix commit)
- **Acceptance impact:** Task 3's acceptance criterion `down_revision == "0013_compliance_foundation_schema"` is no longer met (0014 now points at 0017). Task 5's criterion that 0017 points at 0016 is also broken (0017 now points at 0013). These criteria assumed the plan's broken chain order; the working chain takes precedence per Rule 3 (functional correctness over structural acceptance check).

**3. [Rule 3 — Blocking] alembic_version column widened from varchar(32) to varchar(64)**
- **Found during:** Task 8 (first attempt at `alembic upgrade head`)
- **Issue:** Existing `alembic_version.version_num` is `character varying(32)`. The revision id `0013_compliance_foundation_schema` is 33 characters and the UPDATE statement fails with `psycopg2.errors.StringDataRightTruncation: value too long for type character varying(32)`.
- **Fix:** Two-pronged:
  - Direct ALTER TABLE on the running DB (`ALTER TABLE alembic_version ALTER COLUMN version_num TYPE varchar(64)`)
  - Idempotent ALTER in `backend/alembic/env.py` `run_migrations_online()` so future deployments auto-widen the column on first migration run.
- **Files modified:** backend/alembic/env.py
- **Verification:** Migrations apply on the local DB; future test/CI databases will auto-widen on first `alembic upgrade head`.
- **Committed in:** `9132d5f` (Task 8 fix commit)

**4. [Rule 2 — Missing Critical] DROP INDEX IF EXISTS for GIN index in 0013 downgrade**
- **Found during:** Task 2 author review
- **Issue:** Plan instructed using raw `op.execute("CREATE INDEX ... USING gin")` for the JSONB GIN index. Without an explicit `DROP INDEX IF EXISTS` in the downgrade, downgrade after a partial upgrade could fail.
- **Fix:** Added `op.execute("DROP INDEX IF EXISTS ix_clients_config_overrides_gin;")` to 0013's downgrade.
- **Files modified:** backend/alembic/versions/0013_compliance_foundation_schema.py
- **Verification:** `alembic downgrade -3 && alembic upgrade head` cycles cleanly.
- **Committed in:** `496e9f8` (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (3 Rule 3 blocking, 1 Rule 2 missing critical)
**Impact on plan:** All deviations were structurally necessary to make migrations actually run. The plan's intent — security primitives that turn merge gates GREEN — is fully met. Rule-3 deviations were forced by the gap between plan author's environmental assumptions (local docker postgres available, alembic_version width sufficient) and reality (Supabase-only compose, default varchar(32)). The migration chain re-order is the most consequential deviation: head is `0016_regulatory_calendar_seed` rather than `0017_db_roles`. Plan 09-04's tenant middleware should target current head dynamically rather than hardcoding `0017_db_roles`.

## Issues Encountered

- **Supabase project paused at session start:** `Tenant or user not found` error when connecting to Supabase pooler. Per memory `project_supabase_config.md` this most often means the free-tier Supabase project auto-paused. Did not unpause (no internet DNS access on host); pivoted to local docker postgres which was already a planned dependency per 09-RESEARCH line 1179.
- **PG_TRGM extension installed by 0003 in v1.0:** required CREATE EXTENSION pg_trgm which the local postgres:16-alpine image supports. No issue.
- **Pytest mark warning:** `pytest.mark.integration` is unregistered (PytestUnknownMarkWarning). Documented in 09-01 SUMMARY as "in scope for Plan 02" but only adds a warning, not a failure. Marker registration deferred to Plan 03 conftest update.

## User Setup Required

**External services NOT required** — Phase 9 Plan 02 is fully self-contained behind the docker-compose stack.

For developers continuing this work locally:
1. Generate a Fernet key once: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and add to `.env` as `FERNET_KEY=...`
2. Pull the latest postgres:16-alpine image: `docker compose pull db`
3. Recreate the backend container to pick up new env: `docker compose up -d --force-recreate backend`

For production deployment (Supabase):
- Switch `DATABASE_URL` back to the Supabase pooler URL in `.env` (preserved as comment)
- Run `alembic upgrade head` against Supabase (the env.py auto-widens alembic_version)
- Note: Supabase RLS testing limitations apply — production deploys should use a dedicated postgres instance for full RLS / role / trigger testing in CI

## Next Phase Readiness

**Plan 09-03 unblocked** — has all the foundational schema, validators, registry, and state machine it needs:
- Build `app.compliance.models.client.Client`, `app.compliance.models.notice.ComplianceNotice`, etc. SQLAlchemy ORM models targeting the tables created in 0013
- Build `app.compliance.models.regulatory_calendar.RegulatoryCalendar` so test_regulatory_calendar.py turns GREEN
- Build `app.compliance.models.membership.ClientMembership` so client_a/client_b/auditor_membership/client_with_membership fixtures stop skipping

**Plan 09-04 prerequisites:**
- `app.middleware.tenant_context.set_client_id_middleware` calling `SELECT set_config('app.current_client_id', :cid, true)` per request
- `app.compliance.dependencies.require_compliance_permission(perm)` factory using `has_permission(role, perm)` from this plan
- Engine swap from DATABASE_URL (currently superuser/postgres) to DATABASE_URL_RUNTIME (app_runtime role) so RLS policies actually take effect at runtime

**Wave 1 → Wave 2 handoff complete:**
- All 5 merge-gate tests from Plan 01 turn GREEN (audit immutability fully; RBAC matrix structurally; FORCE RLS structurally)
- 17 Phase 9 unit tests across 7 files all pass
- DB schema is the source of truth for Plans 03+ — they bind ORM models to the 8 existing tables

**Known partial-green tests (will turn GREEN in later plans):**
- `test_rls_isolation.py::test_no_cross_client_leakage` — needs `app.compliance.models.notice.ComplianceNotice` (Plan 09-03)
- `test_rls_isolation.py::test_unset_tenant_returns_empty` — same as above
- `test_rls_isolation.py::test_cross_client_mode_*` — needs ComplianceNotice + ClientMembership models (Plan 09-03) and tenant middleware (Plan 09-04)
- `test_regulatory_calendar.py::test_2026_holidays_seeded` — data IS seeded (12 rows verified in DB) but test imports ORM model that doesn't exist yet (Plan 09-03)
- `test_compliance_endpoints.py::test_role_permission_matrix` — 84 cases skip because they need route-layer integration (Plan 09-05)

## Self-Check: PASSED

- [x] All 13 created files exist:
  - 5 migrations in `backend/alembic/versions/`
  - 8 Python modules in `backend/app/compliance/{utils,services}/` and `__init__.py` files
- [x] All 9 commits exist on main: 70ab86c, 1d7aa48, 496e9f8, a61b463, 11423ca, 1f3599a, cbae234, 7a4152b, 9132d5f
- [x] Migration chain validates: `alembic heads` returns single head `0016_regulatory_calendar_seed`
- [x] All 22 affected pytest tests pass (audit immutability 5 + indian_validators 6 + pii_encryption 2 + log_redaction 1 + permission_registry 4 + notice_state_machine 3 + RLS structural 1)
- [x] V1.0 regression tests pass: 75 admin/auth + 25 documents = 100 v1.0 tests still GREEN
- [x] DB-level checks pass: 2 roles, 1 trigger, 6 FORCE RLS tables, 12 calendar rows
- [x] Migration cycle clean: `alembic downgrade -3 && alembic upgrade head` succeeds without errors
- [x] No SQL syntax errors: every migration parses via `python3 -c "import ast; ast.parse(...)"`
