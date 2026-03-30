# Feature Landscape: Indian Compliance Management System (v2.0)

**Domain:** Compliance notice management for Indian regulatory authorities (GST, Income Tax, MCA, RBI, SEBI, Legal)
**Researched:** 2026-03-30
**Confidence:** MEDIUM (training data through August 2025; Indian regulatory specifics well-documented; portal API details LOW confidence pending official verification)

---

## Context: What "Compliance Management" Means in India

Indian businesses face notices from five regulatory stacks, each with distinct notice types, response windows, and penalty regimes. A CA/tax consultant managing multiple clients (or a corporate compliance team managing one entity across multiple GSTINs/PANs) needs to:

1. Capture notices the moment they appear on government portals or arrive via email/post
2. Classify the notice type (severity, legal section, applicable penalties)
3. Score risk (penalty exposure × deadline urgency × authority severity)
4. Draft a response with supporting evidence pulled from books of accounts / documents
5. Route through approval before submission
6. Track submission and closure
7. Maintain an immutable audit trail for future regulatory inspections

The workflow is fundamentally different from generic document management: the system must understand Indian legal taxonomy, statutory deadlines, and reconciliation logic (GSTR-2A vs 3B mismatches, TDS credit mismatches, etc.).

---

## Table Stakes

Features users expect. Missing any of these makes the product feel incomplete or legally risky.

### 1. Notice Lifecycle Management

The core workflow. Every compliance tool in India (ClearTax, myBillBook Compliance, LegalWiz.in, CA-oriented ERPs like TallyPrime) exposes this workflow.

| Feature | Why Expected | Complexity | Dependencies on Existing System |
|---------|--------------|------------|----------------------------------|
| Notice status workflow (Received → Under Review → Response Drafted → Submitted → Resolved / Dismissed) | Industry standard; auditors demand audit trail of each state transition | MEDIUM | Extends existing document status field; new `compliance_notices` table |
| Manual notice upload (PDF/image scan) | Not all notices arrive digitally; postal notices are common for legacy assessments | LOW | Reuses existing upload + OCR pipeline directly |
| Notice metadata capture (notice number, section, authority, GSTIN/PAN, AY/FY, deadline, penalty amount) | Without structured metadata, search and risk scoring are impossible | MEDIUM | Extends existing NER extraction; add compliance-specific entity types |
| Link related notices (Show Cause Notice → Assessment Order → Demand Notice → Penalty Order) | GST enforcement follows a chain; losing the thread breaks response continuity | MEDIUM | New `notice_relationship` table; FK-based parent-child linking |
| Notice detail view with timeline | Auditors expect a chronological record of all actions on a notice | LOW | Standard CRUD; reuses existing document preview component |
| Filter/search notices by authority, type, status, GSTIN/PAN, deadline, risk level | Compliance teams manage hundreds of notices; filtering is survival | LOW | Extends existing search filters; add compliance-specific filter dimensions |
| Bulk status update | CAs managing 50+ clients cannot update notices one by one | LOW | Batch API endpoint; checkbox-select UI pattern |

**Confidence:** HIGH — these patterns are universal across all Indian compliance software.

### 2. Notice Classification Taxonomy

Users expect the system to know what an ASMT-10 is without being told. This is the domain knowledge layer.

**GST Notice Types (HIGH confidence — these are statutory forms under GST law):**

| Notice Code | Section | Nature | Typical Deadline | Penalty Exposure |
|-------------|---------|--------|-----------------|-----------------|
| ASMT-10 | Section 61 | Scrutiny of returns (mismatch notice) | 30 days from issue | Late fee + interest on mismatch amount |
| ASMT-12 | Section 61 | Acceptance / drop of scrutiny (no action needed) | N/A — acknowledgment | None |
| DRC-01 | Section 73/74 | Show Cause Notice (pre-adjudication) | 30 days to reply | Tax + interest + 10-100% penalty |
| DRC-01A | Section 73/74 | Pre-SCN communication (opportunity before SCN) | 30 days to explain | Avoids SCN if resolved |
| DRC-01C | Section 73 | ITC mismatch notice (GSTR-2B vs 3B) | 7 days to explain | ITC reversal + interest |
| DRC-07 | Section 73/74 | Summary of demand after adjudication | Payment or appeal | Tax + interest + penalty (confirmed demand) |
| DRC-10 | Section 79 | Recovery notice (after demand unpaid) | Immediate compliance | Attachment of assets possible |
| ADT-01 | Section 65 | Audit notice (GST department audit) | 15 days advance notice | Audit findings → further notices |
| ADT-03 | Section 65 | Audit report communication | 30 days to respond | Difference amount + penalty |
| SCN-01 | Various | Show Cause Notice (generic) | 30 days | Varies |
| REG-03 | Section 25 | Clarification notice on registration | 7 working days | Registration rejection |
| REG-17 | Section 29 | Show Cause for registration cancellation | 7 days | Registration cancelled |
| GSTR-3A | Section 46 | Notice for non-filing of returns | 15 days | Late fee ₹200/day, max ₹5,000 |

