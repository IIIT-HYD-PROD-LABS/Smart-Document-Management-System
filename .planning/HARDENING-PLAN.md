# Phase 9-11 Hardening Plan — 2026-05-05

Source: 4-agent end-to-end audit (code-reviewer, security-auditor, debugger,
silent-failure-hunter). 43 distinct findings; 17 block-fixed before Phase 12,
26 deferred with rationale.

This document is the audit trail for hardening decisions. The block-fix
items are executed inline in the same session. Deferred items become
Phase 11.1 / v2.1 work.

---

## Block-fixes (must land before /gsd:discuss-phase 12)

### CRITICAL

**1. Celery RLS bypass** (security-auditor C1)
File: `backend/app/tasks/compliance_tasks.py`, `backend/app/tasks/alert_tasks.py`
Issue: `SessionLocal()` called without `set_tenant_context_for_celery(...)`. Empty ContextVars + listener short-circuit → RLS policies fail-closed (zero rows) under `app_runtime`, OR if worker is `app_migrator` (BYPASSRLS), reads cross-tenant.
Fix: System tasks running across all tenants (`recompute_all_risk_scores`) set `cross_mode=True`. Per-notice tasks (`classify_and_score_notice`, `dispatch_notice_alert`) load the notice with `RESET ROLE` once, capture client_id, then set tenant context for the rest of the work.

**2. WebSocket alerts publish to wrong channel** (code-reviewer + security-auditor + debugger)
File: `backend/app/compliance/services/alert_service.py:120`
Issue: `body.setdefault("client_id", ...)` never called, so `WebSocketSender` falls back to `notifications:default`. `_listen_redis` parses split → ValueError swallowed at line 99-100. **Zero production WebSocket notifications work.**
Fix: Override (not setdefault) `body["client_id"] = notice.client_id` in `dispatch_alert`.

**3. `audit_service.log_audit_event` swallows ALL exceptions** (silent-failure-hunter C1)
File: `backend/app/services/audit_service.py:42-50`
Issue: Constraint violations, JSON serialization errors, DB drops disappear into a `warning` log. Caller treats as success. Audit immutability claim has a write-side hole.
Fix: Escalate failures to `logger.error` with `exc_info=True` + write a fallback `audit_failures.jsonl` line + propagate a structured `AuditFailureMarker` so downstream code knows audit didn't land. v2.0.1 follow-up: dead-letter queue surface in /admin.

**4. `escalate()` silently loses alert dispatch** (silent-failure-hunter C2)
File: `backend/app/ml/compliance/escalation.py:200-214`
Issue: When `dispatch_notice_alert.delay()` raises (broker down), failure is logged but no `notice_alert_log` row exists for the failed dispatch. Operator sees no surface to retry from.
Fix: On dispatch failure, write a `notice_alert_log` row with `delivery_status='failed'` + `error='broker_unavailable: ...'` so `/api/compliance/alerts/pending` shows it.

### HIGH

**5. WebSocket auth one-shot at connect** (security-auditor H1, code-reviewer M)
File: `backend/app/compliance/routers/notifications.py:64-83`
Issue: `is_membership_active(membership)` checked once. Auditor's `access_end` passes mid-session → connection persists, alerts continue.
Fix: `asyncio.wait_for(receive_text(), timeout=60)` with `db.refresh(membership)` + `is_membership_active` revalidation on each timeout. Close on `WS_1008_POLICY_VIOLATION`.

**6. PII in `ner_extracted_fields` JSONB plaintext** (security-auditor H2)
File: `backend/app/tasks/compliance_tasks.py:85-94`
**DEFERRED to v2.0.1** with mitigation note: backup pipeline already treats `compliance_notices` as PII. Fixing properly requires migration to encrypt JSONB sub-fields; not a regression vs Phase 9 baseline.

**7. HTML injection in EmailSender** (security-auditor H3)
File: `backend/app/compliance/services/senders.py:71-79`
Issue: `notice_number`, `authority`, `status` (user-controlled) interpolated into `html_body`. `MIMEText(..., "html")` renders. `<script>` / `<img onerror=...>` execute in compliance_head's email client.
Fix: `html.escape()` on every payload field before interpolation. Subject is already plain-text-safe.

**8. Fictional cron fallback** (silent-failure-hunter)
File: `backend/app/compliance/services/notice_service.py:122-128, 142-147`
Issue: Comments claim "daily recompute will pick this up" but `recompute_all_risk_scores` is not in any `beat_schedule`.
Fix: Add `beat_schedule` entry to `celery_app.conf` for daily 02:00 UTC (07:30 IST). Also add `app.tasks.alert_tasks` to `celery_app.conf.include` (currently missing!).

**9. `retries_exhausted` returns dict** (silent-failure-hunter)
File: `backend/app/tasks/compliance_tasks.py:243-248`
Issue: Returning a dict on max-retries makes Celery record the task as SUCCESS. No DLQ.
Fix: Re-raise the original exception so `task_reject_on_worker_lost=True` + result backend record FAILURE.

