# Phase 11: Alert System + Compliance Calendar - Context

**Gathered:** 2026-05-05 (seed scope; awaiting `/gsd:discuss-phase 11` refinement and `/gsd:research-phase 11`)
**Status:** Awaiting research and discussion

<domain>
## Phase Boundary

**In scope:** No compliance deadline is silently missed. The system fires
multi-channel reminders (email, SMS, in-app WebSocket) at T-7/T-3/T-1 days
before each notice deadline, and a compliance calendar shows all Indian
statutory filing deadlines for each client entity, holiday-aware.

**Specifically:**

1. APScheduler integration for time-based reminders (T-7/T-3/T-1, overdue,
   custom).
2. SendGrid email channel — reuses existing SMTP path's templates contract
   but routes critical/regulatory mail through SendGrid for deliverability.
3. Twilio SMS channel — fires only for Critical/High-priority notices to
   contain cost.
4. WebSocket in-app notifications via FastAPI WebSocket endpoint —
   auto-reconnect on drop; falls back to polling every 30s if connection
   fails.
5. Per-notice-type alert rules — channel preference, recipient hierarchy,
   threshold gates, configurable via Phase 9's `config_overrides` JSONB.
6. Escalation chain consumer — listens for the `notice_escalated` audit
   event written by Phase 10 Plan 02, fans out to the configured chain
   (default: compliance_head → CFO → external counsel).
7. Compliance calendar at `/dashboard/compliance/calendar` — monthly + weekly
   views, filter by authority + obligation type, filing-status indicator
   pulled from existing notices.
8. Indian statutory deadlines pre-loaded — GSTR-1, GSTR-3B, GSTR-9, TDS
   quarterly, Advance Tax quarterly, ITR (4 categories), ROC filings,
   loaded via migration seed.
9. Holiday calendar — gazetted Indian holidays (CBDT/CBIC + state) per year;
   deadline shifts forward to next working day if it falls on a holiday.
10. Real-time notification surface — header bell icon + dropdown drawer with
    unread count, mark-read action, deep-link to source notice.

**Out of scope (explicitly):**

- WhatsApp / Telegram channels — defer to v2.1 unless customer survey
  shows demand.
- SMS internationalization (only Indian +91 numbers in v2.0).
- Calendar export to ICS / Google Calendar / Outlook — defer to v2.1
  (the calendar is viewable in-app; sync is a nice-to-have).
- Per-user notification preferences UI — v2.0 ships per-client config; the
  per-user preference fan-out comes in v2.1.
- Predictive deadline suggestions ("you usually file GSTR-3B on the 18th")
  — deferred to v3.0 ML calendar.
- A/B testing email templates — v2.0 ships single deterministic templates.
- Push notifications via Web Push API or APNs — v2.0 is WebSocket only.

</domain>

<decisions>
## Implementation Decisions (proposed seed; refine via `/gsd:discuss-phase 11`)

### Alert Pipeline (ALERT-01..10)

- **D-01:** APScheduler with PostgreSQL JobStore — durable across worker
  restarts. Alternative (Celery Beat + redbeat) is rejected because the v1.0
  Celery worker stays on `default` queue; alert-specific scheduling lives in
  the new `compliance-worker` (which already has 2GB ceiling) to keep v1.0
  isolation.
- **D-02:** Single canonical `dispatch_alert(notice_id, alert_type, channels)`
  Celery task — channel-specific senders are pluggable (`SendGridSender`,
  `TwilioSender`, `WebSocketSender`). Alert delivery is idempotent via
  `(notice_id, alert_type, recipient, channel)` UNIQUE on a new
  `notice_alert_log` table.
- **D-03:** T-7/T-3/T-1 + overdue scheduling — when a notice's
  `response_deadline` is set or changes, an APScheduler job is scheduled at
  the relevant times. Cancel on status transition to `submitted/resolved/dismissed`.
- **D-04:** SendGrid via official Python SDK; bounce / complaint webhook
  endpoint (auth-gated by signed query parameter) updates a per-recipient
  reputation flag — repeated bounces auto-disable email channel for that user.
- **D-05:** Twilio via official Python SDK; Indian DLT compliance — every
  template is registered with a DLT entity ID and template ID per IRDAI
  regulation (commercial SMS to Indian recipients).
- **D-06:** WebSocket auth — JWT in initial query string + handshake check;
  per-connection client subscription (`client_id` filter applied
  server-side so a connected user never sees notifications for clients they
  lack membership in — Phase 9 RBAC parity).
- **D-07:** WebSocket message envelope: `{type: "notice_alert", payload: {...}}`
  with type discriminator so a future `bill_alert`, `system_alert`, etc. can
  share the same socket.