**Income Tax Notice Types (HIGH confidence — statutory notices under Income Tax Act 1961):**

| Notice Section | Nature | Typical Deadline | Penalty/Consequence |
|---------------|--------|-----------------|---------------------|
| Section 139(9) | Defective return notice | 15 days to rectify | Return treated as not filed if ignored |
| Section 143(1) | Intimation (not really a notice; auto-processed assessment) | N/A | Demand or refund |
| Section 143(2) | Scrutiny notice (limited or complete scrutiny) | 30 days initial; extended per hearing | Assessment order + potential demand |
| Section 148 | Reassessment notice (income escaped assessment) | 30 days to file return | Reassessment + penalty 50-200% of tax |
| Section 148A | Show cause before 148 (post SC ruling, 2022) | 7 days to respond | Avoids reassessment if satisfactory |
| Section 156 | Demand notice (after assessment order) | 30 days to pay | Interest u/s 220(2) @ 1% per month |
| Section 245 | Intimation of set-off of refund against demand | 30 days to object | Refund adjusted |
| Section 263/264 | Revision by PCIT/CIT | 30 days | Re-assessment |
| Section 271(1)(c) | Penalty for concealment / inaccurate particulars | 30 days | 100-300% of tax sought to be evaded |
| Section 271AAB | Penalty for undisclosed income (search) | N/A | 30-60% of undisclosed income |
| Section 276C/277 | Prosecution notice | Urgent | Criminal proceedings possible |

**MCA/Companies Act Notice Types (MEDIUM confidence):**

| Notice Type | Purpose | Deadline | Consequence |
|-------------|---------|----------|-------------|
| ROC Inquiry | Section 206 inquiry by Registrar | 30 days | Prosecution or strike-off |
| STK-2 / STK-5 | Strike-off notice | 30 days to respond | Company struck off |
| MGT-14 Filing Defect | Defective ROC filing | 30 days to rectify | Late fee escalation |
| DPT-3 Non-Filing | Deposit non-compliance | Immediate | Penalty on company + officers |
| ADJ-01 | Adjudication of penalties | 30 days | Penalty order |
| Charge Satisfaction Default | Non-satisfaction of charge | Varies | ROC action |

**RBI Notice Types (MEDIUM confidence — no standardized form codes like GST):**

| Notice Category | Purpose | Typical Deadline | Authority |
|----------------|---------|-----------------|-----------|
| Show Cause Notice | FEMA violations, KYC non-compliance, licensing issues | 21-30 days | RBI Enforcement Dept |
| Inspection Notice | Annual/special inspection by RBI | 15 days advance | RBI Dept of Banking Regulation |
| Corrective Action Plan | Prompt Corrective Action (PCA) framework | Immediate | RBI |
| Penalty Order | Under Banking Regulation Act / FEMA | Payment within 14 days | RBI |
| Compounding Notice | FEMA compounding application | 60-120 days process | RBI Enforcement |

**SEBI Notice Types (MEDIUM confidence):**

| Notice Category | Purpose | Typical Deadline | Authority |
|----------------|---------|-----------------|-----------|
| Show Cause Notice | LODR violations, insider trading, disclosure lapses | 21 days | SEBI Adjudicating Officer |
| Inspection/Investigation Notice | Market manipulation, suspicious trades | 7-14 days | SEBI |
| Adjudication Order | Penalty order after proceedings | Payment within 45 days | SEBI |
| Compounding Order | Settlement of proceedings | Varies | SEBI |
| Suspension/Debarment Notice | Trading or market access restriction | Immediate | SEBI |

**Implementation Note:** These taxonomies feed the BERT classifier's label space. The classifier needs 13+ GST classes, 11+ IT classes, 5+ MCA classes, 5+ RBI classes, 5+ SEBI classes = ~40 fine-grained labels. Multi-label classification (a notice can have multiple applicable sections) is needed.

**Dependency on existing system:** Extends the existing 6-category document classifier. New BERT model shares the same Celery pipeline for async inference.

