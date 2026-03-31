# Requirements: Smart Document Management & Compliance System

**Defined:** 2026-03-30
**Core Value:** Automated classification and intelligent management of documents and compliance notices — upload any document or notice and the system automatically identifies its type, extracts key data, tracks deadlines, and assists with responses.

## v2.0 Requirements

Requirements for the Compliance Management System milestone. Each maps to roadmap phases.

### Notice Lifecycle

- [ ] **LIFE-01**: User can upload a compliance notice (PDF, JPG, PNG) via drag-and-drop
- [ ] **LIFE-02**: System extracts text from uploaded notices via OCR (reuses existing pipeline)
- [ ] **LIFE-03**: User can manually enter notice metadata (number, authority, date, deadline, penalty)
- [ ] **LIFE-04**: User can transition notice through status workflow (Received → Under Review → Response Drafted → Submitted → Resolved/Dismissed)
- [ ] **LIFE-05**: User can link related notices in a chain (Show Cause → Assessment Order → Demand)
- [ ] **LIFE-06**: User can view notice detail page with full activity timeline
- [ ] **LIFE-07**: User can filter/search notices by authority, type, status, risk level, deadline, GSTIN/PAN
- [ ] **LIFE-08**: User can bulk-update notice status for multiple notices

### Classification

- [ ] **CLASS-01**: System classifies notices into 40+ types across 5 authorities (GST, IT, MCA, RBI, SEBI)
- [ ] **CLASS-02**: BERT-based classifier achieves >92% accuracy on test set
- [ ] **CLASS-03**: System displays classification confidence score for each notice
- [ ] **CLASS-04**: Low-confidence classifications (<0.75) routed to human review queue
- [ ] **CLASS-05**: spaCy NER extracts notice number, date, authority, deadline, penalty, legal sections
- [ ] **CLASS-06**: Regex-first extraction for GSTIN, PAN, CIN, DIN, section references (u/s 143(2))
- [ ] **CLASS-07**: ML inference runs in dedicated 2GB Celery worker without degrading v1.0 performance
- [ ] **CLASS-08**: Training pipeline with 5000+ synthetic + public Indian compliance notices

### Risk Scoring

- [ ] **RISK-01**: System generates automated risk score (0-100) on notice creation
- [ ] **RISK-02**: Risk tier labels (Critical/High/Medium/Low) derived from score with configurable thresholds
- [ ] **RISK-03**: Top 3 risk factors displayed via SHAP explanations
- [ ] **RISK-04**: Auto-escalation to Compliance Head for Critical risk notices
- [ ] **RISK-05**: Daily risk score recalculation as deadlines approach

### Alert System

- [ ] **ALERT-01**: Email alerts via SendGrid for new notices and status changes
- [ ] **ALERT-02**: T-7 day reminder email for approaching deadlines
- [ ] **ALERT-03**: T-3 day escalation to manager/compliance head
- [ ] **ALERT-04**: T-1 day critical alert to all stakeholders
- [ ] **ALERT-05**: Post-deadline overdue alert with penalty calculation
- [ ] **ALERT-06**: SMS alerts via Twilio for Critical/High notices
- [ ] **ALERT-07**: In-app real-time notifications via WebSocket
- [ ] **ALERT-08**: Configurable alert rules per notice type
- [ ] **ALERT-09**: Escalation hierarchy (Staff → Senior → Compliance Head → CFO)
- [ ] **ALERT-10**: Calendar integration (Google Calendar, Outlook) for deadline events

### Audit Trail

- [ ] **AUDIT-01**: Immutable timestamped audit log with database-level enforcement (triggers + REVOKE)
- [ ] **AUDIT-02**: Audit log captures who, what, when, before/after values for every change
- [ ] **AUDIT-03**: Auditor-ready export of audit trail (PDF, Excel) by notice/date range
- [ ] **AUDIT-04**: Compliance health score (% resolved on time, adjusted for penalty avoidance)
- [ ] **AUDIT-05**: Response time analytics (average receipt-to-submission time)
- [ ] **AUDIT-06**: Penalty analysis dashboard (paid vs avoided amounts)
- [ ] **AUDIT-07**: Notice summary reports by authority, type, status with trend visualization

### Extended RBAC

