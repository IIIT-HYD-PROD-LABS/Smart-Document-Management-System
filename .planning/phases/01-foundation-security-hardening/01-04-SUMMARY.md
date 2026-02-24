---
phase: 01-foundation-security-hardening
plan: 04
subsystem: backend-database
tags: [alembic, migrations, database, schema-management, postgresql]

dependency-graph:
  requires: ["01-01", "01-02"]
  provides:
    - "Alembic migration framework fully initialized and configured"
    - "Initial migration capturing users, documents, refresh_tokens schema"
    - "Versioned, reversible database migrations replacing create_all()"
  affects:
    - "All future phases that add/modify database tables"
    - "Phase 2+ schema changes use alembic revision --autogenerate"

tech-stack:
  added: []
  patterns:
    - "Alembic for all database schema management"
    - "env.py imports all models for autogenerate accuracy"
    - "settings.DATABASE_URL as single source of truth for DB connection"

key-files:
  created:
    - "backend/alembic.ini"
    - "backend/alembic/env.py"
    - "backend/alembic/script.py.mako"
    - "backend/alembic/README"
    - "backend/alembic/versions/097ce00eb065_initial_schema_users_documents_refresh_.py"
  modified:
    - "backend/app/main.py"

decisions:
  - id: "01-04-01"
    decision: "Manual migration instead of autogenerate due to no live DB"
    rationale: "Database not running locally; wrote migration by hand matching SQLAlchemy models exactly"
  - id: "01-04-02"
    decision: "Dummy sqlalchemy.url in alembic.ini overridden by env.py"
    rationale: "Single source of truth for DATABASE_URL via app.config.settings"

metrics:
  duration: "8min"
  completed: "2026-02-25"
---

# Phase 1 Plan 4: Alembic Migration Framework Summary

**Alembic initialized with env.py importing all models, initial migration for users/documents/refresh_tokens, and create_all() removed from main.py startup.**

## What Was Done

### Task 1: Initialize Alembic and configure env.py with model imports
- Ran `alembic init alembic` in backend/ to scaffold Alembic structure
- Configured `alembic.ini` with `script_location = alembic` and dummy sqlalchemy.url
- Replaced auto-generated `env.py` with custom version that:
  - Imports `settings.DATABASE_URL` from app.config as the connection URL
  - Imports `Base.metadata` from app.database as the target metadata
  - Imports all three models (User, Document, RefreshToken) with noqa annotations
  - Supports both offline (SQL generation) and online (direct execution) modes
- Left `script.py.mako` as the default template

**Commit:** `54fb990` -- feat(01-04): initialize Alembic and configure env.py with model imports

### Task 2: Generate initial migration and remove create_all() from main.py
- Created initial migration `097ce00eb065` capturing complete schema:
  - **users** table: id, email, username, hashed_password, full_name, is_active, created_at, updated_at with unique indexes on email and username
  - **documents** table: id, user_id (FK to users with CASCADE), filename, original_filename, file_type, file_size, file_path, s3_url, category (enum), confidence_score, extracted_text, status (enum), created_at, updated_at with composite and individual indexes
  - **refresh_tokens** table: id, token (unique), user_id (FK to users with CASCADE), expires_at, is_revoked, created_at, revoked_at, replaced_by with indexes on user_id and expires_at
- Migration written manually (autogenerate failed due to no live database connection)
- Includes complete `downgrade()` that drops all indexes, tables, and enums in correct order
- Removed `Base.metadata.create_all(bind=engine)` from main.py
- Removed unused `engine` and `Base` imports from main.py
- Added migration setup instruction comments in main.py

**Commit:** `e33f19e` -- feat(01-04): generate initial migration and remove create_all from main.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Manual migration due to database connection failure**
- **Found during:** Task 2
- **Issue:** `alembic revision --autogenerate` failed because PostgreSQL was not running locally (password authentication failed)
- **Fix:** Created migration manually using `alembic revision -m` and wrote upgrade/downgrade functions by hand, matching all SQLAlchemy model definitions exactly
- **Files modified:** `backend/alembic/versions/097ce00eb065_initial_schema_users_documents_refresh_.py`
- **Commit:** `e33f19e`

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| 01-04-01 | Manual migration instead of autogenerate | Database not running locally; wrote migration by hand matching SQLAlchemy models exactly |
| 01-04-02 | Dummy sqlalchemy.url in alembic.ini overridden by env.py | Single source of truth for DATABASE_URL via app.config.settings |

## Verification Results

| Check | Status |
|-------|--------|
| alembic.ini has script_location = alembic | PASS |
| env.py imports User, Document, RefreshToken | PASS |
| env.py uses settings.DATABASE_URL | PASS |
| versions/ contains migration file | PASS |
| Migration creates users, documents, refresh_tokens | PASS |
| main.py does NOT call create_all | PASS |
| alembic heads shows initial revision | PASS |
| autogenerate empty test (requires DB) | SKIPPED |

## Next Phase Readiness

Phase 1 (Foundation & Security Hardening) is now **complete** with all 4 plans executed:
- 01-01: Environment & config hardening
- 01-02: JWT auth with refresh token rotation
- 01-03: Rate limiting, security headers, structured logging
- 01-04: Alembic migration framework

**Important for future phases:**
- Any new model must be imported in `backend/alembic/env.py` for autogenerate to detect it
- After adding a model, run `alembic revision --autogenerate -m "description"` to generate migration
- First deployment against existing database must run `alembic stamp head` before `alembic upgrade head`