### 3. Risk Scoring

Every notice must be scored on arrival. Compliance teams triage by risk score, not chronological order.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Automated risk score (0-100) on notice creation | Compliance managers cannot manually evaluate every notice | HIGH | XGBoost model; features: penalty amount, deadline days remaining, authority severity weight, historical response rate, notice type severity |
| Risk tier labels (Critical / High / Medium / Low) | Numeric scores are not actionable; tiers drive workflow | LOW | Thresholds derived from score; configurable per organization |
| Risk score explanation (top factors) | Auditors and compliance heads need to understand why a notice is Critical | MEDIUM | SHAP values for XGBoost; surface top 3 contributing factors |
| Auto-escalation on Critical risk | High-risk notices must not sit in queue | MEDIUM | Celery beat task; checks risk score on creation; triggers escalation workflow |
| Risk score recalculation as deadline approaches | A Medium notice 30 days out becomes High at T-7 | LOW | Scheduled APScheduler job; re-scores based on remaining days |

**Risk Scoring Model Features (XGBoost inputs):**

```
penalty_amount_inr          — extracted from notice; log-scaled
days_to_deadline            — calculated; negative = overdue
authority_severity_weight   — RBI/SEBI > IT > GST > MCA (configurable)
notice_type_severity        — DRC-07 > DRC-01 > ASMT-10 (pre-encoded)
repeat_notice_flag          — same section, same GSTIN/PAN, prior period
pending_related_notices     — count of unresolved notices in same chain
historical_penalty_paid     — prior penalty for same authority (₹)
entity_compliance_score     — rolling 12-month compliance score
```

**Confidence:** MEDIUM — risk scoring logic is well-established in Indian CA/compliance software; specific feature weights require validation against real notice data.

### 4. Alert and Escalation System

Compliance deadlines in India are hard legal deadlines. Missing a reply to a DRC-01 or 143(2) can result in ex-parte orders, demands, or prosecution.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| T-7 reminder (7 days before deadline) | First warning to start preparing response | LOW | APScheduler daily job; query notices where deadline = today + 7 |
| T-3 reminder (3 days before deadline) | Urgency escalation | LOW | Same scheduler pattern |
| T-1 reminder (1 day before deadline) | Last chance alert | LOW | Same scheduler pattern |
| Overdue alert (deadline passed, not resolved) | Legal exposure is active; needs immediate management | LOW | Continuous daily check |
| Email alerts (SendGrid) | Primary channel; all compliance professionals use email | LOW | Template-based; SMTP or SendGrid API |
| SMS alerts for Critical/High (Twilio) | Critical notices need out-of-band channel | LOW | Twilio API; SMS for T-1 and overdue only (cost control) |
| In-app notifications | Real-time awareness while using the system | MEDIUM | WebSocket push; notification bell + count badge |
| Custom alert rules per notice type | A CA may want T-14 for 143(2) scrutiny but T-3 for GSTR-3A | MEDIUM | Per-notice-type rule configuration; stored in DB |
| Escalation hierarchy | If notice owner does not act by T-3, escalate to compliance head | MEDIUM | Configurable chain: Staff → Senior → Compliance Head → CFO |
| Calendar integration (Google Calendar / Outlook) | Compliance heads use calendar for scheduling | MEDIUM | iCal/ICS export; OAuth-based Google Calendar API write |

**Confidence:** HIGH — alert patterns (T-7, T-3, T-1) are universal across Indian compliance tools and CA practice management software.

### 5. Audit Trail

In India, regulatory inspections (by GST, IT, RBI, SEBI) may require showing who did what to each notice and when. Tampering with this record is itself a compliance violation.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Immutable timestamped log of every action on a notice | Regulatory inspection requirement; legal discovery requirement | MEDIUM | Append-only `audit_log` table; PostgreSQL triggers or application-level hooks; no UPDATE/DELETE |
| Who changed what (user, role, timestamp, before/after values) | Auditors need to verify no unauthorized changes | MEDIUM | Store diff of changed fields; JSON blob for flexibility |
| Auditor-read-only role | External auditors must be able to view but not modify | LOW | New RBAC role: Auditor; read-only DB policy |
| Audit trail export (PDF, Excel) | Auditors request exports; they don't have system access | LOW | Generate report from `audit_log` filtered by notice/date range |
| Compliance health score (aggregate) | Management wants a single KPI for compliance posture | MEDIUM | Formula: (resolved on time / total notices) × 100, adjusted for penalty avoidance |
| Response time analytics | How long did it take from receipt to submission? | LOW | Calculated from audit_log timestamps |
| Penalty analysis (paid vs avoided) | Financial reporting requirement | LOW | Aggregate penalty amounts by status: paid, avoided, pending |

