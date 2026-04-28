# Phase 15: Gmail MCP Integration & Email Document Ingestion - Context

**Gathered:** 2026-04-28 (seed scope; awaiting `/gsd:discuss-phase 15` refinement)
**Status:** Awaiting research and discussion

<domain>
## Phase Boundary

**In scope:** A user connects their Gmail account once and the system continuously surfaces compliance notices and personal/household bills from email — auto-uploaded to the existing DMS, auto-routed for compliance review where applicable, and queryable by internal AI agents through Model Context Protocol (MCP) tools.

**Specifically:**

1. MCP server that exposes Gmail capabilities (search, read, attachments, labels) as callable tools for internal AI agents.
2. Gmail OAuth 2.0 connection flow with offline access (refresh-token).
3. Encrypted refresh-token vault per user (extends Phase 14 Fernet pattern).
4. Background scheduled scanner that pulls matching messages and ingests attachments into DMS.
5. Compliance auto-routing — emails from regulatory authorities create `ComplianceNotice` records (Phase 9 schema).
6. Personal/household bill detection, extraction, dashboard, and pre-deadline reminders.
7. GmailFetchLog with three-state monitoring (mirrors PortalFetchLog from Phase 14).
8. Audit logging of every MCP tool invocation.

**Out of scope (explicitly):**

- Outlook / Yahoo / custom IMAP — Phase 14 PORT-05 retains the generic IMAP path.
- Business-vendor invoice ingestion — overlaps with the existing v1.0 `invoices` document category and v2.1+ AP/AR workflow; deferred.
- User-facing AI chat surface ("Ask AI about my Gmail") — internal agents only; user-facing chat is a follow-up phase.
- Outbound email — Phase 15 is read-only ingestion. No drafts, no replies sent.
- Calendar integration (Google Calendar) — covered by ALERT-10 in Phase 11.
- Gmail label management UI — minimum viable label filtering only; no label-creation surface.
- Multi-account support per user — single Gmail per user in v2.0; multi-account deferred.

</domain>

<decisions>
## Implementation Decisions (proposed seed; refine via `/gsd:discuss-phase 15`)

### MCP Server Architecture

- **D-01:** Run the Gmail MCP server as a sidecar process inside the existing backend container (not a separate microservice). Reduces deployment surface and reuses the existing FastAPI auth context. Communication over stdio for local agents and HTTP/SSE for in-cluster agents.
- **D-02:** Expose 6 MCP tools in v2.0: `gmail_search`, `gmail_read_message`, `gmail_list_attachments`, `gmail_get_attachment`, `gmail_list_labels`, `gmail_modify_labels` (read-only label modification limited to system-managed labels like `dms-ingested`).
- **D-03:** No outbound tools (`gmail_send`, `gmail_create_draft`, `gmail_reply`) in v2.0 — read-only scope eliminates a class of misuse and keeps OAuth scope minimal (`gmail.readonly` + `gmail.modify` for label-only writes).
- **D-04:** All MCP tool invocations write a row to `audit_log` with actor=user, action=`MCP_TOOL_CALL`, target=tool name, before/after capturing args (PII-redacted via Phase 9 INFRA-06 pattern). Phase 9 immutability triggers apply automatically.
- **D-05:** MCP server is gated by the same `require_compliance_permission` dependency factory introduced in Plan 09-04 — only users with the `email_integration:use` permission can connect or invoke tools.

### OAuth & Token Storage

- **D-06:** OAuth client registered as a "Web application" in Google Cloud Console with offline access. Authorized redirect URI is `${BASE_URL}/api/email/gmail/oauth/callback`. Scopes: `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.modify` (label-only writes).
- **D-07:** Refresh tokens stored in a new `gmail_credentials` table, AES-Fernet encrypted at the field level (reuses Phase 9 INFRA-06 encryption helper). Access tokens are never persisted — derived on demand from the refresh token and cached in Redis with TTL = `expires_in` minus 60s skew.
- **D-08:** Token revocation handler — when Gmail returns `invalid_grant`, mark the credential row `status=REVOKED`, disable the scanner job, and emit a `gmail.connection.lost` event (Phase 11 alert system delivers a "reconnect required" banner).
- **D-09:** Per-client OAuth — each `gmail_credentials` row is scoped to `(user_id, client_id)`. A CA managing multiple clients can connect a different Gmail per client. Cross-client read is forbidden by RLS (Phase 9 CLIENT-04).

### Ingestion Pipeline