### Per-Type Alert Rules

- **D-08:** `notice_alert_rules` lookup table keyed by `(client_id, notice_type_id)`
  — JSONB column holds `{channels: [...], threshold_score: int, recipients: [...],
  escalation_chain: [...]}`. Defaults loaded via Phase 9 D-17 config_overrides;
  per-client overrides win over defaults.
- **D-09:** Recipient hierarchy is a list of role identifiers (e.g.
  `["compliance_head", "cfo", "external_counsel"]`); `dispatch_alert`
  resolves each role to active members of the client and fans out via the
  selected channels.

### Compliance Calendar (CAL-01..06)

- **D-10:** New table `regulatory_deadline_calendar` with columns: `authority`,
  `deadline_type` (e.g. `GSTR-3B`, `Advance Tax Q3`), `due_date`,
  `applicable_to` (JSONB array of client_type and registration_type filters),
  `category` (`monthly`, `quarterly`, `annual`), `is_holiday_adjusted` boolean.
  Pre-loaded for FY 2025-26 via migration seed.
- **D-11:** Holiday source — canonical `indian_gazetted_holidays_<year>` JSON
  file in repo, loaded via `python -m app.compliance.calendar.seed_holidays
  --year 2026`. Each holiday has `(date, name, source: "central"|"state",
  applies_to_states: list[state_code])`.
- **D-12:** Adjustment rule — when a deadline falls on Sunday OR a gazetted
  holiday in the affected state, deadline shifts forward to the next working
  day. Rule encoded in a pure function `adjust_deadline(date, state) -> date`
  for testability + reuse by Phase 10 risk scorer (deadline pressure).
- **D-13:** Calendar UI — month grid + week list, filter sidebar (authority,
  category, registration), color-code by status (filed / pending / overdue).
  Render via FullCalendar React (open-source, MIT) or hand-rolled — bake-off
  during planning.
- **D-14:** "Compliance score" header chip — derived from
  `(notices_resolved_on_time / total_notices) * 100` over rolling 90 days.
  Emits a delta indicator vs. the previous 90 days. Source-of-truth lives in
  a materialized view refreshed nightly to keep page load < 1s.

### Frontend (UI hint: yes)

- **D-15:** `/dashboard/compliance/calendar` page — month grid, deadline
  badges, click-to-create-notice quick action.
- **D-16:** Header bell icon + drawer — list of unread notifications,
  per-row click navigates to source notice.
- **D-17:** Per-notice detail page gets an "Upcoming alerts" strip —
  shows scheduled T-7/T-3/T-1 events and channels they'll fire on.
- **D-18:** Settings page surface for alert rules — Phase 11 ships READ-ONLY;
  edit UI defers to v2.1 (config_overrides JSONB editing is risky without
  schema validation guardrails).

### Infrastructure

- **D-19:** SendGrid + Twilio API keys stored encrypted in same Fernet vault
  pattern Phase 9 INFRA-06 introduced — never in `.env`, always in encrypted
  DB column accessed only by the compliance worker.
- **D-20:** Webhook signature verification — SendGrid webhooks signed via
  EC public key; Twilio via HMAC. Reject unsigned. Documented in
  `docs/webhooks.md`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — ALERT-01..10 (Alert system), CAL-01..06
  (Calendar), INFRA-03..04 (APScheduler infrastructure)

### Upstream Phases (dependencies)
- `.planning/phases/09-compliance-foundation/09-CONTEXT.md` — RBAC, RLS,
  audit, config_overrides JSONB pattern
- `.planning/phases/10-ml-classification-risk-scoring/10-CONTEXT.md` —
  risk_tier and `notice_escalated` audit event that this phase consumes
  for cross-channel delivery
- `.planning/phases/10-ml-classification-risk-scoring/10-RESEARCH-FINAL.md`
  — Phase 10 v2.0 ship vs v2.1 deferral; alert pipeline must NOT depend on
  BERT being trained

### Existing Codebase
- `backend/app/services/audit_service.py` — log_audit_event pattern
- `backend/app/compliance/services/activity_service.py` — NoticeActivity
  timeline write pattern
- `backend/app/ml/compliance/escalation.py` (Phase 10) — escalation event
  emitter; alert pipeline subscribes to `notice_escalated` audit rows
- `backend/app/tasks/celery_app.py` — Celery configuration; routing rule
  for new alert tasks goes here

### Architecture
- `.planning/codebase/ARCHITECTURE.md`
- `.planning/codebase/STACK.md` — Phase 11 adds: APScheduler, sendgrid-python,
  twilio, fastapi-websocket