**Confidence:** HIGH — audit trail requirements are mandated by Indian compliance regulations (GST Rule 56, Income Tax Section 285B, Companies Act Section 128).

### 6. Extended RBAC for Compliance Workflows

The existing system has admin/editor/viewer roles. Compliance workflows need domain-specific roles.

| Role | Permissions | Notes |
|------|-------------|-------|
| Compliance Head | View all notices, approve responses, access all reports, configure escalation rules | Senior manager; owns compliance posture |
| Legal Team | Draft responses, access regulation library, view all notices in their authority scope | Cannot submit; submits after approval |
| Finance Team | View tax notices (GST, IT), access reconciliation data, cannot modify responses | Limited scope; no legal notices |
| Auditor | Read-only access to all notices, audit trails, reports | Time-bound access; no write permissions |
| CA/Tax Consultant | All permissions within assigned client scope | Multi-client management; isolated per client |
| Staff/Junior | Create notices, draft initial responses, escalate | Cannot approve or submit |

**Dependency on existing system:** Extends existing RBAC tables (roles, permissions, user_roles). Add `client_scope` FK for CA multi-client support.

---

## Differentiators

Features that set this product apart from generic compliance trackers. Not universally expected, but highly valued by CAs and corporate compliance teams.

### 7. AI-Assisted Response Drafting

Generic compliance tools have template libraries. The differentiator here is LLM-generated responses that incorporate the specific facts of the notice and the entity's financial data.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Template library for common notice types (per GST/IT/MCA notice code) | 80% of ASMT-10 responses follow the same structure; templates save hours | MEDIUM | Pre-built templates for 20+ notice types; variables substituted from extracted metadata |
| LLM draft generation (notice context + entity facts → full response draft) | Eliminates the blank-page problem; legal-grade language | HIGH | GPT-4o or Claude as primary; prompt engineered with Indian legal context; 5-provider fallback (extends existing LLM infrastructure) |
| Reconciliation-powered responses for GST mismatches | ASMT-10 / DRC-01C responses need GSTR-2A vs 3B reconciliation data as exhibit | HIGH | Query reconciliation module; auto-generate mismatch analysis table; embed in response as Exhibit A |
| Response version control | Drafts go through multiple revisions; need rollback | LOW | Reuses existing document version control system |
| Document attachment from existing DMS | Notice responses require supporting documents (invoices, bank statements, ledgers) | MEDIUM | Cross-system evidence linking; select documents from Task 1 system to attach to response |
| Multi-stage approval workflow (Drafter → Reviewer → Legal → CFO → Submit) | Prevents unauthorized submissions; required for listed companies and large CAs | HIGH | Configurable stages per notice type; each stage records approver + timestamp in audit trail |
| Response submission tracking | Was the response acknowledged by the portal? | MEDIUM | Status update after manual submission; auto-update if portal API supports read-back |

**Confidence:** MEDIUM — template-based response generation is well-established; reconciliation-powered responses are a differentiator specific to this product's architecture.

### 8. Government Portal Integration

This is the hardest feature. Direct portal integration eliminates manual downloading and checking.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| GST portal notice auto-fetch (GSTIN-based) | Notices appear on GST portal; CAs check multiple GSTINs manually | HIGH | GST Sandbox API exists; production API requires GSP (GST Suvidha Provider) empanelment — LOW confidence on self-service API access |
| Income Tax e-filing portal notice fetch | IT notices appear in My Account → e-Proceedings | HIGH | No public API documented; requires screen scraping of e-filing portal with CAPTCHA handling or third-party API aggregators (like ClearTax, SignDesk) |
| MCA portal filing status and notice fetch | ROC notices in MCA21 portal | HIGH | MCA21 v3 has limited public API; scraping is primary approach |
| RBI / SEBI notice monitoring | No centralized portal; notices are served via email or official letters | HIGH | Web scraping of RBI press releases / enforcement actions; email parsing for direct notices |
| Email integration for notice capture | Many government notices are sent to registered email | MEDIUM | IMAP/OAuth email polling; pattern matching to identify compliance notices vs general mail |
| Webhook/push notification from portals | Portals notify on new notice | LOW (future) | GST sandbox supports webhooks; IT portal does not (as of August 2025) |

