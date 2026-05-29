# Opus 4.8 End-to-End Audit and Remediation

**System:** Smart Document Management and Compliance System (TaxSync)
**Date:** 2026-05-29
**Branch / base commit:** feat/mfa-account-lockout @ bdca56e (== origin/main)
**Method:** A super-agent team driven by Opus 4.8. A 17-agent read-only audit (one agent per domain across auth, tenant isolation, compliance notices, response/segregation-of-duties, email ingestion, BYOK AI, ML, alerts, search, documents, DB/migrations, config/secrets, infra/deps, frontend, input validation, and a whole-diff review) with an adversarial verifier per Critical/High finding, followed by an 18-agent fix pass (one agent per non-overlapping file group). Every change was reviewed by hand and gated on a fresh-database backend suite plus ruff, tsc, and the Next.js build.

## 1. Relationship to the 2026-05-26 godmode audit

The working tree carried the godmode audit's uncommitted remediation (about 51 files, migration 0037, and the report at `docs/status/GODMODE-AUDIT-2026-05-26.md`). This 4.8 pass first reproduced that baseline green (609 passed, 0 failed, 32 skipped on a fresh Postgres 15 plus Redis), then validated each prior fix and hunted for issues the prior pass missed. Spot result of the validation: the prior A1 to A4, C1 to C4, R1/R3/R4/R6, S1/S2, SEC1 to SEC5, D1/D2, AI1/AI2/AI3/AI6/AI7, L1/L2/L4, G2/G6 fixes are all correct as applied. Two prior items were found incomplete or wrong and corrected here (G6 initial-scan history id, the M2 test patch target).

## 2. New issues found and fixed (this pass)

Severity reflects the post-verification assessment. The single most consequential finding is that the primary RLS isolation layer is inactive at runtime, which reclassified several "defense in depth" gaps into real cross-tenant IDORs. Those exploitable gaps are now closed at the application layer.

### Tenant isolation (IDOR), authorization
| Area | File | Fix |
|------|------|-----|
| Cross-tenant note write | `compliance/routers/notices.py` add_note | client_id ownership check before `log_activity` (404 on mismatch) |
| Cross-tenant metadata write | `compliance/routers/notices.py` update_notice (PATCH) | cross-client mode refused for writes, client_id always filtered |
| Cross-tenant status oracle | `compliance/routers/notices.py` transition error path | status re-query scoped to client_id |
| Cross-tenant review mutation | `compliance/routers/review_queue.py` assign_review | client_id ownership guard before the unscoped service `db.get` |
| Cross-tenant response access | `compliance/routers/responses.py` (6 query sites) | every `NoticeResponse` query scoped by client_id |
| Approval abort by non-author | `compliance/routers/responses.py` withdraw | author-or-supervisor guard, supervisor override audited |
| Self-approval NULL bypass | `compliance/services/response_service.py` apply_approval | R1.1 made fail-closed: unknown (NULL) author cannot approve |

### Authentication
- MFA enroll and disable now revoke all outstanding refresh tokens (`routers/auth.py`), so a token stolen before enrollment cannot ride past the new MFA gate.

### Crash / denial-of-service (500s)
- `compliance/routers/reports.py`: `window_days` bounded (1 to 3660) to stop an OverflowError 500.
- `compliance/routers/notices.py`: NUL byte in `gstin_or_pan` rejected at the boundary (was a psycopg2 500).
- `compliance/schemas/notice.py`, `schemas/response.py`: tags list capped (50 items, 100 chars each) and `body_markdown` capped (100000 chars).
- `services/llm_service.py`: OpenAI `choices[0]` guarded (no IndexError, no silent degrade).
- `compliance/routers/notices.py` extract_preview: AI auth, rate-limit, and provider errors mapped to 502/429 instead of a generic 500, with no provider response body leaked.
- `main.py`: a 2 MB request-body cap for non-multipart endpoints (uploads exempt).

### Races, correctness
- `tasks/compliance_tasks.py`: escalation read-then-write race closed with a `pg_advisory_xact_lock(notice_id)` (M1); deadline-pressure date computed in IST, not server-local (M7).
- `email/tasks/scanner_task.py`, `email/services/ingestion_service.py`: initial-scan history id now persisted (G6), and the re-scan duplicate-notice regression fixed (already-ingested messages skip the notice-creating side effects).
- `ml/compliance/risk_scorer.py`: a sub-rupee penalty no longer yields a negative contribution that lowered the tier.
- `compliance/calendar/seed.py`: statutory deadlines that fall in January of the next calendar year are stored under the correct year.