- **D-10:** Scanner runs on APScheduler (introduced in Phase 11 via INFRA-04). Default cadence: every 15 minutes per active credential. User-configurable per credential (5min - 24hr).
- **D-11:** Filter rules stored in `gmail_filter_rules` table — `(credential_id, sender_pattern, subject_pattern, label_include, label_exclude, route_to)`. `route_to` is one of `compliance_notice`, `bill`, `dms_only`, or `ignore`.
- **D-12:** Default filter rules seeded on connect: gov.in domain → `compliance_notice`; common biller domains (`*.tatapower.com`, `airtelpayments@*`, etc.) → `bill`; everything else → ignored unless user adds a rule.
- **D-13:** Deduplication — composite UNIQUE on `(credential_id, gmail_message_id)` for messages, plus per-attachment SHA-256 hash UNIQUE within a credential. Restarting the scanner mid-run never creates duplicate records.
- **D-14:** Attachment ingestion reuses the v1.0 document upload path (`storage_service.save` → `document_tasks.process_document`) — no parallel pipeline. The Document.source_email_id FK records provenance.
- **D-15:** GmailFetchLog mirrors Phase 14 PortalFetchLog three states: `SUCCESS_EMPTY` / `SUCCESS_WITH_RESULTS` / `FETCH_FAILED`. Two consecutive `FETCH_FAILED` for the same credential triggers a Phase 11 alert.

### Compliance Auto-Routing

- **D-16:** A `compliance_notice` route invokes Phase 10 BERT classifier on the extracted email body + first attachment. Confidence ≥0.75 → auto-create `ComplianceNotice` with `Received` status and `source=gmail`. Below 0.75 → human review queue (Phase 10 CLASS-04 path).
- **D-17:** Notice metadata extraction reuses Phase 10 spaCy NER — same code path, different input source.
- **D-18:** A "View original email" deep-link on the notice detail page opens a backend endpoint that fetches the email via MCP `gmail_read_message` (no caching of email body in DB — PII minimization).

### Bill Management

- **D-19:** New `Bill` model — separate from `Document` and `ComplianceNotice` (third entity type). Reasons: bills have payment-cycle semantics (recurring, paid-state) that differ from notice-status workflow; sharing a table would muddy queries.
- **D-20:** Bill fields: `biller_name`, `biller_category` (utility/telecom/credit_card/subscription/other), `amount_due` (Decimal INR), `currency` default INR, `due_date`, `account_number_last4`, `payment_status` (pending/paid/overdue), `is_recurring`, `recurrence_period` (monthly/quarterly/annual), `parent_bill_id` for sibling linking.
- **D-21:** Extraction reuses v1.0 LLM service (`app/services/llm/extraction_service.py`) with a new bill-specific prompt template. Falls back to local regex for amount and date if LLM is unavailable.
- **D-22:** Reminders piggyback on Phase 11 alert infrastructure with a `BILL_DUE_SOON` event type (T-3, T-1, overdue tiers). Cool-down per bill: max 3 reminders.
- **D-23:** Recurring bill detection — when a new bill matches an existing bill's `(biller_name, account_number_last4)`, link via `parent_bill_id`. The scheduler also flags missing months ("expected May bill but none received") via Phase 11 anomaly detection.

### Frontend

- **D-24:** New `/dashboard/email` route tree. Top-level pages: `/email/connect` (OAuth flow), `/email/settings` (filter rules), `/email/activity` (fetch log), `/email/bills` (bill dashboard).
- **D-25:** Compliance dashboard gains a `source` filter chip (manual/portal/gmail) — reuses existing filter sidebar from Plan 09-07.
- **D-26:** Bill dashboard pattern matches v1.0 admin dashboard — stat cards (Upcoming, Due Soon, Overdue, This Month) + filterable table + bulk mark-as-paid.

### AI Agent Surface (Internal Only in v2.0)

- **D-27:** MCP tools are callable by internal compliance-routing and response-drafting agents (Phase 12) only. No user-facing chat surface in v2.0. Hard guard: MCP server binds to localhost only; no public network listener.
- **D-28:** Agent identity is the user who connected the credential — every tool call carries the user's JWT claims for RLS context.

### Claude's Discretion

All technical implementation specifics (table column types, MCP server library choice between `mcp` Python SDK / FastMCP / custom, scheduler granularity, UI component composition) are at Claude's discretion within the constraints above.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — EMAIL-01..EMAIL-10 (Email Integration), BILL-01..BILL-06 (Bill Management)

### Upstream Phases (dependencies)
- `.planning/phases/09-compliance-foundation/09-CONTEXT.md` — RBAC dependency factory, RLS pattern, audit immutability, INFRA-06 PII encryption helper
- `.planning/phases/10-ml-classification-risk-scoring/` — BERT classifier and spaCy NER (consumed by Plan 15-04)
- `.planning/phases/11-alerts-compliance-calendar/` — APScheduler + alert pipeline (consumed by Plans 15-02 and 15-03)
- `.planning/phases/14-government-portal-integration/` — PortalFetchLog three-state pattern, Fernet credential vault (mirrored by Plan 15-01 and 15-02)

