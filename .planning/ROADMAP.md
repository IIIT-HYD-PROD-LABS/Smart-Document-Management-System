# Roadmap: Smart Document Management & Compliance System

## Milestones

- **v1.0 Smart Document Management System** -- Phases 1-8 (shipped 2026-03-30) | [Archive](milestones/v1.0-ROADMAP.md)
- **v2.0 Compliance Management System** -- Phases 9-13, 15, 17 shipped; Phase 16 BYOK shipped under v2.1; Phase 14 portal integration remains blocked on GSP empanelment plus IT API access decisions

## Phases

<details>
<summary>v1.0 Smart Document Management System (Phases 1-8) -- SHIPPED 2026-03-30</summary>

Phases 1-8 shipped. See archived roadmap: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

42/42 requirements validated across 8 phases.

</details>

### v2.0 Compliance Management System

**Milestone Goal:** Add AI-powered compliance notice management for Indian regulatory authorities to the existing document management system, with BERT-based classification, risk scoring, AI-assisted response drafting, multi-channel alerts, full audit trails, and Gmail MCP integration for direct email-to-DMS ingestion of notices and bills.

- [x] **Phase 9: Compliance Foundation** ✅ Shipped 2026-04-28 - Notice lifecycle, extended RBAC, client/entity management, immutable audit infrastructure
- [~] **Phase 10: ML Classification + Risk Scoring** v2.0 CODE-COMPLETE 2026-05-05 + smoke PASSED — BERT empirical bake-off + spaCy custom NER deferred to v2.1 (depend on labeled data)
- [~] **Phase 11: Alert System + Compliance Calendar** v2.0 CODE-COMPLETE 2026-05-05 — APScheduler + email + WebSocket; SMS scaffolded (Twilio disabled until DLT registration); SendGrid migration + ICS export + severity-weighted compliance score deferred to v2.1
- [~] **Phase 12: Response Drafting + Evidence Management** v2.0 CODE-COMPLETE 2026-05-05 + smoke PASSED — 4-stage approval workflow (Drafter → Reviewer → Legal → CFO) + versioned drafts + evidence linking + frontend response editor; LLM draft generation + 20+ response templates + evidence PDF merge + GST ITC reconciliation + regulation library deferred to v2.1
- [~] **Phase 13: Elasticsearch + Cross-Entity Search + Reporting** v2.0 CODE-COMPLETE 2026-05-05 + smoke PASSED — PG-FTS-backed unified search across notices + documents + reports analytics (penalty by authority + volume by status + response time percentiles); Elastic Cloud + outbox + reconciliation deferred to v2.1
- [ ] **Phase 14: Government Portal Integration** — GST/IT/MCA auto-fetch, RBI/SEBI scraping, IMAP email parsing — CONTEXT seeded 2026-05-05; **BLOCKED on external decisions: GSP empanelment status, IT e-filing API access path**
- [x] **Phase 15: Gmail MCP Integration & Email Document Ingestion** — Gmail OAuth + MCP server, auto-ingest notice/bill attachments — 7 plans planned 2026-05-07 (completed 2026-05-07)
- [x] **Phase 16: BYOK AI Assistant (v2.1)** — per-tenant Anthropic / Gemini key, Fernet-encrypted, scope-locked SYSTEM prompt, 5 task surfaces (notice summary + recommended actions, invoice summary + suggested actions + payment timing) — shipped 2026-05-08
- [x] **Phase 17: AI Notice Field Extraction, BYOK (v2.0)** — upload-first flow on `/dashboard/compliance/notices/new` that extracts 14 canonical fields via the tenant's Phase 16 key, conjunctive 0.85 routing gate (average + notice_number + authority), structural validators for GSTIN / PAN / CIN / ISO dates / liability arithmetic that halve confidence on shape failure, PII-redacted audit chain (`notice_ai_extract` + `notice_ai_extract_accepted`), provenance disclosure on the detail page — 7 plans, shipped 2026-05-25
- [x] **Phase 18: AI Notice Response Drafting, BYOK (v2.0)** — `POST /api/compliance/ai/notice-response-draft/{notice_id}` generates a markdown reply draft for any user with NOTICE_DRAFT_RESPONSE (legal_team, ca_consultant, staff), reusing the Phase 16 scope-locked SYSTEM prompt and the Phase 17 extracted_fields envelope as structured context, with PII-redacted `notice_ai_draft` audit rows that hash both the draft body and the user guidance — 1 plan, shipped 2026-05-25 (smoke 10/10 PASS)

