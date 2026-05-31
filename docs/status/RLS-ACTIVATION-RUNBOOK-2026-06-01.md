# RLS Activation Runbook, 2026-06-01

Postgres Row Level Security is now wired to be enforced at runtime as a second,
independent tenant-isolation layer behind the explicit per-endpoint client_id
filters. It is shipped GATED OFF (`DB_ENFORCE_RLS=false`), so nothing changes
until you flip the gate. This runbook is the cutover.

## What changed (all gated behind DB_ENFORCE_RLS, default false)

- `config.py`: new `DB_ENFORCE_RLS` flag. Off by default. The gate is explicit
  and deliberately NOT keyed on "is DATABASE_URL_RUNTIME set" (it already is in
  .env), so the app does not flip to RLS on a restart by accident.
- `database.py`: when the gate is on AND a runtime DSN is set, the app engine
  connects as the non-owner `app_runtime` role (RLS enforced). Otherwise it
  connects as the owner (BYPASSRLS), unchanged. Migrations always use the owner
  DSN. A small owner "bootstrap" engine handles first-client onboarding (which
  cannot satisfy RLS because no membership exists yet); it reuses the app engine
  when the gate is off, so there is no second pool in the default mode.
- Migration `0038_rls_activation_grants`: comprehensive `app_runtime` grants on
  all tables, sequences, and functions, plus default privileges for future
  objects. Closes a real gap (two lookup tables, `compliance_notice_types` and
  `compliance_regulatory_calendar`, were never granted and would 500 under
  `app_runtime`). Re-narrows `audit_logs` (append-only) and `alembic_version`
  (owner-only).
- Migration `0039_rls_self_membership_policy`: lets a user read their OWN
  membership rows with only `app.user_id` set (the client switcher and the
  notifications WebSocket need this before any client is selected).
- `clients.py` onboarding runs under the owner bootstrap session.
- `notifications.py` WebSocket sets `app.user_id` before its membership checks
  (the WebSocket scope does not run the tenant middleware).

## Verification already done (ephemeral Postgres 15, app connected as app_runtime)

- Migrations 0038 + 0039 apply cleanly on top of head (0037).
- `tests/test_rls_isolation.py`: 8 of 8 pass, including cross-tenant isolation,
  fail-closed on no context, the grant-gap lookup tables now readable, and the
  self-membership policy.
- The production engine + `before_cursor_execute` listener enforce RLS
  end-to-end: with a client context only that client's rows are visible, with
  no context zero rows are returned.
- With the gate off, the app imports unchanged (138 routes), so the default
  path is untouched.

## Cutover (do this on Supabase when you want RLS live)

1. Apply migrations to the target database so 0038 and 0039 land. Migrations run
   as the owner via alembic:
   `docker compose exec backend alembic upgrade head`
2. Confirm `DATABASE_URL_RUNTIME` points at the `app_runtime` role and
   `APP_RUNTIME_PASSWORD` matches (both are already present in `.env`). The
   `app_runtime` role was created by migration 0017.
3. Set `DB_ENFORCE_RLS=true` in the backend environment (the gitignored
   `docker-compose.override.yml`, or `.env`).
4. Restart the backend and the two workers:
   `docker compose up -d backend celery_worker compliance_worker`
5. Smoke test: log in, open the client switcher (GET /api/compliance/clients/me),
   select a client, open a notice list, onboard a test client. Watch the backend
   logs for `permission denied` (a missing grant) or unexpectedly empty lists (a
   missing tenant context).

## Rollback (instant, no database change)

Set `DB_ENFORCE_RLS=false` and restart the backend. The app reconnects as the
owner role and behaves exactly as before. The grants and policies added by 0038
and 0039 are harmless while the gate is off.

## Notes

- Celery and APScheduler tasks already set tenant context (audited), so
  background jobs work under `app_runtime` without change.
- No route outside `/api/compliance` and `/api/email` touches a client-scoped
  RLS table, so the v1.0 routes (documents, auth, admin) are unaffected.
- The grants in 0038 do not weaken isolation: RLS still filters rows on every
  FORCE-RLS table regardless of the grant. The grant only provides the object
  privileges RLS needs in order to apply.
