# 08 · COMPLIANCE WORKFLOW

> Phase 9 → 13 · 6-state notice machine · 4-stage approval · 37 statutory deadlines · WebSocket alerts

## ★ Remember
- 6 notice states · 4 approval stages · 5 authorities · 4 risk tiers
- Activity timeline = mutable; audit log = **immutable** (DB trigger)
- Bulk ops still go through the state machine — no shortcut

---

## 1. v2.0 phase landscape

```
PHASE 9   Foundation                 10 tables · RLS · audit trigger · 7×12 RBAC
PHASE 10  Risk scoring + escalation  rule-based scorer · SHAP explanations · review queue
PHASE 11  Alerts + statutory cal.    APScheduler · 37 FY 25-26 deadlines · WebSocket bell
PHASE 12  4-stage approval           Drafter → Reviewer → Legal → CFO · versioned drafts
PHASE 13  Cross-entity search        unified FTS (notices + documents) · 3 analytics
```

---

## 2. Notice state machine

```
                ┌───────────┐
                │ RECEIVED  │
                └─────┬─────┘
                      │
            ┌─────────┴───────────┐
            ▼                     ▼
     ┌─────────────┐         ┌─────────┐
     │UNDER_REVIEW │◄───┐    │DISMISSED│  (terminal)
     └─────┬───────┘    │    └─────────┘
           │            │
           ▼            │
     ┌──────────────┐   │ back-edit
     │RESPONSE_DRAFT│───┘
     └─────┬────────┘
           ▼
     ┌─────────────┐ ◄── authority requests clarification
     │  SUBMITTED  │──┐
     └─────┬───────┘  │
           ▼          ▼
     ┌──────────┐  back to UNDER_REVIEW
     │ RESOLVED │       (terminal)
     └──────────┘
```

Source: `backend/app/compliance/services/notice_state_machine.py`. Validates `(current, target)` against `ALLOWED_TRANSITIONS`. `InvalidTransitionError` raised on illegal jumps.

---

## 3. 4-stage approval (Phase 12)

```
DRAFTER
   creates response_draft v1
   evidence_service.attach(document_id)
        │
        ▼ submit
REVIEWER  (notice:approve)
   ▼ approve / send back
LEGAL     (notice:approve_legal)
   ▼ approve / send back
CFO       (notice:approve_cfo)
   ▼ approve → notice goes to SUBMITTED
```

- Each stage gated by its specific permission
- Drafts are versioned (immutable history)
- Send-back rolls to UNDER_REVIEW, draft version++ on next save
- All transitions land in `compliance_notice_activity`
- Audit log captures user + IP per transition

---

## 4. Client & membership model

```
compliance_clients          (tenant root · RLS pivot)
   id · name · client_type · logo_url · website · address
   config_overrides JSONB

compliance_client_registrations  (multi-GSTIN — one row per state)

compliance_memberships     (M:N users × clients × role)
   user_id · client_id · role  (7 ComplianceRole values)
   expires_at NULL = forever
```

A single user can have different roles in different tenants. Role is checked **at request time**, not stored in the JWT.

---

## 5. Statutory calendar (Phase 11)

- 37 FY 2025-26 deadlines pre-seeded by migration 0016
- Recurring rules (annual / quarterly / monthly) + one-offs
- Indian holiday calendar (`holidays` pkg) shifts deadlines
- APScheduler durable jobstore on `apscheduler_jobs`
- Scheduler fires `alert_tasks/check_due`
- Channels: email + WebSocket. SMS scaffolded (Twilio)
- SendGrid migration deferred to v2.1

---

## 6. Alert pipeline

```
APScheduler job (every 5 min)
   │
   ▼
alert_tasks.check_due
   query: deadlines within 7d
   for each:
      email_sender.send()           Resend SMTP
      websocket_broadcast()         /ws/notifications
   write activity + audit

UI:
   NotificationBell.tsx subscribes to WS
   useNotificationStream hook reconnects w/ exponential backoff
```

---

## 7. Notice chain (recursive CTE)

```
SCN ──► Assessment ──► Demand ──► Appeal
```

`parent_notice_id` self-FK builds the chain. `notice_service.get_notice_chain(id, max_depth=10)` runs:

```sql
WITH RECURSIVE chain AS (
   SELECT * FROM compliance_notices WHERE id = :id
 UNION ALL
   SELECT n.* FROM compliance_notices n
     JOIN chain c ON n.parent_notice_id = c.id
     WHERE c.depth < :max_depth
)
SELECT * FROM chain;
```

UI: `NoticeChainTree.tsx` renders the tree.

---

## 8. Unified search (Phase 13)

```sql
SELECT 'notice'::text   AS kind, id, title, …
  FROM compliance_notices
 WHERE search_vector @@ websearch_to_tsquery(:q)
UNION ALL
SELECT 'document'::text AS kind, id, original_filename, …
  FROM documents
 WHERE search_vector @@ websearch_to_tsquery(:q)
ORDER BY ts_rank(...) DESC
LIMIT 50;
```

RLS still in effect — only the active tenant's rows are visible. Elastic Cloud deferred to v2.1.

---

## 9. Analytics (Phase 13)

- **Penalty by authority** — sum / count grouped by `authority`
- **Notice volume by status** — stacked over time
- **Response time percentiles** — p50 / p90 / p99 from `received_date` → `submitted_date`
- Endpoints under `/api/compliance/reports`
- CSV export for all three (v2.0.1)
- Stdlib `csv` + `StreamingResponse`; no new dependencies

---

## 10. Gmail MCP (Phase 15)

```
User connects Gmail → OAuth → tokens encrypted in DB
Filter rule: from .gov.in OR subject contains "Notice"
   │
   ▼
MCP server reads inbox via Gmail API
   for each match:
      ingest attachment → documents row (source='gmail')
      if looks like notice: create compliance_notice
                              source='gmail'
      log activity + audit

Surface in UI: /dashboard/email/{activity, bills, settings}
```

All endpoints gated on `EMAIL_INTEGRATION_USE`. The FastMCP server is in-process (no child process spawned).

---

## 11. Client onboarding

- `OnboardingWizard` component, Zustand-driven wizard state (`onboardingWizardStore`)
- Steps: business info → GST registrations → team members → first notice
- Saves draft to localStorage between steps
- `POST /api/compliance/clients` on finish
- Branding (logo · website · address) editable later from **Clients → \<client\> → Branding**

---

## 12. Bulk operations

- `BulkActionBar` over `NoticeTable`
- Select rows → bulk assign · bulk tag · bulk status change
- Gated on `NOTICE_BULK_UPDATE` permission
- Each change goes through the state machine (no shortcut)
- Failures roll back; partial success returns HTTP 207

---

> "Compliance is a state machine wrapped in a permission matrix
> guarded by a tenant filter, audited by a DB trigger."

**Layer interaction:**
- Route → checks permission → calls service
- Service → validates state machine → calls model → writes activity + audit
- Model → RLS filters → returns rows
- If ML auto-classified with low confidence → review_queue row pops up
- If risk = critical → escalation activity logged automatically