## Phase Details

### Phase 9: Compliance Foundation
**Goal**: Users can manually track compliance notices end-to-end with full audit trail, multi-client support, and role-based access control
**Depends on**: v1.0 (existing auth, RBAC, OCR, document system)
**Requirements**: LIFE-01, LIFE-02, LIFE-03, LIFE-04, LIFE-05, LIFE-06, LIFE-07, LIFE-08, AUDIT-01, AUDIT-02, RBAC-01, RBAC-02, RBAC-03, RBAC-04, RBAC-05, RBAC-06, CLIENT-01, CLIENT-02, CLIENT-03, CLIENT-04, CLIENT-05, CLIENT-06, CLIENT-07, INFRA-05, INFRA-06, INFRA-07
**Success Criteria** (what must be TRUE):
  1. User can upload a compliance notice (PDF/JPG/PNG) and manually enter its metadata (number, authority, date, deadline, penalty) — the notice appears in the dashboard scoped to the correct client
  2. User can move a notice through the full status workflow (Received → Under Review → Response Drafted → Submitted → Resolved/Dismissed) and link related notices in a chain
  3. User can filter and search notices by authority, type, status, risk level, deadline, and GSTIN/PAN; bulk-update status for multiple notices at once
  4. Every notice action is recorded in an immutable, timestamped audit log — no application user (including admins) can alter or delete an audit record
  5. A CA/Tax Consultant user can manage multiple client entities (each with distinct GSTINs/PANs) and see a per-client aggregate dashboard with zero cross-client data leakage
  6. All six roles (Compliance Head, Legal Team, Finance Team, Auditor, CA/Consultant, Staff) enforce correct permission boundaries — an Auditor cannot edit, a Staff member cannot approve/submit
**Plans**: 7 plans
- [x] 09-01-PLAN.md — Wave 0 test infrastructure (RLS isolation, audit immutability, RBAC matrix, fixtures, validation contract)
- [x] 09-02-PLAN.md — Wave 1 DB foundations (5 migrations: schema/audit-immutability/RLS/calendar-seed/DB-roles + Indian validators + PII encryption + permission registry + state machine)
- [x] 09-03-PLAN.md — Wave 2 backend models + services (5 ORM modules, 4 schemas, 4 services + migration 0018 RLS recursion fix)
- [x] 09-04-PLAN.md — Wave 3 backend middleware + RBAC dependencies (tenant context, auditor expiry, require_compliance_permission)
- [x] 09-05-PLAN.md — Wave 4 backend routers (7 routers under /api/compliance)
- [x] 09-06-PLAN.md — Wave 5 frontend foundation (client switcher, 4-step onboarding wizard, team management)
- [ ] 09-07-PLAN.md — Wave 6 frontend notice surfaces (dashboard, detail, bulk actions, audit viewer, reports, README)
**UI hint**: yes

### Phase 10: ML Classification + Risk Scoring
**Goal**: Notices are automatically classified into 40+ types across 5 authorities, entities are extracted via NER, and every notice receives an XGBoost risk score with SHAP explanations — all without degrading existing v1.0 document processing performance
**Depends on**: Phase 9
**Requirements**: CLASS-01, CLASS-02, CLASS-03, CLASS-04, CLASS-05, CLASS-06, CLASS-07, CLASS-08, RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, INFRA-01
**Success Criteria** (what must be TRUE):
  1. An uploaded notice is automatically classified into one of 40+ types across GST, IT, MCA, RBI, and SEBI — classification accuracy on the held-out test set is >92%
  2. Each classification shows a confidence score; notices below 0.75 confidence are routed to a human review queue instead of auto-assigned
  3. spaCy NER extracts structured fields (notice number, date, authority, deadline, penalty, legal sections) with regex-first extraction for GSTIN/PAN/CIN patterns
  4. Every notice receives an automated risk score (0-100) with a Critical/High/Medium/Low tier label; the top 3 risk factors are displayed via SHAP explanations
  5. Critical-risk notices trigger automatic escalation to the Compliance Head role
  6. ML inference runs in the dedicated 2GB `compliance` Celery worker — uploading a document via the existing v1.0 flow shows no measurable latency regression
