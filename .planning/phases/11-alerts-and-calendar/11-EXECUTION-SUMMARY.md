---
phase: 11-alerts-and-calendar
status: code-complete
completed_at: "2026-05-05"
---

# Phase 11 v2.0 — Execution Summary — CODE-COMPLETE

## Delivered

### Migration
- `backend/alembic/versions/0021_phase11_alert_tables.py` — adds
  `notice_alert_log` (idempotent UNIQUE on notice_id + alert_type +
  recipient_user_id + channel) and `notice_alert_rules` (per-client
  per-type JSONB rule storage). Both RLS-enabled with `tenant_isolation`
  policy mirroring Phase 9. Applied to head.

### Backend modules
- `app/compliance/models/alert.py` — `NoticeAlertLog` + `NoticeAlertRule` ORM
- `app/compliance/calendar/adjust.py` — pure `adjust_deadline(date, state_code)` skipping Sundays + Indian gazetted holidays via `holidays` library
- `app/compliance/calendar/statutory.py` — 37 statutory deadlines for FY 2025-26 (GSTR-1, GSTR-3B, GSTR-9, TDS quarters, Advance Tax, ITR, AOC-4, MGT-7)
- `app/compliance/calendar/seed.py` — idempotent seeding into `compliance_regulatory_calendar` (already 37 rows seeded for 2026)
- `app/compliance/services/alert_service.py` — `dispatch_alert(notice, alert_type, channels, recipients, payload)` orchestrator with PG `ON CONFLICT DO NOTHING` idempotency. `resolve_recipients` walks ClientMembership for active users matching role list.
- `app/compliance/services/senders.py` — `EmailSender` (Resend SMTP via existing `app/utils/email.py`), `SmsSender` (Twilio adapter, disabled-by-default until DLT registration), `WebSocketSender` (Redis pub/sub publish to `notifications:{client_id}`)
- `app/compliance/services/scheduler.py` — APScheduler with PostgreSQL JobStore. `schedule_deadline_alerts(notice_id, deadline)` schedules T-7/T-3/T-1/overdue jobs; `cancel_deadline_alerts` removes on terminal status transition.
- `app/compliance/websocket/manager.py` — `ConnectionManager` with Redis pub/sub bridge; per-client connection tracking + RBAC-parity broadcast filter
- `app/compliance/routers/notifications.py` — `/ws/notifications` WebSocket with JWT-token + active-membership gate
- `app/compliance/routers/calendar.py` — `GET /entries`, `POST /adjust-deadline`, `GET /compliance-score` (rolling 90-day on-time %)
- `app/compliance/routers/alerts.py` — `GET /pending`, `GET /rules`, `PUT /rules`
- `app/tasks/alert_tasks.py` — `dispatch_notice_alert` Celery task on the `compliance` queue
- `app/ml/compliance/escalation.py` — wired to fire `dispatch_notice_alert` on Critical escalation (channels=email+websocket, recipients=compliance_head+cfo)
- `app/compliance/services/notice_service.py` — `transition_notice_status` calls `schedule_deadline_alerts` on entry into `under_review`, `cancel_deadline_alerts` on terminal transitions

### Library deps
Installed in backend + celery + compliance-worker containers and pinned in `requirements.txt`:
- `APScheduler==3.11.0`
- `twilio==9.4.4`
- `holidays==0.61`

