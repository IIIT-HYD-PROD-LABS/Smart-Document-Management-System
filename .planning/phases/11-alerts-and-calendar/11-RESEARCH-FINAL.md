# Phase 11 — Research Final (decisions committed)

**Finalized:** 2026-05-05
**Status:** Decisions locked for v2.0; v2.1 slot reserved for SendGrid migration + DLT-registered SMS

This document closes the open blockers from `11-CONTEXT.md` so v2.0
implementation can proceed without a full `/gsd:research-phase` round.

---

## 1. Email provider: stay on Resend SMTP for v2.0

**Decision:** Keep the existing Resend SMTP integration (`app/services/email_service.py`) as the email channel for v2.0 alert dispatch. SendGrid SDK migration deferred to v2.1.

**Why:**
- Resend SMTP is already wired, tested, and confirmed working (2026-04-30 SMTP fix; two test sends GREEN).
- v2.0 alert volume is bounded (one email per T-7/T-3/T-1/overdue + escalation events) — SendGrid's higher deliverability ceiling matters at >10k/day, not at ~50/day.
- Bounce / complaint webhook handling is the second-order benefit we get from SendGrid. v2.0 ships *without* a bounce-handling pipeline; users with bounced addresses get re-attempted on every alert. v2.1 lands SendGrid + bounce auto-disable.
- Migration cost is bounded: `SendGridSender` is a 30-line adapter swap. Building the v2.0 abstractions correctly today (`AlertChannel` interface, `dispatch_alert(channels=[...])`) means v2.1 swaps the concrete class without touching call sites.

## 2. SMS channel: Twilio adapter ships in v2.0, but only behind a feature flag

**Decision:** Implement `TwilioSender` as a class but do NOT enable SMS by default. Per-client `config_overrides.alert_channels` must explicitly include `"sms"` AND the Twilio credentials must be present in the encrypted vault (Phase 9 INFRA-06 pattern).

**Why:**
- Indian DLT registration is a regulatory prerequisite. Without registered templates, transactional SMS to Indian recipients is non-compliant and Twilio refuses sends.
- Building `TwilioSender` as a stub that errors-out cleanly when credentials are missing is the right *infrastructure*; live SMS sends wait for the customer to complete DLT registration.
- This matches the v2.0 "ship the wires, defer the carrier contracts" philosophy from Phase 10.

## 3. WebSocket scaling: single-process FastAPI + Redis pub/sub bridge

**Decision:** WebSocket connections terminate at FastAPI (single process for v2.0). Inter-process broadcast routes through Redis pub/sub channel `notifications:{client_id}` so the existing Celery worker can fan out without spawning a websocket connection itself.

**Why:**
- v2.0 launch volume is <100 concurrent users — single FastAPI process is sufficient.
- Redis pub/sub bridge means Celery's `dispatch_alert` task publishes to Redis; FastAPI's WebSocket manager subscribes and broadcasts to connected clients. Decouples the channels.
- v2.1 can replace single FastAPI with multi-process gunicorn workers; the pub/sub bridge remains identical.

## 4. APScheduler durability: PostgreSQL JobStore

**Decision:** APScheduler with `SQLAlchemyJobStore` using the existing PostgreSQL connection. Jobs survive worker restarts.

**Why:**
- We already have PostgreSQL; adding Redis JobStore adds a second persistence layer without operational benefit at our scale.
- T-7/T-3/T-1 reminders are infrequent (one schedule call per notice with a deadline). The JobStore overhead is negligible.
- Same pattern v1.0 doesn't use — Phase 11 is the introduction of scheduled execution. Keeps the operational surface minimal.

## 5. Compliance score formula

**Decision:** v2.0 ships a deterministic linear formula:

```
score = 100 * (notices_resolved_within_deadline / total_resolved_or_overdue_notices)
```

Computed over the rolling 90-day window. Authority severity weighting is **NOT** applied in v2.0 — the formula needs to be defensible to non-technical compliance heads, and a simple "% on time" score is the most legible. Severity-weighted variants ship in v2.1 with CA/CFO sign-off.

**Why:**
- Compliance heads will explain this score to clients/CFOs/auditors. "What % of my notices did we file on time?" is universally understandable.
- The materialized view (`mv_client_compliance_score`) refreshes nightly; sub-second page load is preserved.
- Severity weighting is a v2.1 enhancement once the rule-based authority weights from Phase 10 D-13 have CA/CFO ratification.

---

## 6. Library versions (locked)

```
APScheduler==3.11.0      # SQLAlchemyJobStore stable; FastAPI lifespan-friendly
twilio==9.4.4            # Indian DLT compatible
sendgrid==6.11.0         # v2.1 upgrade target (NOT installed in v2.0)
python-socketio          # NOT installed — using FastAPI's native WebSocket
holidays==0.61           # Indian gazetted holiday lookup; bundled corpus
```

Only APScheduler + holidays + twilio are added to `requirements.txt` in v2.0. SendGrid is documented as the v2.1 upgrade path but not pulled.

---

## 7. v2.0 → v2.1 split

**v2.0 ships:**
1. APScheduler with PostgreSQL JobStore — schedules T-7/T-3/T-1/overdue per notice
2. `dispatch_alert` Celery task — orchestrates fan-out across enabled channels
3. Email channel via existing Resend SMTP path (no provider change)
4. SMS channel scaffolding (TwilioSender class) — disabled by default per client
5. WebSocket `/ws/notifications` endpoint — JWT-auth handshake, Redis pub/sub bridge
6. `notice_alert_rules` table for per-client per-type rules
7. `notice_alert_log` for delivery audit trail
8. `regulatory_deadline_calendar` table + 21 statutory deadlines for FY 2025-26
9. `holiday_calendar` table + Indian gazetted holidays for 2026 (using `holidays` library)
10. Pure `adjust_deadline(date, state)` function for forward-shift to next working day
11. Calendar router + month/week views
12. Compliance score view (`mv_client_compliance_score`)
13. Frontend: `/dashboard/compliance/calendar` page, header bell icon + drawer
14. Phase 10 → Phase 11 wire-up: `notice_escalated` audit event triggers `dispatch_alert(channels=["email"])`

**v2.1 deferred:**
1. SendGrid migration with bounce/complaint webhook + auto-disable
2. Twilio live SMS (post-DLT registration)
3. Per-user notification preferences UI
4. Multi-process WebSocket scaling (gunicorn workers + Redis adapter)
5. ICS calendar export
6. Severity-weighted compliance score
7. Configurable escalation chain UI

---

*Phase 11 research finalized 2026-05-05.*