**Plans**: 3 plans landed for v2.0 (10-01 review queue backend, 10-02 auto-escalation, 10-03 frontend SHAP UI); v2.1 plan slot reserved for BERT bake-off + active learning. See `.planning/phases/10-ml-classification-risk-scoring/10-RESEARCH-FINAL.md` for v2.0/v2.1 split rationale.
- [x] 10-01-PLAN.md — Review queue backend (NoticeReviewQueue ORM + service + router + NOTICE_REVIEW permission + tests)
- [x] 10-02-PLAN.md — Auto-escalation on Critical risk (escalation.py + activity timeline + immutable audit log + tests)
- [x] 10-03-PLAN.md — Frontend SHAP UI (ConfidenceBadge + WhyThisRiskScore + RiskTierDot upgrade + review queue page + sidebar nav)
- [ ] 10-04-PLAN.md (v2.1) — BERT empirical bake-off + spaCy custom NER + active learning loop (deferred — depends on 200+ hand-labeled real notices)
**UI hint**: yes

### Phase 11: Alert System + Compliance Calendar
**Goal**: No compliance deadline is silently missed — users receive tiered alerts (email, SMS, in-app) at T-7/T-3/T-1 before deadlines, and a compliance calendar shows all Indian statutory filing deadlines for each client entity
**Depends on**: Phase 10
**Requirements**: ALERT-01, ALERT-02, ALERT-03, ALERT-04, ALERT-05, ALERT-06, ALERT-07, ALERT-08, ALERT-09, ALERT-10, CAL-01, CAL-02, CAL-03, CAL-04, CAL-05, CAL-06, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. User receives email via SendGrid when a new notice is ingested or a notice changes status; SMS via Twilio fires only for Critical/High-priority notices
  2. T-7, T-3, and T-1 day reminder emails fire automatically before each notice deadline; an overdue alert fires post-deadline with calculated penalty
  3. In-app notifications appear in real time via WebSocket without a page refresh; the connection auto-reconnects on drop
  4. User can configure custom alert rules per notice type (channel, threshold, recipient hierarchy) including a configurable escalation chain (Staff → Senior → Compliance Head → CFO)
  5. The compliance calendar shows pre-loaded Indian statutory deadlines (GSTR-1/3B/9, TDS quarters, Advance Tax, ITR, ROC filings) filtered to the entity's applicable obligations, with monthly/weekly views and filing status indicators
  6. Deadline calculations account for Indian gazetted holidays and CBDT/CBIC circular extensions — a deadline never lands on a non-working day without adjustment
**Plans**: TBD
**UI hint**: yes

### Phase 12: Response Drafting + Evidence Management
**Goal**: Users can draft, review, approve, and assemble complete notice responses — including LLM-generated drafts, GST reconciliation exhibits, linked DMS evidence, and a searchable regulation library — without leaving the compliance system
**Depends on**: Phase 11
**Requirements**: RESP-01, RESP-02, RESP-03, RESP-04, RESP-05, RESP-06, EVID-01, EVID-02, EVID-03, EVID-04, RECON-01, RECON-02, RECON-03, RECON-04, RECON-05, REG-01, REG-02, REG-03, REG-04
**Success Criteria** (what must be TRUE):
  1. User can generate an LLM-assisted response draft from a notice template (20+ types with variable substitution) — each save creates a versioned snapshot with full rollback capability
  2. A response moves through multi-stage approval (Drafter → Reviewer → Legal → CFO) — each stage approval/rejection is immutably recorded and the notice cannot advance to Submitted until all required approvals are granted
  3. User can attach existing DMS documents as evidence exhibits to a notice response and assemble them into a single merged PDF with table of contents; an auto-suggested evidence checklist appears based on notice type
  4. User can upload GSTR-2A/2B and GSTR-3B JSON files to generate an ITC reconciliation report (mismatch analysis, blocked credits under Section 17(5)) that can be attached as a response exhibit
  5. User can search the regulation library (GST Act, IT Act, Companies Act, FEMA, SEBI regulations, CBDT/CBIC circulars) and see regulation-to-notice-type mappings with version history for changes
**Plans**: TBD
**UI hint**: yes

