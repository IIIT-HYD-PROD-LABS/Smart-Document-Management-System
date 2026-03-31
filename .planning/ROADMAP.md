# Roadmap: Smart Document Management & Compliance System

## Milestones

- **v1.0 Smart Document Management System** -- Phases 1-8 (shipped 2026-03-30) | [Archive](milestones/v1.0-ROADMAP.md)
- **v2.0 Compliance Management System** -- Phases 9-14 (in progress)

## Phases

<details>
<summary>v1.0 Smart Document Management System (Phases 1-8) -- SHIPPED 2026-03-30</summary>

Phases 1-8 shipped. See archived roadmap: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

42/42 requirements validated across 8 phases.

</details>

### v2.0 Compliance Management System

**Milestone Goal:** Add AI-powered compliance notice management for Indian regulatory authorities to the existing document management system, with BERT-based classification, risk scoring, AI-assisted response drafting, multi-channel alerts, and full audit trails.

- [ ] **Phase 9: Compliance Foundation** - Notice lifecycle, extended RBAC, client/entity management, immutable audit infrastructure
- [ ] **Phase 10: ML Classification + Risk Scoring** - BERT notice classifier, spaCy NER, XGBoost risk scoring, dedicated ML worker
- [ ] **Phase 11: Alert System + Compliance Calendar** - SendGrid/Twilio/WebSocket alerts, T-7/T-3/T-1 reminders, statutory deadline calendar
- [ ] **Phase 12: Response Drafting + Evidence Management** - LLM draft generation, approval workflow, evidence packages, reconciliation engine, regulation library
- [ ] **Phase 13: Elasticsearch + Cross-Entity Search + Reporting** - Unified notice+document search, compliance reports, penalty analytics, compliance health score
- [ ] **Phase 14: Government Portal Integration** - GST/IT/MCA auto-fetch, RBI/SEBI scraping, IMAP email parsing, portal credential vault

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
**Plans**: TBD
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
**Plans**: TBD

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
**Goal**: Notices from GST, Income Tax, and MCA portals are auto-fetched on a schedule, RBI/SEBI public notices are scraped, and email inboxes are parsed — all with encrypted credential storage, fetch health monitoring, and duplicate prevention
**Depends on**: Phase 13
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, PORT-05, PORT-06, PORT-07, PORT-08
**Success Criteria** (what must be TRUE):
  1. Notices from GST portal (GSTIN-based), Income Tax e-filing portal (PAN-based), and MCA portal (CIN-based) are automatically fetched on a configurable schedule and appear in the compliance dashboard without manual upload
  2. RBI and SEBI public enforcement notices are scraped and ingested; the scraper detects redirect-to-login and marks the run as FETCH_FAILED rather than SUCCESS_EMPTY
  3. An IMAP-connected email account captures compliance notices sent to official email addresses and routes them through the standard ingestion pipeline
  4. Every portal fetch run creates a PortalFetchLog entry with a three-state result (SUCCESS_EMPTY / SUCCESS_WITH_RESULTS / FETCH_FAILED); admins receive an alert after two consecutive FETCH_FAILED runs for any portal
  5. Portal credentials (GST API keys, email passwords) are stored encrypted (Fernet) in the database; no credentials appear in application logs, Celery task arguments, or Elasticsearch source fields
  6. Duplicate notices are prevented by a database UNIQUE constraint plus Redis distributed lock — restarting the portal poller during a partial run never creates duplicate notice records
**Plans**: TBD

## Progress

**Execution Order:** Phases execute in numeric order: 9 → 10 → 11 → 12 → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 9. Compliance Foundation | v2.0 | 0/TBD | Not started | - |
| 10. ML Classification + Risk Scoring | v2.0 | 0/TBD | Not started | - |
| 11. Alert System + Compliance Calendar | v2.0 | 0/TBD | Not started | - |
| 12. Response Drafting + Evidence Management | v2.0 | 0/TBD | Not started | - |
| 13. Elasticsearch + Cross-Entity Search + Reporting | v2.0 | 0/TBD | Not started | - |
| 14. Government Portal Integration | v2.0 | 0/TBD | Not started | - |

---
*Last updated: 2026-03-30 — v2.0 roadmap created (phases 9-14, 92 requirements)*
