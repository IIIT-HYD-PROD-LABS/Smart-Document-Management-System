# Phase 15: Gmail MCP Integration & Email Document Ingestion - Context

**Gathered:** 2026-04-28 (seed) → refined 2026-05-07
**Status:** Ready for planning

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
## Implementation Decisions

### MCP Server Architecture

- **D-01:** Run the Gmail MCP server as a sidecar process inside the existing backend container (not a separate microservice). Reduces deployment surface and reuses the existing FastAPI auth context.
- **D-02:** Expose 6 MCP tools in v2.0: `gmail_search`, `gmail_read_message`, `gmail_list_attachments`, `gmail_get_attachment`, `gmail_list_labels`, `gmail_modify_labels` (read-only label modification limited to system-managed labels like `dms-ingested`).
- **D-03:** No outbound tools (`gmail_send`, `gmail_create_draft`, `gmail_reply`) in v2.0 — read-only scope eliminates a class of misuse and keeps OAuth scope minimal (`gmail.readonly` + `gmail.modify` for label-only writes).
- **D-04:** All MCP tool invocations write a row to `audit_log` with actor=user, action=`MCP_TOOL_CALL`, target=tool name, before/after capturing args (PII-redacted via Phase 9 INFRA-06 pattern). Phase 9 immutability triggers apply automatically.
- **D-05:** MCP server is gated by the same `require_compliance_permission` dependency factory introduced in Plan 09-04 — only users with the `email_integration:use` permission can connect or invoke tools.
- **D-29 [2026-05-07]:** **MCP library = FastMCP**. Decorator-based tool registration over the official `mcp` Python SDK; spec-compliant; ~5x less boilerplate per tool than raw SDK; mirrors FastAPI ergonomics. Builds on `mcp` so spec drift is impossible. (Alternatives weighed: raw `mcp` SDK — too verbose for 6 tools; custom stdio loop — no reason to re-implement protocol parsing.)
- **D-30 [2026-05-07]** **[SUPERSEDED 2026-05-07 by D-38 — see researcher reconciliation #1]:** Original decision: "Transport in v2.0 = stdio only". Superseded — see D-38. Stdio remains on shelf as v2.1 fallback if Phase 12 agents move out-of-process.
- **D-31 [2026-05-07]** **[SUPERSEDED 2026-05-07 by D-38 — see researcher reconciliation #1]:** Original decision: "MCP server lifecycle = backend entrypoint spawns child via subprocess.Popen". Superseded — see D-38. subprocess.Popen lifecycle remains on shelf as v2.1 fallback if external agent host materializes.
- **D-38 [2026-05-07]:** **MCP transport = in-memory `Client(server_instance)` from FastMCP.** Phase 12 agents share the FastAPI process — in-memory eliminates IPC + subprocess overhead, gives native exception propagation, simpler lifecycle. Supersedes D-30 (stdio) and D-31 (subprocess). Stdio + subprocess remain on shelf as v2.1 patterns if Phase 12 agents move out-of-process.

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

- **D-16 [REVISED 2026-05-07]:** **v2.0 path uses a rule-based detector, NOT BERT.** Original seed assumed BERT confidence ≥0.75 — but Phase 10 v2.0 shipped only the rule-based risk scorer; BERT classifier is deferred to v2.1.
  - **Detector signal:** sender-domain regex (`*.gov.in`, `sebi.gov.in`, `mca.gov.in`, …) AND subject keyword match (`notice|intimation|demand|scrutiny|show.cause|adjudication`).
  - **Binary confidence:** matched → auto-create ComplianceNotice with `status=Received`, `source=gmail`. Unmatched → routed to Phase 10 Review queue (CLASS-04 path).
  - **Risk scoring:** Phase 10's rule-based scorer fires unchanged on auto-created notices.
  - **v2.1 swap path:** swap one file (`gmail_classifier.py`) — schema, audit, status workflow all unchanged. The `route_to=compliance_notice` rule schema stays; only the detector function changes.
- **D-17 [REVISED 2026-05-07 — Phase 10 v2.0 deferred custom NER training; ner.py:49 raises NotImplementedError. v2.0 uses regex_patterns.py (GSTIN/PAN/CIN/section refs) + extract_with_llm() for narrative fields. v2.1 swap-in mirrors D-16's BERT pattern.]:** Notice metadata extraction reuses Phase 10 spaCy NER — same code path, different input source. Applies to body + first attachment (OCR if image/PDF) after rule-detector fires.
- **D-18:** A "View original email" deep-link on the notice detail page opens a backend endpoint that fetches the email via MCP `gmail_read_message` (no caching of email body in DB — PII minimization).
- **D-32 [NEW 2026-05-07]:** **Auto-created notice status = Received + 'Auto-imported from Gmail' badge**. Standard Phase 9 Received status — indistinguishable from manual upload at the API/audit/transition level. UI adds a small visual badge near the notice number on detail pages so compliance heads can distinguish auto from manual at a glance. No new statuses introduced (avoids Phase 9 enum migration).
- **D-33 [NEW 2026-05-07]:** **Forwarded-notice handling = route to `dms_only`**. When email matches a notice rule by content but sender-regex fails (e.g., advocate forwarding a notice from a personal Gmail), ingest as Document with `source=gmail`. No auto-ComplianceNotice creation — avoids false-positive compliance records. Compliance head manually links via Plan 09-07 link-notice UI. v2.1 BERT will handle forwarded notices via content classification, not sender pattern.

### Email Body PII Lifecycle [NEW SECTION 2026-05-07]

- **D-34 [NEW]:** **Fetch-once / classify+extract / discard.** Scanner task fetches the body once via `gmail_read_message`; runs classifier + bill extractor + NER + risk scorer in the same task; never persists raw body. Body lives only in Python locals for ~seconds. Single PII touchpoint per message. (Alternatives weighed: per-operation refetch — multiplies Gmail quota + audit volume; Redis cache — leaves PII at rest even briefly.)
- **D-35 [NEW]:** **Audit log = one row per `MCP_TOOL_CALL` with body SHA-256.** Schema: `actor_id`, `action='MCP_TOOL_CALL'`, `target=tool_name`, `args={message_id, body_sha256, attachment_ids[], attachment_sha256s[]}`. Provable tampering detection without storing the body. Phase 9 INFRA-07 immutability triggers apply automatically.
- **D-36 [NEW]:** **Audit-arg redaction = bodies + attachments + subjects + senders all PII-redacted; keep IDs + SHA-256.** Reuses Phase 9 INFRA-06 PII helper (battle-tested). No raw email content, subject lines, or sender names ever in audit trail. Even sender domain only — not full address. (Trade-off accepted: marginally harder incident triage, decisively cleaner privacy posture.)

### Bill Management

- **D-19 [REFINED 2026-05-07]:** **Hybrid Bill data model.** New `bills` table holds payment-cycle metadata (status workflow, recurrence, `parent_bill_id`). Optional `source_document_id` FK → `documents.id` when a PDF is attached. PDF storage stays in `documents` (single storage path); bill-specific queries stay clean. **Bills WITHOUT attachments** (text-only billers like "Your bill is ₹X due Y") have `source_document_id=NULL` — encoded cleanly in schema; future analytics can join on it.
- **D-20:** Bill fields: `biller_name`, `biller_category` (utility/telecom/credit_card/subscription/other), `amount_due` (Decimal INR), `currency` default INR, `due_date`, `account_number_last4`, `payment_status` (pending/paid/overdue), `is_recurring`, `recurrence_period` (monthly/quarterly/annual), `parent_bill_id` for sibling linking, plus **`source_document_id`** (FK, nullable, per D-19 refinement) and **`source_email_id`** (FK to gmail_message_log).
- **D-21:** Extraction reuses v1.0 LLM service (`app/services/llm/extraction_service.py`) with a new bill-specific prompt template. Falls back to local regex for amount and date if LLM is unavailable.
- **D-22:** Reminders piggyback on Phase 11 alert infrastructure with a `BILL_DUE_SOON` event type (T-3, T-1, overdue tiers). Cool-down per bill: max 3 reminders per lifetime. **Marking paid stops further reminders. Un-marking paid does NOT reset the count** — prevents accidental-toggle reminder spam.
- **D-23:** Recurring bill detection — when a new bill matches an existing bill's `(biller_name, account_number_last4)`, link via `parent_bill_id`. Biller name normalized via regex (lowercase + whitespace + common suffix stripping: `LTD|LIMITED|PRIVATE|PVT`). The scheduler also flags missing months ("expected May bill but none received") via Phase 11 anomaly detection.
- **D-37 [NEW 2026-05-07]:** **Bill detail page = `/dashboard/email/bills/[id]`**. Renders payment status, due date, biller info, recurrence parent/children list, link to source PDF (if `source_document_id` set), link to source email (via `gmail_read_message` MCP deep-link). Deep-linkable URL preserved for sharing within team.

### Frontend

- **D-24:** New `/dashboard/email` route tree. Top-level pages: `/email/connect` (OAuth flow), `/email/settings` (filter rules), `/email/activity` (fetch log), `/email/bills` (bill dashboard).
- **D-25:** Compliance dashboard gains a `source` filter chip (manual/portal/gmail) — reuses existing filter sidebar from Plan 09-07. **Same chip applied to `/dashboard/documents/*` listings** — Documents now has 3 source types post-Phase-15 (manual upload / portal / gmail), so the chip belongs there too.
- **D-26:** Bill dashboard pattern matches v1.0 admin dashboard — stat cards (Upcoming, Due Soon, Overdue, This Month) + filterable table + bulk mark-as-paid.

### AI Agent Surface (Internal Only in v2.0)

- **D-27 [SUPERSEDED by D-30]:** Original "MCP server binds to localhost only; no public network listener." Now structural: D-30's stdio-only choice means there is no listener at all. Internal-only is enforced by the absence of a network surface, not a binding rule.
- **D-28 [REFINED 2026-05-07]:** Agent identity = the user who connected the credential. Implementation under D-30's stdio transport: the MCP child process inherits the parent backend's authority. Each tool call's caller (a Phase 12 agent) passes the originating user's `client_id` + `user_id` as call args (validated server-side by `require_compliance_permission`). RLS context set via `set_config('app.current_client_id', ...)` before any DB read inside the tool body.

### Claude's Discretion

The following are at Claude's discretion within the constraints above:

- Scanner cadence default tuning (seed D-10 says 15min per credential — may adjust based on Gmail quota analysis or alert noise data; exposed as user-configurable 5min-24hr regardless)
- Pydantic schemas for MCP tool args (FastMCP's auto-derivation from Python type hints is acceptable; explicit Pydantic models for tools that need stricter validation)
- MCP error envelope format (FastMCP defaults — return type-annotated exceptions; uniform with HTTPException pattern from FastAPI)
- Bill `payment_method` enum starting set: `upi | netbanking | card | cash | cheque | autopay | other` (extensible via migration if needed)
- Bill detail page layout details (cards-with-stat pattern from v1.0 documents)
- Gmail label management UX in v2.0 (auto-apply `dms-ingested` label silently; surface to user only if they create a filter rule that involves a label)
- LLM prompt versioning for bill extraction (`bills.extraction_prompt_rev` field — string semver of the prompt template used)
- Migration ordering relative to Phase 14 (Phase 14a may ship first; Phase 15 migrations must be additive only — no Phase 14 schema dependencies in earlier migrations)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements

- `.planning/REQUIREMENTS.md` §EMAIL-01..EMAIL-10 (Email Integration acceptance criteria)
- `.planning/REQUIREMENTS.md` §BILL-01..BILL-06 (Bill Management acceptance criteria)
- `.planning/PROJECT.md` — vision, principles, non-negotiables

### Upstream Phases (dependencies)

- `.planning/phases/09-compliance-foundation/09-CONTEXT.md` — RBAC dependency factory, RLS pattern, audit immutability triggers, INFRA-06 PII encryption helper
- `.planning/phases/10-ml-classification-risk-scoring/10-CONTEXT.md` — Phase 10 v2.0 shipped rule-based scorer only (BERT deferred); review queue infra (CLASS-04); spaCy NER pattern
- `.planning/phases/11-alerts-and-calendar/11-CONTEXT.md` — APScheduler integration, alert pipeline, BILL_DUE_SOON event type slot
- `.planning/phases/12-response-drafting-evidence/12-CONTEXT.md` — Phase 12 agents are the primary internal MCP consumers
- `.planning/phases/13-elasticsearch-search-reporting/13-CONTEXT.md` — search indexing strategy (Gmail-ingested docs feed the same FTS pipeline)
- `.planning/phases/14-portal-integration/14-CONTEXT.md` — PortalFetchLog three-state pattern (mirrored by GmailFetchLog), Fernet credential vault pattern (extended for refresh-token storage)

### Existing Codebase

- `backend/app/models/document.py` — Document model; gains `source_email_id` FK in Plan 15-02
- `backend/app/services/storage_service.py` — Reused for Gmail attachment uploads (D-14)
- `backend/app/tasks/document_tasks.py` — Reused for Gmail attachment processing pipeline (D-14)
- `backend/app/services/llm/extraction_service.py` — Reused for bill metadata extraction (D-21)
- `backend/app/utils/encryption.py` — Phase 9 INFRA-06 Fernet helpers for refresh-token-at-rest encryption (D-07)
- `backend/app/utils/security.py` — `require_compliance_permission` dependency factory (D-05)
- `backend/app/models/audit_log.py` — Audit log used by all MCP tool invocations (D-04, D-35, D-36)
- `backend/app/compliance/services/scheduler.py` — Phase 11 APScheduler integration (D-10)
- `backend/app/ml/datasets/scrape_sebi.py` — pattern for content scrapers (analogue for body classification rules)

### Architecture / Conventions

- `.planning/codebase/ARCHITECTURE.md` — Layered backend architecture (router → service → repo)
- `.planning/codebase/CONVENTIONS.md` — Coding conventions
- `.planning/codebase/STACK.md` — Technology stack reference
- `.planning/codebase/INTEGRATIONS.md` — External integrations inventory (Gmail joins this list)
- `.planning/codebase/TESTING.md` — Test conventions; Phase 15 tests follow Phase 9 RLS-fixture pattern

### MCP Spec / Library Docs (downstream researcher should fetch via Context7)

- Anthropic MCP specification — protocol, tool schema, capability negotiation
- FastMCP docs — decorator API, transport configuration, error handling

### Cross-Phase Auth Gotcha (surfaced 2026-05-07 Phase 11 smoke)

- `frontend/src/hooks/useNotificationStream.ts:43` — JWT now in httpOnly cookies; localStorage-read pattern is broken. Phase 15 must NOT repeat this drift in any user-facing OAuth callback handling. Cookie-based session is the source of truth for browser-side identity; MCP tool calls inherit identity via parent backend process under D-30/D-31, not via client-side token.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- v1.0 document upload path (`storage_service.save` + `document_tasks.process_document` + Celery worker) — directly reused for Gmail attachment ingestion. No parallel pipeline.
- v1.0 LLM extraction service with 5-provider fallback chain — extended with a bill-specific prompt template for BILL-02.
- Phase 9 INFRA-06 Fernet encryption helper — reused for refresh-token-at-rest encryption.
- Phase 9 INFRA-07 audit log immutability triggers — automatically apply to MCP tool invocation rows.
- Phase 14 PortalFetchLog three-state pattern — copied schema for GmailFetchLog (when Phase 14a lands; Phase 15 may bring this schema first if 14 slips).
- Phase 11 APScheduler + alert pipeline — invoked for bill reminders and connection-lost alerts.
- Phase 9 `require_compliance_permission` factory — gates MCP tool registration + invocation.

### Established Patterns

- FastAPI routers with `require_compliance_permission(...)` dependency factory.
- SQLAlchemy ORM with Alembic migrations under `backend/alembic/versions/`.
- Pydantic schemas in `backend/app/schemas/` matching ORM model names.
- Service-layer pattern — routers thin, business logic in `backend/app/services/`.
- Celery tasks under `backend/app/tasks/` for any work that exceeds 200ms.
- React 19 + Next.js 14 frontend with Zustand stores and axios interceptors.
- Dark-theme zinc/neutral token system (no hard-coded hex anywhere).
- httpOnly-cookie JWT auth (post-Phase-9 refactor).

### Integration Points

- Backend: New `/api/email/*` route prefix; new `gmail_credentials`, `gmail_filter_rules`, `gmail_fetch_log`, `gmail_message_log`, `bills` tables; new `email_integration` permission.
- Backend MCP server: Runs as `subprocess.Popen` child of the FastAPI app (D-31), stdio transport (D-30), FastMCP library (D-29).
- Frontend: New `/dashboard/email/*` route tree; bill dashboard widget on main dashboard.
- Compliance dashboard (Plan 09-07): Adds a `source` filter chip.
- Documents listing pages: Add same `source` filter chip (per D-25 extension).
- Document detail page: Adds "View source email" link when `source_email_id` is set.

### Anti-patterns to Avoid

- Do not write a custom Gmail polling loop — use the official `google-api-python-client` library and APScheduler.
- Do not store access tokens in the DB — only refresh tokens, with Redis-cached access tokens.
- Do not bypass the audit log for MCP calls "for performance" — Phase 9 made audit immutable for a reason.
- Do not couple bill-detection logic to the compliance-notice classifier — they share NER but are independent classifiers.
- Do not build a generic "email provider" abstraction in v2.0 — Gmail-only per Decision D-02 of `/effort` discussion 2026-04-28.
- Do not read JWT from `localStorage` in any new code — auth is in httpOnly cookies (Phase 11 lesson).
- Do not cache email bodies anywhere — D-34 (fetch-once-discard) is the only allowed pattern.

</code_context>

<specifics>
## Specific Ideas

- Personal/household bills are the v2.0 scope — utility (electricity/water/gas), telecom (mobile/internet), credit card statements, OTT and SaaS subscriptions. Business AP invoices are explicitly deferred.
- The MCP server is **internal-only**. v2.0: stdio-only transport means no listener at all (structural enforcement); D-27's localhost-binding rule becomes moot. User-facing AI chat ("ask AI about my bills") is a v3.0 feature.
- A single Gmail connection per user-client pair. CAs managing 20+ clients can connect a different Gmail per client.
- Default filter rules out-of-the-box: gov.in domain → compliance; known billers (state utility boards, top-3 telcos, top-5 credit cards) → bills. User can edit anytime.
- Provenance is critical — every Document and ComplianceNotice ingested via Gmail must record `source_email_id` for the "view original" deep-link and for compliance audit purposes.
- v2.0 ships rule-based compliance detector (D-16 revised); v2.1 swaps in BERT (Phase 10 unfinished work). Schema and status workflow unchanged across the swap.
- All audit args containing email metadata are PII-redacted (D-36) — even sender names and subjects. Tribunal-grade privacy posture.

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
- **MCP HTTP/SSE transport** — D-30 ships stdio only. HTTP/SSE listener deferred to v2.1 (when external/in-cluster agents arrive).
- **BERT-based compliance classifier** — D-16 revised; rule-based detector ships in v2.0. BERT swap-in in v2.1 (Phase 10 v2.1 work).
- **Forwarded-notice content classification** — D-33 routes forwarded notices to dms_only in v2.0. v2.1 BERT classifier handles content-based detection regardless of sender.
- **Auto-Received pre-acknowledgement status** — considered as a 6th notice status but rejected (D-32) in favor of a UI badge to avoid Phase 9 enum migration.

</deferred>

---

*Phase: 15-gmail-mcp-integration*
*Context seeded 2026-04-28; refined 2026-05-07 via discuss-phase 15 (4 gray areas, 12 new decisions: D-29..D-37 + revised D-16, D-19, D-22, D-25, D-28)*
*Revised 2026-05-07 (revision iteration 1): D-30 + D-31 superseded by D-38 (in-memory transport per researcher reconciliation #1); D-17 revised note added (Phase 10 v2.0 deferred custom NER training).*
*Next: `/gsd:plan-phase 15` (or `/gsd:research-phase 15` first if FastMCP / Gmail API spec details warrant a research pass)*