### Phase 13: Elasticsearch + Cross-Entity Search + Reporting
**Goal**: Users can search across all notices and documents in a single query, and compliance reports use aggregated analytics powered by Elasticsearch — with automatic fallback to PostgreSQL FTS if Elasticsearch is unavailable
**Depends on**: Phase 12
**Requirements**: INFRA-02, EVID-05, AUDIT-03, AUDIT-04, AUDIT-05, AUDIT-06, AUDIT-07
**Success Criteria** (what must be TRUE):
  1. A single search query returns ranked results spanning both compliance notices and DMS documents — results include authority, status, risk level, and document type facets
  2. User can find DMS documents relevant to a specific notice using cross-system search (e.g., invoices matching a GST ITC dispute)
  3. Compliance reports (by authority, type, status), penalty analysis, response time analytics, and compliance health score render with sub-3-second page loads using Elasticsearch aggregations
  4. If Elasticsearch is unavailable, the dashboard and search fall back to PostgreSQL FTS automatically — users see a degraded-mode indicator but all data remains accessible
  5. The ES index stays consistent with PostgreSQL via the transactional outbox pattern; a daily reconciliation job detects and repairs any index drift
**Plans**: TBD

### Phase 14: Government Portal Integration + Reconciliation Engine
**Goal**: Notices from GST, Income Tax, and MCA portals are auto-fetched on a schedule, RBI/SEBI public notices are scraped, and non-Gmail email inboxes are parsed via IMAP — all with encrypted credential storage, fetch health monitoring, and duplicate prevention
**Depends on**: Phase 13
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, PORT-05, PORT-06, PORT-07, PORT-08
**Success Criteria** (what must be TRUE):
  1. Notices from GST portal (GSTIN-based), Income Tax e-filing portal (PAN-based), and MCA portal (CIN-based) are automatically fetched on a configurable schedule and appear in the compliance dashboard without manual upload
  2. RBI and SEBI public enforcement notices are scraped and ingested; the scraper detects redirect-to-login and marks the run as FETCH_FAILED rather than SUCCESS_EMPTY
  3. An IMAP-connected email account (Outlook/Yahoo/custom — Gmail is owned by Phase 15) captures compliance notices sent to official email addresses and routes them through the standard ingestion pipeline
  4. Every portal fetch run creates a PortalFetchLog entry with a three-state result (SUCCESS_EMPTY / SUCCESS_WITH_RESULTS / FETCH_FAILED); admins receive an alert after two consecutive FETCH_FAILED runs for any portal
  5. Portal credentials (GST API keys, email passwords) are stored encrypted (Fernet) in the database; no credentials appear in application logs, Celery task arguments, or Elasticsearch source fields
  6. Duplicate notices are prevented by a database UNIQUE constraint plus Redis distributed lock — restarting the portal poller during a partial run never creates duplicate notice records
**Plans**: TBD

### Phase 15: Gmail MCP Integration & Email Document Ingestion
**Goal**: A user connects Gmail once and the system continuously surfaces compliance notices and personal/household bills from email — auto-uploaded to DMS, auto-routed for compliance review, queryable by internal AI agents via MCP tools — without manual forwarding or copy-paste
**Depends on**: Phase 9 (RBAC, audit, RLS, INFRA-06 encryption), Phase 10 (BERT classifier + spaCy NER for notice routing), Phase 11 (APScheduler + alert pipeline for bill reminders), Phase 14 (Fernet credential vault and PortalFetchLog three-state pattern)
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05, EMAIL-06, EMAIL-07, EMAIL-08, EMAIL-09, EMAIL-10, BILL-01, BILL-02, BILL-03, BILL-04, BILL-05, BILL-06
**Success Criteria** (what must be TRUE):
  1. A user can connect their Gmail account via OAuth 2.0 with offline access, and refresh tokens are stored Fernet-encrypted at rest with no plaintext leakage in logs, Celery args, or Elasticsearch source fields
  2. The system exposes Gmail as 6 callable MCP (Model Context Protocol) tools — `gmail_search`, `gmail_read_message`, `gmail_list_attachments`, `gmail_get_attachment`, `gmail_list_labels`, `gmail_modify_labels` — accessible only to internal compliance and response-drafting agents (localhost-bound, no public surface)
  3. A configurable scheduled scanner pulls matching messages every 15 minutes (per-credential cadence 5min-24hr) and ingests attachments into the existing DMS via the v1.0 upload pipeline, with deduplication via Gmail message-id UNIQUE + per-attachment SHA-256 hash
  4. Emails from regulatory authorities auto-create ComplianceNotice records (Phase 9 schema) with `source=gmail`, classified via the Phase 10 BERT pipeline; low-confidence (<0.75) routes to the human review queue
  5. Personal/household bills (utility, telecom, credit card, OTT/SaaS subscriptions) are auto-detected, metadata-extracted via the v1.0 LLM service, and surfaced in a bill dashboard with Upcoming/Due Soon/Overdue/Paid filters and T-3/T-1/overdue reminders via Phase 11 alerts
  6. Every MCP tool invocation writes an immutable audit_log row (Phase 9 INFRA-07); two consecutive FETCH_FAILED runs trigger a Phase 11 alert; OAuth token revocation auto-disables the scanner and surfaces a "reconnect required" UI banner
  7. A "View source email" deep-link on every Gmail-ingested Document and ComplianceNotice fetches the email body via MCP at view-time without persisting it (PII minimization)