### Hardening, hygiene, honesty
- `alembic/versions/0017_db_roles.py`: role passwords escaped before interpolation, neutralizing the f-string injection (the env-with-fallback is retained for CI).
- `middleware/logging.py`, `utils/log_redaction.py`: the log sanitizer now recurses into nested structures.
- `compliance/middleware/tenant_context.py`: the docstring that falsely claimed the listener issues `SET ROLE app_runtime` was corrected (see section 3).
- `tasks/document_tasks.py`: status and error strings no longer clobber `extracted_text` (D6); celery tenant-context note added.
- `.dockerignore`, `.gitignore`: real test PDFs excluded from the Docker build context and from git.
- `tests/test_escalation.py`: M2 patch target corrected to the symbol `escalate()` actually calls.

## 3. Deferred, with rationale (and the RLS activation runbook)

These were deliberately not changed in this pass because they are high blast radius and cannot be validated against the production Supabase from here, or are out of scope. Each is tracked.

**RLS is inactive at runtime (the headline finding).** `app/database.py` connects via `DATABASE_URL` (the `postgres` owner role, which has BYPASSRLS), and `compliance/middleware/tenant_context.py` only calls `set_config(...)`; it never issues `SET ROLE app_runtime`. So the RLS policies on tenant tables are not evaluated in production, and the explicit client_id checks (hardened above) are the only active isolation layer. This pass closed the exploitable application-layer gaps, so tenant isolation is sound today. Activating RLS as true defense in depth requires a coordinated, staged change:
1. Grant the connecting role the ability to assume `app_runtime` (on Supabase: `GRANT app_runtime TO postgres` by the project owner; on Postgres 16+ add `WITH SET TRUE`).
2. Grant `app_runtime` SELECT/INSERT/UPDATE/DELETE on every table and USAGE/SELECT on every sequence (a comprehensive grant migration), since later migrations added tables beyond migration 0017's grant set.
3. Either switch the runtime engine to `DATABASE_URL_RUNTIME` (the `app_runtime` DSN) or make the listener issue `SET ROLE app_runtime` per checkout, with a matching `RESET ROLE` on checkin.
4. Set tenant context in every request and background task, and update the TestClient suite so requests carry tenant context (otherwise RLS fail-closes to zero rows).

**Frontend token storage and CSP.** Access and refresh tokens live in JS-readable cookies (no httpOnly), and the CSP allows `script-src 'unsafe-inline'`, so any XSS is a durable account takeover. The fix is a backend-set httpOnly refresh cookie plus a nonce or hash for the static theme bootstrap script. This is an architectural change that cannot be validated against the live frontend here.

**Lower-severity items left documented:** A5 (forgot-password timing channel) and A6/G7 (OAuth state nonce not single-use); DB3/DB4 ORM-vs-database constraint-name drift and the `NoticeAlertLog` bill-type CHECK mismatch (both need a careful migration); the second APScheduler instance in the celery worker; and assorted Low items (M4, deactivated-recipient filtering, search snippet fields, AI4/AI5). Bill auto-ingestion (G1/G4) stays out of scope because bills were repositioned as vendor invoices.

## 4. Verification

Run on a fresh Postgres 15 plus Redis 7 matching the CI recipe (`pg_trgm`, `app_runtime` grant, a valid `FERNET_KEY`), inside the backend image:

- Backend: **613 passed, 0 failed, 32 skipped** (the 609 baseline plus 4 new regression tests in `tests/test_audit48_regressions.py`).
- Lint: **ruff clean** (`ruff check . --select E,F,W --ignore E501`, all checks passed).
- Migrations: **`alembic upgrade head` applies cleanly through 0037** (single head).
- Frontend: **`tsc --noEmit` 0 errors**, Next.js build verified.

The new regression tests pin the input-validation caps and the risk-scorer clamp. The IDOR, segregation-of-duties, and auth fixes were verified by hand against the diff and by the green suite; endpoint-level IDOR regression tests are a recommended follow-up.