**Critical Implementation Note (LOW confidence — verify before building):**
- GST API access requires either: (a) taxpayer's own API credentials via GST portal developer console, or (b) GSP empanelment. Direct taxpayer API may be feasible for self-use but not for CAs serving multiple clients without ASP/GSP licensing.
- IT e-filing portal has no documented public API for e-Proceedings. Third-party integrations (ClearTax APIs, Karvy/KFintech) provide this but at licensing cost.
- MCA21 v3 API is partially documented at `developer.mca.gov.in`; most integrations use data.gov.in's SPARQL endpoint or scraping.
- **Risk:** Build portal integration as optional/Phase 2; fallback to email parsing + manual upload (which are Phase 1).

**Dependency on existing system:** Extends existing Celery pipeline for async portal polling; extends existing OCR pipeline for scanned notices.

### 9. Reconciliation Engine for GST Responses

This is a unique differentiator specific to India's GST regime.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| GSTR-2A / GSTR-2B vs GSTR-3B ITC reconciliation | Most ASMT-10 and DRC-01C notices allege ITC discrepancy; reconciliation is the evidence | HIGH | Parse GSTR-2A/2B JSON (from portal download); compare against GSTR-3B filed data; compute mismatch table |
| GSTR-1 vs GSTR-3B outward supply reconciliation | Some notices allege under-reporting of outward supply | HIGH | Parse GSTR-1 JSON; compare against 3B; identify gaps |
| ITC eligibility analysis (blocked credits u/s 17(5)) | Reconciliation must also exclude ineligible ITC categories | MEDIUM | Rule-based engine: identify items blocked under Section 17(5); auto-classify |
| Reconciliation report generation | Attach as exhibit to notice response | MEDIUM | PDF/Excel export of mismatch table with explanation column |
| Document linking to reconciliation line items | Each disputed invoice should link to the invoice document in Task 1 DMS | MEDIUM | Cross-reference: invoice number in reconciliation → document in Task 1 search |

**Confidence:** HIGH for business need; MEDIUM for technical approach (GSTN JSON formats are documented but subject to change).

### 10. Compliance Calendar

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Pre-loaded statutory deadlines (GSTR-1, GSTR-3B, GSTR-9, GSTR-9C, TDS Q1-Q4, Advance Tax, ITR, ROC Annual Filings) | Compliance teams track 50+ recurring deadlines; manual tracking causes lapses | MEDIUM | Static seed data; updated annually; linked to applicable entity (GSTIN/PAN) |
| GSTIN/PAN-specific calendar (applicable deadlines only) | A composition taxpayer has different deadlines than regular GST taxpayer | MEDIUM | Entity type drives which deadlines apply; configuration during entity onboarding |
| Deadline status tracking (Pending / Filed / Filed Late / Missed) | Calendar is not useful if it doesn't track actuals | MEDIUM | Manual status updates initially; auto-update via portal integration later |
| Compliance calendar view (monthly/weekly) | Visual overview of upcoming filings | LOW | Standard calendar UI component (react-big-calendar or similar) |
| Reminder integration (alerts at T-7, T-3, T-1 before each deadline) | Same alert infrastructure as notice deadlines | LOW | Reuses alert system; calendar deadlines are just another trigger source |
| Penalty calculator for late filing | "If I file GSTR-3B 5 days late, penalty = ₹1,000?" | MEDIUM | Rule engine: authority × filing type × days late → penalty amount |

**Pre-loaded Indian Statutory Deadlines (HIGH confidence):**

```
GSTR-1 (monthly, turnover >5Cr):        11th of next month
GSTR-1 (quarterly, QRMP scheme):        13th of month after quarter end
IFF (optional, QRMP):                   13th of first two months of quarter
GSTR-3B (monthly):                      20th of next month (22nd/24th for smaller states)
GSTR-9 (annual return):                 31 December (AY+1)
GSTR-9C (reconciliation statement):     31 December (AY+1)
TDS Q1 (Apr-Jun):                       31 July
TDS Q2 (Jul-Sep):                       31 October
TDS Q3 (Oct-Dec):                       31 January
TDS Q4 (Jan-Mar):                       31 May
Advance Tax Installment 1:              15 June (15% of estimated tax)
Advance Tax Installment 2:              15 September (45%)
Advance Tax Installment 3:              15 December (75%)
Advance Tax Installment 4:              15 March (100%)
ITR Filing (non-audit):                 31 July
ITR Filing (audit cases):               31 October
ITR Filing (transfer pricing):          30 November
ROC Annual Return (MGT-7/7A):           60 days after AGM
ROC Financial Statements (AOC-4):       30 days after AGM
DPT-3 (deposits return):               30 June annually
MSME-1 (half-yearly):                  30 April and 31 October
```