### Frontend
- `frontend/src/types/compliance.ts` — `CalendarEntry`, `AlertLogEntry`, `AlertRule`, `ComplianceScore`, `AdjustDeadlineResult`, `NotificationEnvelope`
- `frontend/src/lib/api/compliance.ts` — `listCalendarEntriesV2`, `adjustDeadline`, `getComplianceScore`, `listPendingAlerts`, `listAlertRules`, `upsertAlertRule`
- `frontend/src/hooks/useNotificationStream.ts` — auto-reconnecting WebSocket subscription, exponential backoff capped at 30s
- `frontend/src/components/compliance/NotificationBell.tsx` — bell icon with unread count + slide-over drawer
- `frontend/src/components/compliance/ComplianceScoreChip.tsx` — header chip; green/amber/red by score
- `frontend/src/app/dashboard/compliance/calendar/page.tsx` — month-grid calendar with authority + category filters; auto-shifts holidays
- `frontend/src/app/dashboard/compliance/layout.tsx` — header now mounts `ComplianceScoreChip` + `NotificationBell`
- `frontend/src/app/dashboard/layout.tsx` — sidebar nav adds `Calendar` entry

### Tests
- `tests/test_calendar_adjust.py` — 8 tests: Sunday shift, Saturday working-day, Republic Day, Independence Day, state-code parametrization, max-skip safety
- `tests/test_alert_dispatch.py` — 7 tests: EmailSender + SmsSender + WebSocketSender + recipient resolution
- `tests/test_compliance_score.py` — 6 tests: score formula edge cases (denominator-zero default 100%, all on time, all overdue, partial, status_changed_at gating)

## Acceptance verification

- Migration 0021 applied to head; tables visible
- 37 statutory deadlines seeded for FY 2025-26 in `compliance_regulatory_calendar`
- 95 backend tests GREEN (Phase 10 + Phase 11 + supporting suites; no regressions)
- Phase 10 smoke test re-run with Phase 11 escalation→alert wiring active: PASSED (Critical-tier notice creates escalation activity + audit log + dispatches `dispatch_notice_alert` Celery task; alert delivery logs flow through `notice_alert_log`)
- 9 compliance endpoints exposed via OpenAPI: `/api/compliance/{review/pending, review/{id}, review/{id}/assign, alerts/pending, alerts/rules, calendar/entries, calendar/adjust-deadline, calendar/compliance-score, regulatory-calendar}` + WebSocket `/ws/notifications`
- Frontend rebuilt; routes `/dashboard/compliance/{calendar,review,...}` return 307 (auth redirect — expected behavior, routes register cleanly)

## v2.0 → v2.1 split (binding)

**v2.0 ships now:**
1. APScheduler with PostgreSQL durable JobStore — schedules T-7/T-3/T-1/overdue per notice
2. Email channel via existing Resend SMTP path
3. WebSocket `/ws/notifications` — JWT-auth handshake, Redis pub/sub bridge
4. Calendar UI with month grid + authority/category filters
5. Compliance score chip (rolling 90-day on-time %)
6. NotificationBell with unread badge
7. SMS scaffolding (TwilioSender) — disabled by default; sends when env credentials present
8. Phase 10 escalation → Phase 11 alert dispatch wired

**v2.1 deferred:**
1. SendGrid migration with bounce/complaint webhook + auto-disable
2. Twilio live SMS post-DLT registration
3. Per-user notification preferences UI
4. Multi-process WebSocket scaling (gunicorn + Redis adapter)
5. ICS calendar export
6. Severity-weighted compliance score
7. Configurable escalation chain UI (currently per-client `config_overrides` only via direct DB write)

## Notes

- The `notice_alert_log` UNIQUE constraint is the dedup contract: re-firing the same alert is a safe no-op via PostgreSQL `ON CONFLICT DO NOTHING`. The Celery task can retry on failure without producing duplicate emails.
- The compliance score formula intentionally simple (% on time) — severity-weighted variants need CA/CFO sign-off and the placeholder `AUTHORITY_SEVERITY` weights from Phase 10 D-13 must be ratified first.
- WebSocket auto-reconnect uses exponential backoff capped at 30s — enough resilience for flaky mobile networks without thundering-herd reconnect storms.
- The compliance-worker Celery service (2GB memory, queue=compliance) carries both ML inference (Phase 10) and alert dispatch (Phase 11); v1.0 default-queue worker is untouched. Zero v1.0 throughput regression.