- [ ] **RBAC-01**: Compliance Head role — view all, approve responses, reports, configure escalation
- [ ] **RBAC-02**: Legal Team role — draft responses, regulation library, authority-scoped notices
- [ ] **RBAC-03**: Finance Team role — view tax notices (GST/IT), reconciliation data, no response editing
- [ ] **RBAC-04**: Auditor role — time-bound read-only access to notices, trails, reports
- [ ] **RBAC-05**: CA/Tax Consultant role — full permissions within assigned client scope
- [ ] **RBAC-06**: Staff role — create notices, draft responses, escalate (no approve/submit)

### Client Management

- [ ] **CLIENT-01**: User can create and manage client entities with GSTIN/PAN/CIN registrations
- [ ] **CLIENT-02**: Multi-GSTIN/PAN support per client entity
- [ ] **CLIENT-03**: Client-scoped aggregate dashboard showing all client notices
- [ ] **CLIENT-04**: Client data isolation via PostgreSQL RLS (zero cross-client leakage)
- [ ] **CLIENT-05**: Client onboarding workflow (add → entities → team assignment → import)
- [ ] **CLIENT-06**: Per-client configuration overrides (alert rules, approval workflows)
- [ ] **CLIENT-07**: Monthly compliance health summary report per client

### Response Drafting

- [ ] **RESP-01**: Template library for 20+ notice types with variable substitution
- [ ] **RESP-02**: LLM-assisted response draft generation from notice context + entity data
- [ ] **RESP-03**: Multi-stage approval workflow (Drafter → Reviewer → Legal → CFO → Submit)
- [ ] **RESP-04**: Response version control with full rollback capability
- [ ] **RESP-05**: Document attachment from existing DMS to notice responses
- [ ] **RESP-06**: Response submission tracking (acknowledged, pending, rejected)

### Portal Integration

- [ ] **PORT-01**: Auto-fetch notices from GST portal API (GSTIN-based)
- [ ] **PORT-02**: Auto-fetch from Income Tax e-filing portal (PAN-based)
- [ ] **PORT-03**: Auto-fetch from MCA portal (CIN-based)
- [ ] **PORT-04**: Web scraping for RBI/SEBI public enforcement notices
- [ ] **PORT-05**: Email integration (IMAP) for notice capture from official emails
- [ ] **PORT-06**: PortalFetchLog with three-state status monitoring (SUCCESS_EMPTY/WITH_RESULTS/FAILED)
- [ ] **PORT-07**: Encrypted credential vault for portal authentication (Fernet)
- [ ] **PORT-08**: Scheduled portal polling via APScheduler (configurable intervals)

### Reconciliation

- [ ] **RECON-01**: GSTR-2A/2B vs GSTR-3B ITC reconciliation from uploaded JSON
- [ ] **RECON-02**: GSTR-1 vs GSTR-3B outward supply reconciliation
- [ ] **RECON-03**: ITC eligibility analysis for blocked credits under Section 17(5)
- [ ] **RECON-04**: Reconciliation report generation (PDF/Excel) as response exhibit
- [ ] **RECON-05**: Document linking from reconciliation line items to DMS invoices

### Compliance Calendar

- [ ] **CAL-01**: Pre-loaded Indian statutory deadlines (GSTR, TDS, Advance Tax, ITR, ROC filings)
- [ ] **CAL-02**: Entity-specific calendar (applicable deadlines based on entity type/registration)
- [ ] **CAL-03**: Filing status tracking per deadline (Pending/Filed/Filed Late/Missed)
- [ ] **CAL-04**: Monthly/weekly calendar view with visual status indicators
- [ ] **CAL-05**: Calendar alerts integrated with alert system (T-7/T-3/T-1)
- [ ] **CAL-06**: Penalty calculator for late filing scenarios

### Regulation Library

- [ ] **REG-01**: Searchable regulation repository (GST Act, IT Act, Companies Act, FEMA, SEBI)
- [ ] **REG-02**: Regulation-to-notice type mapping (notice → applicable legal sections)
- [ ] **REG-03**: Circular/notification library (CBDT, CBIC circulars, indexed by subject)
- [ ] **REG-04**: Regulation change tracking with version history and update notifications

### Evidence Management

- [ ] **EVID-01**: Link existing DMS documents to notice responses as evidence exhibits
- [ ] **EVID-02**: Evidence package assembly (merge documents into single PDF with TOC)
- [ ] **EVID-03**: Evidence checklist per notice type (auto-suggested from notice metadata)
- [ ] **EVID-04**: Evidence status tracking (Pending/Attached/Submitted) per notice
- [ ] **EVID-05**: Cross-system search (find relevant DMS documents for a specific notice)