### 11. Regulation Library

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Regulation repository (GST Act, IT Act, Companies Act, FEMA, SEBI regulations) | Response drafters need to cite applicable sections | MEDIUM | Static document store; searchable; linked to notice types |
| Regulation-to-notice mapping | Given a DRC-01 under Section 73, what law applies? Show relevant sections | MEDIUM | FK table: notice_type → regulation_sections (many-to-many) |
| Regulation change tracking | GST law changes frequently (2-4 circulars/month); outdated law = wrong response | HIGH | Subscribe to GST Council press releases / CBDT circulars; manual update workflow with notification |
| Circular/notification library (CBDT, CBIC) | CAs rely on interpretive circulars, not just the Act | MEDIUM | Curated repository; tag by subject matter and applicable section |

**Confidence:** MEDIUM — regulation library as a static searchable repository is straightforward; automated regulation change tracking requires content monitoring infrastructure.

### 12. Multi-Client Management (CA/Tax Consultant Mode)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Client entity management (multiple GSTINs, PANs, MCA CINs per client) | A CA firm may manage 100+ entities; each has multiple registrations | MEDIUM | New `client` and `entity` tables; GSTIN/PAN/CIN as unique identifiers per entity |
| Client-scoped dashboard | CA sees all clients' pending notices in one view; click-through to client | MEDIUM | Aggregate view with client filter; access controlled per CA-client assignment |
| Client onboarding workflow | Add client → configure entities → assign team members → import notices | MEDIUM | Wizard-style onboarding; entity verification via GST/PAN API (if available) |
| Client isolation (no cross-client data leakage) | Ethical obligation; also a regulatory requirement for CA firms | HIGH | Row-level security (PostgreSQL RLS) or application-level tenant filtering; critical for data integrity |
| Bulk client notice summary report | Monthly compliance health report per client (for CA to share with client) | MEDIUM | Parameterized report: client → notices summary → pending actions → health score |
| Client-specific configuration (alert rules, approval workflows) | Different clients may have different escalation tolerances | LOW | Per-client configuration table overrides global defaults |

**Confidence:** HIGH — multi-client management is a defining feature for the CA/tax consultant market segment in India.

### 13. Evidence Management

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Link DMS documents to notice response as evidence | "Exhibit A: Invoice #INV-2023-456" should pull from Task 1 document store | MEDIUM | New `notice_evidence` junction table: notice_id → document_id (Task 1) |
| Evidence package assembly | Combine multiple documents into a single PDF bundle for submission | HIGH | PDF merging (pypdf2/reportlab); TOC generation; exhibit labeling |
| Evidence checklist per notice type | For ASMT-10, typical exhibits are: GSTR-2A, invoices, payment receipts | MEDIUM | Template-based checklist; auto-suggest from notice type + extracted metadata |
| Evidence status tracking (Pending / Attached / Submitted) | Know if all required evidence has been assembled before submission | LOW | Status field on `notice_evidence`; pre-submission validation check |
| Cross-system search (find relevant documents from Task 1 for this notice) | "Find all purchase invoices from GSTIN 33AABCT1332L1ZS between Apr-Jun 2023" | HIGH | Elasticsearch cross-index query across `documents` and `notices` indices; parameter extraction from notice feeds the query |

**Dependency on existing system:** Heavy. Uses existing document store, OCR pipeline, FTS/Elasticsearch, and document preview. This is the primary integration point between Task 1 and Task 2.

---

## Anti-Features

Features to deliberately NOT build for v2.0.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Direct government portal submission | APIs for submitting responses are either not available (IT, MCA) or require GSP empanelment (GST); building this creates a compliance liability if the submission fails silently | Track submission status manually; provide drafted response as downloadable package for human submission |
| Real-time portal sync (continuous polling) | Rate limits, CAPTCHA, session management; high failure rate; engineering complexity disproportionate to benefit | Daily scheduled batch fetch; user-triggered manual refresh |
| WhatsApp notifications | Requires WhatsApp Business API approval (slow process); high operational cost | Email + SMS is sufficient for v2; defer to v3 |
| Predictive compliance analytics (predict future notices) | Requires 2+ years of labeled notice history per entity; insufficient training data at launch | Build after 12+ months of data accumulation |
| Blockchain audit trail | Engineering overhead with no practical benefit; PostgreSQL immutable append-only log is legally sufficient | PostgreSQL with trigger-based immutability + signed exports |
| External counsel portal | Separate authentication, UI, and access management for external lawyers | Auditor role + secure report sharing via export is sufficient |
| Indian Kanoon / case law integration | High complexity; edge case for most users; licensing ambiguity | Provide regulation library with CBDT/CBIC circulars; link to relevant sections |
| Mobile native app | Compliance work requires document review and form filling; mobile is not the primary workflow | Responsive web design for mobile access to dashboards and alerts |
| Multi-language notice interface (Hindi, regional) | English is the professional standard for compliance work; adds significant UI complexity | All notice text in English; v3 consideration |
| Automated email filing to portals | Not supported by Indian government portals; email is only for acknowledgment tracking | Manual submission workflow with drafted response export |
| OCR for regional language notices | Some government notices are in regional languages; cross-language OCR is expensive and unreliable | Flag notices with non-English content; manual review queue |
| Kubernetes / microservices | 10-12 week timeline; Docker Compose is sufficient for initial load | Docker Compose for v2; revisit at scale |

