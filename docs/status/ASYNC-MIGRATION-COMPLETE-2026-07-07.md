# Async Migration: Phase 9/10 Closeout and Critical RLS Fix

Date: 2026-07-07

## Summary

The sync-to-async SQLAlchemy migration (11-phase plan, approved earlier) is complete. All 10 phases are done, full backend test suite is back to the known baseline (6 pre-existing failures, unrelated to this migration), and a genuine, previously-live cross-tenant isolation bug was found and fixed during final verification.

## What this session covered

Three agents from the prior wide-parallel migration workflow reported failures (transient API errors, not incomplete work). Each was independently re-verified against the actual code on disk rather than trusted from the agent's self-report:

1. **Phase 9 (auth.py, documents.py, admin.py, early_access.py)**: confirmed already fully async-converted (0 sync `Depends(get_db)`, 0 `db.query()`). 120 tests green in isolation.
2. **Phase 10 finalization** (async conftest fixtures, mock-test classification, release-gate test): confirmed already present and structurally correct on disk.
3. **live-e2e-check**: executed fresh this session (see below).

## The critical finding

`app/compliance/middleware/tenant_context.py`'s `checkin` event listener, responsible for clearing tenant GUCs (`app.current_client_id`, `app.user_id`, `app.cross_client_mode`) when a pooled connection is returned to the pool, contained a leftover debug statement:

```python
return  # TEMPORARY: release-gate RED-proof, restore before commit
```

placed immediately after the docstring. This made the entire cleanup body permanently unreachable. Every pooled connection retained whatever tenant's session state it last had, meaning a connection that served one tenant's request could be handed to a different tenant's next request still carrying the first tenant's `app.current_client_id`. This is exactly the failure mode the RLS layer exists to prevent.

This explains two real test failures observed in the full-suite run: `test_release_gate_notices_rls.py::test_release_gate_concurrent_notices_no_cross_tenant_leak` (timed out after ~4 minutes with cascading connection errors) and `test_async_pilot_rls_integration.py::test_membership_gate_isolates_tenants_through_real_async_chain` (failed with a malformed-integer error from stale GUC state).

Fix: removed the stray `return`, restoring the real cleanup logic. Verified on disk (grep, sed) and confirmed live in the running container via matching md5sum between host and container copies of the file.

## Verification after the fix

- Both previously-failing RLS tests now pass in 2.45s (down from a 255s timeout).
- Full backend suite: 717 passed, 6 failed (all pre-existing, documented baseline: extraction/routing-gate mock tests and one notice-upload test, none related to this migration), 32 skipped. Suite runtime dropped from 307s to 93s, consistent with the checkin bug also causing connection-pool stalls, not just a correctness issue.
- Live end-to-end HTTP check against the real running app (not mocked): `/api/documents/all` returned 200 with real data; `/api/compliance/notice-types` and `/api/compliance/notices` returned 200 with correctly tenant-scoped data once tested against a client the test user actually has membership for. Celery and compliance-worker logs show no errors introduced by this migration.
- Phase 9's noted nice-to-have (`synchronize_session=False` consistency across auth.py's three bulk-update sites) is already consistent; no action needed.

## Scope notes

- The DB host cutover to `10.2.8.73` remains explicitly out of scope and deferred, per standing project decision.
- Celery/APScheduler/Alembic/CLI scripts remain permanently sync, per the original migration plan's approved carve-out. A pre-existing `TypeError: %d format` logging warning observed in Celery worker logs is unrelated to this migration (sync code, not touched) and is not fixed here.

## Files changed

- `backend/app/compliance/middleware/tenant_context.py`: removed the stray `return` in `_clear_tenant_on_checkin`.

No other code changes this session. No commits made (per standing instruction: only commit when explicitly asked).