- `.planning/codebase/CONVENTIONS.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- v1.0 `app/services/email_service.py` — SMTP base; SendGrid is a drop-in
  adapter (different transport, same template contract).
- v1.0 `app/utils/security.py` — JWT token generation; reused for WebSocket
  handshake.
- Phase 9 `audit_service.log_audit_event` — every alert send writes an
  audit row. Critical for compliance: "did the system warn the user about
  this deadline?" must be answerable.
- Phase 10 escalation hook — already emits `notice_escalated` audit row;
  Phase 11's alert dispatcher subscribes to those rows in a daemon poll
  (or via direct Celery chain — bake-off during research).

### Established Patterns
- Service layer is single point of mutation
- Celery task naming `app.tasks.<domain>_tasks.<verb>_<entity>` (e.g.
  `app.tasks.alert_tasks.dispatch_alert`)
- SQLAlchemy ORM with Alembic migrations
- Pydantic schemas for I/O validation
- React Query for frontend data fetching
- Tailwind hex tokens via inline-style; same color contract as Phase 9

### Integration Points
- Backend: New `/api/compliance/alerts/*` for rule CRUD; new
  `/api/compliance/calendar/*` for calendar entries; WebSocket at
  `/ws/notifications`. New `notice_alert_log`, `notice_alert_rules`,
  `regulatory_deadline_calendar`, `holiday_calendar` tables.
- Celery: New `dispatch_alert` task on the existing `compliance` queue.
- Frontend: New `/dashboard/compliance/calendar` page, header bell icon,
  per-notice "Upcoming alerts" strip on detail page.

### Anti-patterns to Avoid
- Do NOT store SendGrid/Twilio credentials in plain `.env` — use the
  Fernet vault pattern (Phase 9 INFRA-06).
- Do NOT broadcast WebSocket messages to all connected users — server-side
  client_id filter (Phase 9 RBAC parity) is mandatory.
- Do NOT skip DLT compliance for SMS — Indian regulators levy fines for
  unregistered template senders.
- Do NOT make alerts mutate notice state — alerts are read-only side
  effects of state changes; never the cause.

</code_context>

<specifics>
## Specific Ideas

- The 21 statutory deadlines for FY 2025-26 are a known upfront-loadable
  set; we're not designing a generic deadline engine — we're hard-coding
  the Indian compliance calendar.
- WebSocket auto-reconnect with exponential backoff is the reliability
  contract; users on flaky mobile networks must NOT lose alert deliveries.
- The escalation chain semantics matter: each step is a fire-and-forget
  delivery, not a wait-for-acknowledgement. If compliance_head doesn't
  respond, CFO is notified at T+24h regardless. The "wait for ack" mode
  is v2.1.

</specifics>

<deferred>
## Deferred Ideas

- WhatsApp / Telegram channels — v2.1 if customer survey shows demand.
- ICS calendar export — v2.1 nice-to-have.
- Per-user alert preferences UI — v2.1; v2.0 ships per-client only.
- Predictive deadline suggestions — v3.0 ML feature.
- Push notifications via Web Push API / APNs — v3.0.
- A/B testing alert templates — v3.0.

</deferred>

---

*Phase: 11-alerts-and-calendar*
*Context seeded: 2026-05-05 — refine via `/gsd:discuss-phase 11` and `/gsd:research-phase 11` (resolves SendGrid vs Resend choice + DLT registration pathway) before `/gsd:plan-phase 11`*

## Open Blockers (must be resolved during `/gsd:research-phase 11`)

1. **Email provider — SendGrid vs Resend vs hybrid.** v1.0 already has
   Resend wired via SMTP; ALERT-01 names SendGrid but Resend may be
   sufficient. Bake-off needed: deliverability stats for Indian recipients,
   bounce handling, DKIM/DMARC setup effort.
2. **DLT registration prerequisite.** TRAI mandates DLT-registered templates
   for transactional SMS to Indian recipients. Need to verify whether
   Twilio's pre-registered templates cover compliance use cases or if we
   need to register custom templates with our own entity ID.
3. **WebSocket scaling — single-process vs Redis pub/sub.** Single-process
   FastAPI is fine for <100 concurrent users; if v2.0 launches with >100,
   we need Redis pub/sub fan-out so multiple FastAPI workers can broadcast.
4. **APScheduler durability — PostgreSQL vs Redis vs MongoDB JobStore.**
   PostgreSQL is operationally simpler (we already have it); Redis is
   faster but loses jobs if Redis restarts without RDB persistence.
5. **Compliance score formula.** The "% on-time over rolling 90 days"
   needs domain-expert sign-off — should it weight authority severity?
   Should overdue notices count as 0 or as negative?