---

## Feature Dependencies

```
Existing System (Task 1 — Already Built):
├── User Authentication (JWT, OAuth SSO)
├── Document Upload + OCR Pipeline (PDF, JPG, PNG, DOCX)
├── ML Classification (scikit-learn, Linear SVC)
├── Full-Text Search (PostgreSQL FTS + pg_trgm)
├── LLM Extraction (5-provider fallback)
├── RBAC (admin, editor, viewer)
├── Document Preview + Version Control
├── Async Celery + Redis
├── Analytics Dashboard
└── PostgreSQL + FastAPI + Next.js + Docker stack

New Compliance Layer Foundation (Must Build First):
├── Notice Data Model (compliance_notices, notice_types, notice_evidence tables)
├── Client/Entity Management (clients, entities, GSTIN/PAN registry)
├── Extended RBAC (compliance roles, client-scoped permissions)
└── Compliance-Specific NER (extend existing LLM extraction)
    Required by: ALL compliance features

Tier 1 — Core Tracking (Build Next):
├── Notice Lifecycle Workflow → Requires: Notice Data Model
├── Manual Notice Upload → Requires: Existing OCR + Notice Data Model
├── Notice Classification (BERT) → Requires: Notice Data Model + Celery pipeline
├── Risk Scoring (XGBoost) → Requires: Notice Classification + Notice Data Model
├── Alert System (email/SMS/in-app) → Requires: Notice Data Model + SendGrid + Twilio
│   └── T-7/T-3/T-1 reminders → Requires: APScheduler + Alert System
└── Basic Audit Trail → Requires: Notice Data Model

Tier 2 — Intelligence Layer (Build After Tier 1):
├── Template Library → Requires: Notice Classification
├── LLM Response Draft → Requires: Template Library + Existing LLM Infrastructure
│   └── Approval Workflow → Requires: LLM Response Draft + Extended RBAC
├── Compliance Calendar → Requires: Client/Entity Management
│   └── Calendar Alerts → Requires: Compliance Calendar + Alert System
├── Evidence Management → Requires: Notice Data Model + Existing Document Store
│   └── Cross-System Search → Requires: Evidence Management + Elasticsearch
└── Audit Reports + Health Score → Requires: Audit Trail + Analytics (Task 1)

Tier 3 — Advanced Features (Build Last):
├── Reconciliation Engine → Requires: GSTR JSON parsing + Evidence Management
│   └── Reconciliation-Powered Responses → Requires: Reconciliation Engine + LLM Response Draft
├── Portal Integration (GST API) → Requires: Client/Entity Management + Notice Data Model
│   └── Email Notice Parsing → Requires: IMAP integration + Existing OCR
├── Multi-Client Dashboard → Requires: Client/Entity Management + Tier 1 Complete
├── Regulation Library → Requires: Notice Classification (for mapping)
└── Escalation Hierarchy → Requires: Alert System + Extended RBAC
```

---

## MVP Recommendation

Given 10-12 week timeline, build in this order:

**Must Have (Weeks 1-4): Notice Tracking Core**
- Notice data model + client/entity management
- Manual notice upload (reuses existing OCR)
- Notice classification (BERT) — this is the AI differentiator
- Notice lifecycle workflow (status transitions)
- Risk scoring (XGBoost) — even with heuristic scoring initially
- T-7/T-3/T-1 email alerts (SendGrid)
- Basic audit trail
- Extended RBAC (4 new roles)