**10. ActivityTimeline status_change key mismatch** (debugger TRACE 6)
Files: backend writes `details["to"]` (`notice_service.py:90`), frontend reads `details["new_status"]` (`ActivityTimeline.tsx:44`).
Issue: Every status change row in the UI renders `"moved status to —"`.
Fix: Frontend reads both keys with fallback. Backend stays the same (it's also written this way for the bulk update path; changing it would invalidate existing rows).

**11. Redis listener crash kills alerts permanently** (debugger TRACE 4 + silent-failure)
File: `backend/app/compliance/websocket/manager.py:72-110`
Issue: After `except Exception`, the listener task ends. New connections restart it; existing connections see no alerts. `notice_alert_log` says `sent` but no client receives.
Fix: Outer reconnect loop with exponential backoff (1s → 30s cap). Inner per-message try/except so one bad message doesn't kill the bridge.

**12. `ON CONFLICT DO NOTHING` blocks resend on email change** (debugger TRACE 2)
**DEFERRED to v2.0.1** — rare in practice; fix requires schema decision (key by user_id vs key by user_id+email_at_dispatch). Track in v2.1 backlog.

**13. SMS sender always fails** (code-reviewer)
File: `backend/app/compliance/services/senders.py`, `backend/app/models/user.py`
Issue: User has no `phone` column. Every SMS dispatch returns "no_phone_for_recipient" + adds noise to `/alerts/pending`.
Fix: Document SMS as v2.1 in senders.py docstring. Drop `"sms"` from any default channel list (currently only `["email", "websocket"]` is used in `escalation.py:194`; safe). v2.1 ships `users.phone` migration + DLT-registered Twilio.

**14. Naive datetime in scheduler** (code-reviewer)
File: `backend/app/compliance/services/scheduler.py:63`
Issue: `datetime.combine(...)` may produce naive datetime; arithmetic with `datetime.now(timezone.utc)` raises.
Fix: Normalize to UTC-aware via `if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)`.

**15. TDS Q4 fiscal-year semantic muddle** (code-reviewer)
File: `backend/app/compliance/calendar/statutory.py:91`
**DEFERRED with documentation fix** — rename `expand_statutory_deadlines(year)` parameter docstring to clarify FY-vs-CY semantics. Splitting per-FY requires a refactor that's out of scope for hardening pass.

**16. `alerts.py` docstring lies about `/log` + `/retry`** (code-reviewer)
File: `backend/app/compliance/routers/alerts.py:1-8`
Fix: Remove unimplemented routes from docstring. Optional: implement `/retry/{alert_id}` (single-line wrapper around `dispatch_notice_alert.delay`). v2.0.1 implements `/log` (full alert log query).

**17. `last_escalation_at` Python-side filter** (code-reviewer)
File: `backend/app/ml/compliance/escalation.py:51-65`
Issue: Loads ALL `assigned` activity rows then iterates. Defeats the index.
Fix: Push filter to Postgres via `NoticeActivity.details["source"].astext == ACTIVITY_SOURCE`.

---

## Deferred (v2.0.1 / v2.1 backlog)

26 medium-severity findings deferred. Captured in `.planning/HARDENING-DEFERRED.md`
for v2.0.1 grooming. Highlights:
- M1 notice_alert_log UPDATE permission → restructure to single INSERT after send (refactor)
- TRACE 5 midnight race in recompute → mitigate by passing fixed `today` per-batch (perf)
- TRACE 3 multi-worker APScheduler → single-worker constraint until v2.1 multi-process scaling
- M2 WebSocket payload caller-controlled client_id → addressed alongside CRITICAL #2 (override semantics)
- code-reviewer perf items (compliance_score SQL aggregate, alert_service N+1, broadcast cleanup)
- WebSocket holds DB session for entire lifetime (#26)

---

## Verification gates

Before Phase 12:
1. All 13 fix-now items committed
2. Existing 107 tests still GREEN
3. ≥4 new tests covering: Celery RLS context, WebSocket payload client_id, audit failure dead-letter, escalation broker-down failure persistence
4. Phase 10 smoke re-run: PASSED
5. STATE.md updated with hardening status

---

## Decision log

- Did not block on M1 `notice_alert_log` UPDATE permission: restructuring to single-INSERT requires reordering of error handling that's safer in a separate PR.
- Did not block on PII JSONB encryption (H2): not a regression vs Phase 9; v2.0.1 owns proper Fernet sub-field encryption.
- Did not block on TDS Q4 fiscal year (#15): semantic clarity, not a correctness bug; documentation pass sufficient.
- Did not block on `ON CONFLICT` email change (#12): low-frequency real-world scenario; v2.0.1 owns key restructure.
- Multi-worker APScheduler (TRACE 3): production deploy must be single-worker for the compliance service in v2.0; v2.1 adds Redis distributed lock.