### Infrastructure

- [ ] **INFRA-01**: Dedicated Celery worker for ML tasks (2GB RAM, separate `compliance` queue)
- [ ] **INFRA-02**: Elasticsearch managed service with automatic PostgreSQL FTS fallback
- [ ] **INFRA-03**: WebSocket infrastructure via Redis pub/sub bridge for real-time notifications
- [ ] **INFRA-04**: APScheduler integration for periodic jobs (portal polling, deadline scans, ES sync)
- [ ] **INFRA-05**: RegulatoryCalendar table with Indian holiday data for accurate deadline calculation
- [ ] **INFRA-06**: Field-level PII encryption (Fernet) for GSTIN, PAN, penalty amounts in DB and logs
- [ ] **INFRA-07**: Database-level audit trail immutability (PostgreSQL triggers, REVOKE UPDATE/DELETE)

## Future Requirements (v2.1+)

### Deferred Features

- **PRED-01**: Predictive compliance analytics (predict likelihood of receiving notices)
- **MOBILE-01**: Native mobile application (iOS/Android) for notice alerts and dashboard
- **LEGAL-01**: Indian Kanoon / case law search engine integration
- **CHAIN-01**: Blockchain-based tamper-proof audit trail
- **I18N-01**: Multi-language notice interface (Hindi, regional languages)
- **WA-01**: WhatsApp Business API notifications for critical notices
- **PORTAL-SUB-01**: Direct response submission to government portals
- **COUNSEL-01**: External legal counsel portal with secure sharing
- **RECON-ADV-01**: Reconciliation-powered automatic response generation
- **K8S-01**: Kubernetes orchestration for production scaling

## Out of Scope