**Plans**: 7 plans
- [x] 15-01-PLAN.md — Wave 0 test infrastructure (17 backend + 4 frontend stub tests, conftest fixtures, requirements pinning)
- [x] 15-02-PLAN.md — Wave 1 DB foundations (alembic 0025: 5 tables + RLS, ORM models, Pydantic schemas, permission, alert types)
- [x] 15-03-PLAN.md — Wave 2A services (oauth, vault, access cache, scanner, classifier with rbi.org.in, bill extractor + bill service + ingestion + scanner_task)
- [x] 15-04-PLAN.md — Wave 2B MCP server (FastMCP with 6 tools + in-memory client per reconciliation #1 + lifespan handler in main.py)
- [x] 15-05-PLAN.md — Wave 3A backend routers (7 routers under /api/email gated by email_integration:use)
- [x] 15-06-PLAN.md — Wave 3B frontend (typed email-api + 7 components + 6 pages + sidebar nav; reconciliation #3 enforced — js-cookie not localStorage)
- [x] 15-07-PLAN.md — Wave 4 smoke + manual checklist (12 automated checks + 12-step manual verification)
**UI hint**: yes

### Phase 17: AI Notice Field Extraction (Zero-Shot, BYOK)
**Goal**: A user drops a notice PDF, JPG, or PNG on `/dashboard/compliance/notices/new` and the system extracts the canonical compliance fields using the tenant's Phase 16 BYOK key, pre-populates the create-notice form with per-field confidence indicators, and on low confidence routes the artefact to the Phase 10 review queue. The Gmail ingestion path uses the same extractor so behaviour is identical regardless of source.
**Depends on**: Phase 9 (RBAC, audit immutability, RLS, PII encryption), Phase 10 (`NoticeReviewQueue`), Phase 15 (`process_classified_email` hook), Phase 16 (`AICredential`, `build_provider`, scope-locked SYSTEM prompt)
**Requirements**: EXTRACT-01, EXTRACT-02, EXTRACT-03, EXTRACT-03b, EXTRACT-04, EXTRACT-05, EXTRACT-06, EXTRACT-07, EXTRACT-08, EXTRACT-09, EXTRACT-10, EXTRACT-11, EXTRACT-12
**Success Criteria** (what must be TRUE):
  1. A user uploads a GST DRC-01 PDF on `/dashboard/compliance/notices/new` and within 10 seconds sees the form pre-populated with at least notice_number, authority, issued_date, and response_deadline, each carrying a visible confidence indicator
  2. Each pre-populated field can be accepted as-is, edited inline, or discarded before Save; edits are recorded in the audit log against the same notice id
  3. A low-confidence extraction (average below 0.85, OR notice_number below 0.85, OR authority below 0.85) routes the upload to the existing Phase 10 review queue; a structurally invalid GSTIN / PAN / CIN / date counts as a confidence downgrade per D-33
  4. Gmail-ingested notices arrive with extracted fields already populated and the same provenance disclosure is visible on the notice detail page
  5. Tenants without an `AICredential` configured see a quiet inline banner and can still upload and fill manually; no 500s, no broken state
  6. Every extraction call writes exactly one `audit_log` row with action `notice_ai_extract` containing provider, model, latency, average confidence, and body SHA-256 (no raw text, no extracted values)
  7. RLS isolation holds: an extraction artefact on a notice in client A is invisible to a user authenticated against client B
  8. The Phase 9 audit immutability trigger refuses any UPDATE or DELETE attempt on extraction audit rows (verified by an automated test, not a manual probe)
  9. Smoke script (`scripts/smoke_phase17_v20.py`) passes end to end against a real provider call
**Plans**: 7 plans
- [x] 17-01-PLAN.md — Wave 0 test infrastructure (8 backend pytest stubs + 3 frontend vitest stubs + extraction fixtures gating Plans 02-07)
- [x] 17-02-PLAN.md — Wave 1 schema (migration 0034, 5 columns, status CHECK, confidence CHECK, partial index, Pydantic schemas, NOTICE_AI_EXTRACT permission)
- [x] 17-03-PLAN.md — Wave 2 extractor service (`extract_notice_fields`, prompt module, structural validator, routing helper)
- [x] 17-04-PLAN.md — Wave 3 wiring (Celery `process_document_task` + Gmail `process_classified_email` + first-upload-wins guard)
- [x] 17-05-PLAN.md — Wave 4 routers (extract-preview, get-extraction, accept-extraction; rate limit; 412 on no credential)
- [x] 17-06-PLAN.md — Wave 5 upload-first UI (`ExtractionPreviewForm`, `ExtractedFieldRow`, provenance disclosure)
- [x] 17-07-PLAN.md — Wave 6 smoke + README + ROADMAP + STATE + SUMMARY (smoke 12/12 PASS on 2026-05-25)
**UI hint**: yes

## Progress

**Execution Order:** Phases execute in numeric order: 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 9. Compliance Foundation | v2.0 | 7/7 | ✅ Shipped | 2026-04-28 |
| 10. ML Classification + Risk Scoring | v2.0 | 3/3 v2.0 + 0/1 v2.1 | v2.0 CODE-COMPLETE + smoke PASSED; v2.1 deferred (BERT bake-off + active learning) | 2026-05-05 |
| 11. Alert System + Compliance Calendar | v2.0 | 1/1 v2.0 + 0/N v2.1 | v2.0 CODE-COMPLETE + hardening pass shipped; v2.1 deferred (SendGrid + DLT SMS + per-user prefs + ICS export) | 2026-05-05 |
| 12. Response Drafting + Evidence Management | v2.0 | 1/1 v2.0 + 0/N v2.1 | v2.0 CODE-COMPLETE + smoke PASSED; v2.1 deferred (templates + LLM drafts + PDF merge + ITC recon + regulation library) | 2026-05-05 |
| 13. Elasticsearch + Cross-Entity Search | v2.0 | 1/1 v2.0 + 0/N v2.1 | v2.0 CODE-COMPLETE + smoke PASSED via PG-FTS; v2.1 deferred (Elastic Cloud + outbox + reconciliation) | 2026-05-05 |
| 14. Government Portal Integration | v2.0 | 0/TBD | CONTEXT seeded 2026-05-05 — **BLOCKED on GSP empanelment + IT API decisions** | - |
| 15. Gmail MCP Integration | v2.0 | 7/7 | ✅ Shipped | 2026-05-07 |
| 16. BYOK AI Assistant | v2.1 | 1/1 | ✅ Shipped (per-tenant Anthropic / Gemini key, 5 task surfaces, scope-locked SYSTEM prompt) | 2026-05-08 |
| 17. AI Notice Field Extraction, BYOK | v2.0 | 7/7 | ✅ Shipped (upload-first flow, 0.85 conjunctive gate, structural validators, PII-redacted audit chain, smoke 12/12 PASS) | 2026-05-25 |
| 18. AI Notice Response Drafting, BYOK | v2.0 | 1/1 | ✅ Shipped (markdown draft endpoint, NOTICE_DRAFT_RESPONSE gate, PII-redacted draft + guidance hashes, smoke 10/10 PASS against live Gemini) | 2026-05-25 |

---
*Last updated: 2026-05-25 — **Phase 17 v2.0 SHIPPED**. End-to-end smoke `scripts/smoke_phase17_v20.py` cleared 12 of 12 checks against a live Gemini call (avg confidence 0.99, 13 of 14 fields returned, 3.6s latency). Audit redaction, immutability, and RLS isolation all verified by the smoke. Phase 14 remains BLOCKED on GSP empanelment + IT API decisions. v2.1 deferrals for Phase 17: supervised NER / BERT bake-off, tabular line-item extraction, bulk re-extraction of historical notices, cross-validation of extracted GSTIN / PAN against authoritative registries, active-learning loop on accepted edits.*