**Should Have (Weeks 5-8): Response and Calendar**
- Template-based response drafting (without LLM first; LLM is enhancement)
- LLM draft generation (extends existing LLM infrastructure)
- Compliance calendar (pre-loaded deadlines)
- Evidence management (link DMS documents to notices)
- In-app notifications (WebSocket)
- Multi-client dashboard for CAs

**Could Have (Weeks 9-12): Integration and Intelligence**
- Approval workflow for responses
- SMS alerts for Critical notices (Twilio)
- Audit reports + health score
- Regulation library (static content)
- GST email parsing (IMAP)
- Cross-system Elasticsearch search
- Reconciliation engine (GST ITC reconciliation)

**Defer to v2.1+:**
- Government portal API auto-fetch (GST/IT/MCA)
- Calendar integration (Google Calendar/Outlook)
- Reconciliation-powered response generation
- Regulation change tracking
- Penalty analytics

---

## Complexity Summary by Feature Category

| Category | Feature Count | Avg Complexity | Highest Complexity Item | Dependency on Task 1 |
|----------|--------------|---------------|------------------------|---------------------|
| Notice Lifecycle | 7 | LOW-MEDIUM | Linked notice chain | LOW (new tables) |
| Notice Classification | 40+ notice types | HIGH | BERT multi-label classifier | MEDIUM (extends OCR pipeline) |
| Risk Scoring | 5 | HIGH | XGBoost model + SHAP | LOW (new ML module) |
| Alert System | 10 | LOW-MEDIUM | Escalation hierarchy | LOW (new service) |
| Audit Trail | 7 | MEDIUM | Immutable audit log | LOW (extends existing audit concepts) |
| Extended RBAC | 6 roles | MEDIUM | Client-scoped isolation | HIGH (extends existing RBAC) |
| AI Response Drafting | 7 | HIGH | Reconciliation-powered responses | HIGH (extends existing LLM) |
| Portal Integration | 5 | VERY HIGH | IT e-filing scraping | LOW (new async jobs) |
| Reconciliation Engine | 5 | HIGH | GSTR-2A/2B vs 3B parser | MEDIUM (document parsing) |
| Compliance Calendar | 6 | MEDIUM | GSTIN-specific deadlines | LOW (new module) |
| Regulation Library | 4 | MEDIUM | Change tracking | LOW (static store) |
| Multi-Client Management | 6 | HIGH | Client isolation (RLS) | HIGH (extends RBAC/auth) |
| Evidence Management | 5 | HIGH | Cross-system search | VERY HIGH (core integration) |

---

## Indian Regulatory Specifics: Accuracy Notes

**HIGH confidence (statutory, well-documented):**
- GST notice form codes (ASMT-10, DRC-01, DRC-01A, DRC-01C, DRC-07, ADT-01, GSTR-3A, REG-17)
- Income Tax notice sections (139(9), 143(2), 148, 148A, 156, 245, 271(1)(c))
- Compliance calendar deadlines (GSTR-1, 3B, 9; TDS quarters; Advance Tax dates; ITR deadlines)
- Penalty regimes (GST late fee ₹200/day; IT penalty 50-200% of tax; SEBI ₹1L-₹25L)

**MEDIUM confidence (observed in practice, may change with GST Council/CBDT circulars):**
- Notice response deadlines (30 days for most; 7 days for DRC-01C and 148A — verify against current rules)
- MCA notice form codes (ROC enforcement procedures are less standardized)
- RBI/SEBI notice categorization (no standardized form codes; categorization is descriptive)

**LOW confidence (verify before building):**
- GST portal API access model for CAs/ASPs (may require GSP empanelment)
- IT e-filing portal API availability (no public documentation found as of training cutoff)
- MCA21 v3 API completeness (developer.mca.gov.in content; verify current status)
- Specific deadline dates for GSTR-9/9C (frequently extended by CBIC notification)

---

## Sources

**Confidence:** Training data through August 2025. No external sources could be verified in this session (web/fetch tools unavailable). Findings marked HIGH confidence are based on statutory law (GST Act, Income Tax Act 1961, Companies Act 2013) which is stable; findings marked LOW confidence relate to portal APIs and regulatory deadlines subject to frequent change.

**Recommended verification before building:**
- GST portal developer documentation: `developer.gst.gov.in`
- MCA21 API documentation: `developer.mca.gov.in`
- CBIC circulars for current GST return deadlines: `cbic.gov.in`
- CBDT circulars for current IT deadlines: `incometax.gov.in`
- IT e-filing e-Proceedings API: contact CPC Bangalore or check SignDesk/ClearTax API docs

---

*Last updated: 2026-03-30 | v2.0 Compliance Management Milestone Research*