| Feature | Reason |
|---------|--------|
| Direct portal response submission | APIs not available or require GSP empanelment; risk of silent submission failure |
| Real-time continuous portal sync | Rate limits, CAPTCHA, high failure rate; daily batch + manual refresh sufficient |
| WhatsApp notifications | Business API approval complexity; email + SMS sufficient for v2 |
| Predictive compliance analytics | Requires 12+ months of notice data; build after data accumulates |
| Blockchain audit trail | PostgreSQL immutable append-only with triggers is legally sufficient |
| External counsel portal | Auditor role + secure export sufficient for v2 |
| Indian Kanoon case law search | High complexity, licensing ambiguity; regulation library covers core need |
| Mobile native app | Compliance work requires document review; responsive web sufficient |
| Multi-language interface | English is professional standard for compliance; adds UI complexity |
| OCR for regional languages | Cross-language OCR is expensive and unreliable; manual review queue instead |
| Kubernetes/microservices | Docker Compose sufficient for v2 load; revisit at scale |
| Automated email filing to portals | Not supported by Indian government portals |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LIFE-01 | Phase 9 | Pending |
| LIFE-02 | Phase 9 | Pending |
| LIFE-03 | Phase 9 | Pending |
| LIFE-04 | Phase 9 | Pending |
| LIFE-05 | Phase 9 | Pending |
| LIFE-06 | Phase 9 | Pending |
| LIFE-07 | Phase 9 | Pending |
| LIFE-08 | Phase 9 | Pending |
| AUDIT-01 | Phase 9 | Pending |
| AUDIT-02 | Phase 9 | Pending |
| RBAC-01 | Phase 9 | Pending |
| RBAC-02 | Phase 9 | Pending |
| RBAC-03 | Phase 9 | Pending |
| RBAC-04 | Phase 9 | Pending |
| RBAC-05 | Phase 9 | Pending |
| RBAC-06 | Phase 9 | Pending |
| CLIENT-01 | Phase 9 | Pending |
| CLIENT-02 | Phase 9 | Pending |
| CLIENT-03 | Phase 9 | Pending |
| CLIENT-04 | Phase 9 | Pending |
| CLIENT-05 | Phase 9 | Pending |
| CLIENT-06 | Phase 9 | Pending |
| CLIENT-07 | Phase 9 | Pending |
| INFRA-05 | Phase 9 | Pending |
| INFRA-06 | Phase 9 | Pending |
| INFRA-07 | Phase 9 | Pending |
| CLASS-01 | Phase 10 | Pending |
| CLASS-02 | Phase 10 | Pending |
| CLASS-03 | Phase 10 | Pending |
| CLASS-04 | Phase 10 | Pending |
| CLASS-05 | Phase 10 | Pending |
| CLASS-06 | Phase 10 | Pending |
| CLASS-07 | Phase 10 | Pending |
| CLASS-08 | Phase 10 | Pending |
| RISK-01 | Phase 10 | Pending |
| RISK-02 | Phase 10 | Pending |
| RISK-03 | Phase 10 | Pending |
| RISK-04 | Phase 10 | Pending |
| RISK-05 | Phase 10 | Pending |
| INFRA-01 | Phase 10 | Pending |
| ALERT-01 | Phase 11 | Pending |
| ALERT-02 | Phase 11 | Pending |
| ALERT-03 | Phase 11 | Pending |
| ALERT-04 | Phase 11 | Pending |
| ALERT-05 | Phase 11 | Pending |
| ALERT-06 | Phase 11 | Pending |
| ALERT-07 | Phase 11 | Pending |
| ALERT-08 | Phase 11 | Pending |
| ALERT-09 | Phase 11 | Pending |
| ALERT-10 | Phase 11 | Pending |
| CAL-01 | Phase 11 | Pending |
| CAL-02 | Phase 11 | Pending |
| CAL-03 | Phase 11 | Pending |
| CAL-04 | Phase 11 | Pending |
| CAL-05 | Phase 11 | Pending |
| CAL-06 | Phase 11 | Pending |
| INFRA-03 | Phase 11 | Pending |
| INFRA-04 | Phase 11 | Pending |
| RESP-01 | Phase 12 | Pending |
| RESP-02 | Phase 12 | Pending |
| RESP-03 | Phase 12 | Pending |
| RESP-04 | Phase 12 | Pending |
| RESP-05 | Phase 12 | Pending |
| RESP-06 | Phase 12 | Pending |
| EVID-01 | Phase 12 | Pending |
| EVID-02 | Phase 12 | Pending |
| EVID-03 | Phase 12 | Pending |
| EVID-04 | Phase 12 | Pending |
| RECON-01 | Phase 12 | Pending |
| RECON-02 | Phase 12 | Pending |
| RECON-03 | Phase 12 | Pending |
| RECON-04 | Phase 12 | Pending |
| RECON-05 | Phase 12 | Pending |
| REG-01 | Phase 12 | Pending |
| REG-02 | Phase 12 | Pending |
| REG-03 | Phase 12 | Pending |
| REG-04 | Phase 12 | Pending |
| AUDIT-03 | Phase 13 | Pending |
| AUDIT-04 | Phase 13 | Pending |
| AUDIT-05 | Phase 13 | Pending |
| AUDIT-06 | Phase 13 | Pending |
| AUDIT-07 | Phase 13 | Pending |
| EVID-05 | Phase 13 | Pending |
| INFRA-02 | Phase 13 | Pending |
| PORT-01 | Phase 14 | Pending |
| PORT-02 | Phase 14 | Pending |
| PORT-03 | Phase 14 | Pending |
| PORT-04 | Phase 14 | Pending |
| PORT-05 | Phase 14 | Pending |
| PORT-06 | Phase 14 | Pending |
| PORT-07 | Phase 14 | Pending |
| PORT-08 | Phase 14 | Pending |

**Coverage:**
- v2.0 requirements: 92 total
- Mapped to phases: 92
- Unmapped: 0

| Phase | Requirements | Count |
|-------|-------------|-------|
| Phase 9: Compliance Foundation | LIFE-01..08, AUDIT-01..02, RBAC-01..06, CLIENT-01..07, INFRA-05..07 | 26 |
| Phase 10: ML Classification + Risk Scoring | CLASS-01..08, RISK-01..05, INFRA-01 | 14 |
| Phase 11: Alert System + Compliance Calendar | ALERT-01..10, CAL-01..06, INFRA-03..04 | 18 |
| Phase 12: Response Drafting + Evidence Management | RESP-01..06, EVID-01..04, RECON-01..05, REG-01..04 | 19 |
| Phase 13: Elasticsearch + Cross-Entity Search + Reporting | AUDIT-03..07, EVID-05, INFRA-02 | 7 |
| Phase 14: Government Portal Integration | PORT-01..08 | 8 |
| **Total** | | **92** |

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 — traceability populated by roadmapper (92/92 mapped)*