### Existing Codebase
- `backend/app/models/document.py` — Document model; will gain `source_email_id` FK in Plan 15-02
- `backend/app/services/storage_service.py` — Reused for Gmail attachment uploads
- `backend/app/tasks/document_tasks.py` — Reused for Gmail attachment processing pipeline
- `backend/app/services/llm/extraction_service.py` — Reused for bill metadata extraction
- `backend/app/utils/encryption.py` (Phase 9 INFRA-06) — Fernet helpers for refresh-token encryption
- `backend/app/utils/security.py` — `require_compliance_permission` dependency factory
- `backend/app/models/audit_log.py` — Audit log used by all MCP tool invocations

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — Layered backend architecture
- `.planning/codebase/CONVENTIONS.md` — Coding conventions
- `.planning/codebase/STACK.md` — Technology stack reference
- `.planning/codebase/INTEGRATIONS.md` — External integrations inventory (Gmail joins this list)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- v1.0 document upload path (`storage_service.save` + `document_tasks.process_document` + Celery worker) — directly reused for Gmail attachment ingestion. No parallel pipeline.
- v1.0 LLM extraction service with 5-provider fallback chain — extended with a bill-specific prompt template for BILL-02.
- Phase 9 INFRA-06 Fernet encryption helper — reused for refresh-token-at-rest encryption.
- Phase 9 INFRA-07 audit log immutability triggers — automatically apply to MCP tool invocation rows.
- Phase 14 PortalFetchLog three-state pattern — copied schema for GmailFetchLog.
- Phase 11 APScheduler + alert pipeline — invoked for bill reminders and connection-lost alerts.

### Established Patterns
- FastAPI routers with `require_compliance_permission(...)` dependency factory.
- SQLAlchemy ORM with Alembic migrations under `backend/alembic/versions/`.
- Pydantic schemas in `backend/app/schemas/` matching ORM model names.
- Service-layer pattern — routers thin, business logic in `backend/app/services/`.
- Celery tasks under `backend/app/tasks/` for any work that exceeds 200ms.
- React 19 + Next.js 14 frontend with Zustand stores and axios interceptors.
- Dark-theme zinc/neutral token system (no hard-coded hex anywhere).

### Integration Points
- Backend: New `/api/email/*` route prefix; new `gmail_credentials`, `gmail_filter_rules`, `gmail_fetch_log`, `bill` tables; new `email_integration` permission.
- Backend MCP server: Runs as sidecar process started by the backend container's entrypoint.
- Frontend: New `/dashboard/email/*` route tree; bill dashboard widget on main dashboard.
- Compliance dashboard (Plan 09-07): Adds a `source` filter chip.
- Document detail page: Adds "View source email" link when `source_email_id` is set.

### Anti-patterns to Avoid
- Do not write a custom Gmail polling loop — use the official `google-api-python-client` library and APScheduler.
- Do not store access tokens in the DB — only refresh tokens, with Redis-cached access tokens.
- Do not bypass the audit log for MCP calls "for performance" — Phase 9 made audit immutable for a reason.
- Do not couple bill-detection logic to the compliance-notice classifier — they share NER but are independent classifiers.
- Do not build a generic "email provider" abstraction in v2.0 — Gmail-only per Decision D-02 of `/effort` discussion 2026-04-28.

</code_context>

<specifics>
## Specific Ideas

- Personal/household bills are the v2.0 scope — utility (electricity/water/gas), telecom (mobile/internet), credit card statements, OTT and SaaS subscriptions. Business AP invoices are explicitly deferred.
- The MCP server is **internal-only**. Hard guarded by localhost binding. User-facing AI chat ("ask AI about my bills") is a v3.0 feature.
- A single Gmail connection per user-client pair. CAs managing 20+ clients can connect a different Gmail per client.
- Default filter rules out-of-the-box: gov.in domain → compliance; known billers (state utility boards, top-3 telcos, top-5 credit cards) → bills. User can edit anytime.
- Provenance is critical — every Document and ComplianceNotice ingested via Gmail must record `source_email_id` for the "view original" deep-link and for compliance audit purposes.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-provider email MCP** — generic abstraction across Gmail / Outlook / Yahoo / IMAP. Deferred to v3.0; YAGNI for v2.0 since client only asked for Gmail.
- **User-facing AI chat surface** ("Ask AI about my Gmail") — significant UI work + agent surface area + safety review. Deferred to a follow-up phase.
- **Outbound email tools** (gmail_send, gmail_reply, gmail_create_draft) — adds blast radius and OAuth scope. Deferred until response-drafting workflow (Phase 12) needs it.
- **Business AP invoice ingestion from Gmail** — overlaps with v1.0 invoice category and a future AP/AR workflow. Deferred to v3.0.
- **Multi-account support per user** — connecting personal + work Gmail to the same user record. Deferred.
- **Gmail label-management UI** — minimum-viable label-based filtering only in v2.0. Full label CRUD deferred.
- **Calendar integration** — Google Calendar deadline events handled by Phase 11 ALERT-10, not Phase 15.

</deferred>

---

*Phase: 15-gmail-mcp-integration*
*Context seeded: 2026-04-28 — refine via `/gsd:discuss-phase 15` and `/gsd:research-phase 15` before `/gsd:plan-phase 15`*
