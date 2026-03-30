# Project Research Summary

**Project:** Smart Document Management & Compliance System — v2.0 Compliance Management Milestone
**Domain:** AI-powered Indian regulatory compliance management layer on existing document management system
**Researched:** 2026-03-30
**Confidence:** MEDIUM overall (stack/architecture HIGH; Indian portal APIs LOW)

---

## Executive Summary

This project adds a compliance management vertical to an existing, fully operational document management system (FastAPI, Next.js 15, PostgreSQL, Celery, Redis on Render/Vercel). The core challenge is not building a new system — the underlying infrastructure is already battle-tested — but extending it with ML-powered notice classification, risk scoring, deadline tracking, and alert routing tailored to India's multi-authority regulatory environment (GST, Income Tax, MCA, RBI, SEBI). The recommended approach is a vertical slice extension: new compliance modules live inside the existing codebases, sharing all infrastructure, with no microservices split. PostgreSQL remains the authoritative source of record; Elasticsearch is added as a sidecar search index for cross-entity queries and compliance dashboard facets.

The recommended stack additions are deliberate and proportional: BERT fine-tuning (transformers 4.41) for notice classification (discriminative task — outperforms LLMs at 1/10th inference cost), spaCy 3.7 for structured entity extraction (with regex-first fallback for Indian-specific identifiers like GSTIN/PAN/CIN), and XGBoost with SHAP values for risk scoring (tabular feature input, interpretability required for audit). The ML stack is isolated to a dedicated Celery worker (2GB RAM) to prevent degradation of existing v1.0 functionality. Frontend additions are minimal: Zustand for UI state, TanStack Query for server state, react-big-calendar for the compliance calendar, and @tanstack/react-table for the notices table — all proven choices that avoid overengineering.

The highest risks are not technical but operational and regulatory. Indian government portal APIs (GST, IT, MCA) have undocumented rate limits, inconsistent uptime, and access model ambiguity for CA firms (GSP empanelment may be required). Portal integration must be designed with graceful degradation so manual upload and email parsing always work regardless of portal availability. The ML classification pipeline must not auto-route notices until calibrated with 300+ real labeled examples per class — a SEBI notice misclassified as routine GST could result in a missed 25 lakh rupee penalty response window. Audit trail immutability must be enforced at the database level from day one; retrofitting is a data migration, not a code change.

---

## Key Findings

### Recommended Stack

The existing stack is well-chosen and requires no changes for v2.0. New additions are strictly additive. The most significant infrastructure addition is splitting the single Celery worker into two: a default worker for existing document tasks and a dedicated `ml_tasks` worker (2GB RAM limit) for BERT/spaCy/XGBoost inference. Elasticsearch is strongly recommended as a managed service (Elastic Cloud) rather than self-hosted on Render to avoid OOM-induced index corruption.

See full details: `.planning/research/STACK.md`

**Core new technologies:**
- `transformers==4.41.2` + `torch==2.3.0+cpu`: BERT fine-tuning for notice classification — discriminative task where fine-tuned BERT hits 92%+ vs scikit-learn TF-IDF ceiling of 85%
- `spacy==3.7.4` + `en_core_web_lg`: NER extraction for Indian regulatory entities — runs in <50ms vs 2-8s LLM extraction; regex-first for structured IDs (GSTIN/PAN/CIN)
- `xgboost==2.0.3` + `shap==0.45.0`: Tabular risk scoring with explainability — tree-based models outperform NNs on tabular data; SHAP required for auditor reports
- `elasticsearch==8.13.0`: Cross-entity search across notices and documents with compliance dashboard aggregations — Elastic Cloud managed deployment strongly preferred over self-hosted
- `apscheduler==3.10.4`: Periodic compliance jobs (portal polling, deadline scans, ES sync) — runs inside FastAPI process, dispatches to Celery for heavy work
- `sendgrid==6.11.0` + `twilio==9.0.4`: Email (primary) and SMS (Critical/High notices only) alert delivery
- `beautifulsoup4==4.12.3` + `lxml==5.2.0`: RBI/SEBI portal scraping (no official APIs)
- `zustand@^4.5.2` + `@tanstack/react-query@^5.40.0`: Frontend UI state and server state management
- `react-big-calendar@^1.13.1` + `@tanstack/react-table@^8.17.0`: Compliance calendar and notices data table

**Critical infrastructure change:** Split Celery into `celery_worker_default` (1GB, handles existing document tasks) and `celery_worker_ml` (2GB, handles BERT/spaCy/XGBoost). BERT model ~420MB + spaCy ~560MB cannot coexist in a 1GB worker.

### Expected Features

See full details: `.planning/research/FEATURES.md`

The feature landscape spans 13 categories across three tiers, with well-defined dependencies and an explicit MVP recommendation for a 10-12 week timeline.

**Must have (table stakes — weeks 1-4):**
- Notice lifecycle management: Received to Under Review to Response Drafted to Submitted to Resolved workflow with full audit trail
- Notice metadata capture: notice number, authority, type, GSTIN/PAN, AY/FY, deadline, penalty amount via NER extraction
- Manual notice upload reusing existing OCR pipeline
- Notice classification: BERT-based multi-label classifier covering 40+ Indian notice types (GST, IT, MCA, RBI, SEBI)
- Risk scoring (XGBoost): automated 0-100 risk score on notice creation with Critical/High/Medium/Low tiers
- T-7/T-3/T-1 deadline alerts via email (SendGrid); overdue alerts
- Extended RBAC: Compliance Head, Legal Team, Finance Team, Auditor, CA/Tax Consultant, Staff roles
- Client/entity management: multiple GSTINs, PANs, CINs per client with row-level data isolation
- Immutable audit trail: append-only with database-level enforcement

**Should have (differentiators — weeks 5-8):**
- Template-based response drafting (20+ notice types) with LLM draft generation via existing 5-provider fallback
- Compliance calendar with pre-loaded Indian statutory deadlines (GSTR-1/3B/9, TDS quarters, Advance Tax, ITR, ROC filings)
- Evidence management: link DMS documents to notice responses as exhibits
- In-app real-time notifications via WebSocket and Redis pub/sub
- Multi-client dashboard for CA/tax consultant workflow

**Could have (weeks 9-12):**
- Multi-stage approval workflow (Drafter to Reviewer to Legal to CFO)
- SMS alerts for Critical notices (Twilio)
- Audit reports and compliance health score
- Regulation library (static, searchable)
- GST ITC reconciliation engine (GSTR-2A/2B vs 3B mismatch analysis)
- Cross-entity Elasticsearch search

**Defer to v2.1+:**
- Government portal API auto-fetch (blocked by GSP empanelment requirements)
- Calendar integration (Google Calendar/Outlook)
- Reconciliation-powered response generation
- Predictive compliance analytics (requires 12+ months of data)
- WhatsApp notifications (Business API approval complexity)

### Architecture Approach

The compliance system is a vertical slice extension of the existing application, not a separate service. All 8 new tables connect via foreign keys to the existing 8 tables (`users`, `documents`, etc.) in the same PostgreSQL database. The new `app/compliance/` package contains its own routers, models, services, ML modules, tasks, and scheduler in a self-contained structure. Existing code is modified only additively: new router includes in `main.py`, new role values in the `UserRole` enum, new config vars, and Docker Compose service additions.

See full details: `.planning/research/ARCHITECTURE.md`

**Major components:**
1. **NoticeIngestionService** — receives notices from portals, email, and manual upload; triggers the processing pipeline; reuses existing OCR infrastructure
2. **ComplianceClassifierService** — BERT-based notice classification + spaCy NER extraction; runs async in dedicated Celery `ml_tasks` queue; results hydrate notice record fields
3. **RiskScoringService** — XGBoost scoring from extracted features; null penalty amount defaults to HIGH risk to fail safe; SHAP explanations for audit reports
4. **PortalClientService** — unified `PortalClient` ABC with per-portal implementations (GSTPortalClient, ITPortalClient, MCAPortalClient, RBIScraperClient, SEBIScraperClient, EmailParserClient); encrypted credential vault in PostgreSQL
5. **NotificationService** — routes alerts via email/SMS/WebSocket based on configurable rules; deduplicated; tiered by risk level; Celery async delivery
6. **ResponseDraftService** — LLM draft generation reusing existing LLM infrastructure; version control; multi-stage approval workflow
7. **ElasticsearchSyncService** — transactional outbox pattern: write to `search_index_queue` PostgreSQL table first, then sync to ES; daily reconciliation job; PostgreSQL FTS fallback mandatory
8. **APScheduler (in-process)** — portal polling (every 6 hours), deadline scans (daily 8am IST), ES sync (every 30 seconds), report generation; dispatches heavy work to Celery

**Key architectural constraints:**
- PostgreSQL is always the system of record; ES is eventually consistent and non-authoritative
- All business logic reads (status, deadline, risk score) query PostgreSQL directly
- Celery task arguments must contain only notice IDs, never notice content (PII protection)
- Models loaded once per worker process via module-level singleton; never per-request

### Critical Pitfalls

See full details: `.planning/research/PITFALLS.md`

1. **BERT miscalibration causing high-priority notice misrouting** — A SEBI notice misclassified as routine GST means Legal never sees it and a penalty response window is missed. Prevention: no auto-routing below 0.75 calibrated confidence; human review queue; two-stage classifier (authority first, then notice type); 300+ real labeled examples per class before production deployment; temperature scaling post-training.

2. **Government portal session expiry returning silent empty results** — Portal sessions expire mid-run; the scraper records "no new notices" rather than "retrieval failed"; deadlines never start. Prevention: explicit three-state distinction (SUCCESS_EMPTY, SUCCESS_WITH_RESULTS, FETCH_FAILED); PortalFetchLog on every run; admin alert on two consecutive failures; HTML content-type check to detect redirect-to-login.

3. **Audit trail mutability under regulatory inspection** — Application-level audit logs can be mutated by any user with DB credentials; concurrent writes cause last-write-wins data loss; legally worthless in disputes. Prevention: PostgreSQL-level REVOKE UPDATE and DELETE on audit_logs; INSERT-only trigger; GENERATED ALWAYS AS IDENTITY for IDs; clock_timestamp() for timestamps; hash chaining; optimistic locking with version column.

4. **PII exposure in logs, Redis queues, and Elasticsearch** — GSTIN, PAN, penalty amounts in plaintext in Celery task args, application logs, and ES source fields constitutes a breach under India's DPDP Act 2023 (up to 250 crore rupee fine). Prevention: field-level Fernet encryption for PII; ID-only Celery args; structured log field blocklist; Redis AUTH and TLS in all environments.

5. **v1.0 performance degradation from ML cold starts** — BERT loads in 10-15 seconds; sharing a Celery worker with existing document tasks causes upload endpoint latency to spike from 200ms to 2-3 seconds; Render health checks timeout and trigger restart loops. Prevention: dedicated `ml_tasks` Celery queue in separate worker (2GB); module-level model singleton; p95 regression tests in CI before any v2.0 deployment.

6. **Indian regulatory deadline calculation ignoring holidays and circulars** — `notice_date + timedelta(days=N)` produces legally incorrect deadlines. Prevention: RegulatoryCalendar table pre-populated with CBDT/CBIC/state holidays; DeadlineExtension table for ad hoc circular extensions; all datetimes in UTC, displayed as IST (zoneinfo, Asia/Kolkata).

---

## Implications for Roadmap

Based on the feature dependency tree in FEATURES.md and the architectural constraints, the following phase structure is recommended. The dependency tree is clear: the compliance data model must exist before any feature can be built, and ML must be calibrated before it can be trusted in any automated workflow.

### Phase 1: Compliance Foundation (Data Model + RBAC + Manual Workflow)

**Rationale:** Everything else depends on this. No feature can be built without the `notices` table, client/entity management, and extended RBAC. This phase is also where audit trail immutability must be established — retrofitting is a data migration, not a code fix. Building the manual upload and basic lifecycle workflow first allows real notice data to accumulate for ML training before the classifier is deployed.

**Delivers:** Functional notice tracking system (manual-only) with full audit trail and multi-client support. CA teams can begin logging notices immediately, even before ML is ready.

**Addresses:** Notice lifecycle management, manual notice upload (OCR reuse), notice metadata capture, extended RBAC (6 roles), client/entity management, basic audit trail, notice status workflow UI.

**Avoids:** Pitfall 4 (audit trail mutability — must be enforced from day one); Pitfall 14 (multi-GSTIN data isolation — repository-layer entity scoping must be established before features are built on top of it).

**Research flag:** Standard patterns — no phase research needed. Schema design is fully specified in ARCHITECTURE.md; PostgreSQL trigger and RLS patterns are stable.

### Phase 2: ML Classification + Risk Scoring

**Rationale:** The AI differentiators (BERT classification, XGBoost risk scoring, spaCy NER) must be built and calibrated before any automated routing or escalation can be trusted. This phase is entirely backend ML work; no UI needed beyond confidence indicators and a human review queue. Running this phase second allows Phase 1 to accumulate real notice data for training.

**Delivers:** Automated notice classification with confidence scores, structured entity extraction, and XGBoost risk scores with SHAP explanations. Human review queue for low-confidence predictions. All ML inference isolated in the dedicated `celery_worker_ml` service.

**Addresses:** BERT notice classifier (40+ types), spaCy NER with regex-first for GSTIN/PAN/CIN/section references, XGBoost risk scoring with SHAP, risk tier labels (Critical/High/Medium/Low), model loading singleton pattern.

**Avoids:** Pitfall 1 (BERT miscalibration — temperature scaling and 300+ real examples required before any auto-routing); Pitfall 9 (spaCy missing Indian regulatory entities — regex-first architecture); Pitfall 5 (v1.0 degradation — dedicated ML Celery worker, model singleton); Pitfall 12 (concept drift — OOD detection via entropy, UNKNOWN_TYPE class).

**Research flag:** NEEDS phase research. BERT fine-tuning on Indian regulatory text, two-stage classifier design, and temperature scaling calibration are non-trivial ML engineering steps. The base model choice (bert-base-uncased vs. ai4bharat/indic-bert vs. legal-bert-base-uncased) needs empirical validation on the specific training dataset.

### Phase 3: Alert System + Compliance Calendar

**Rationale:** Once risk scores exist, the alert infrastructure can consume them. Alert priority tiers must be designed before implementation — not retrofitted — to avoid notification fatigue. Compliance calendar is a self-contained module that can be built in parallel with the alert system since it shares the same deadline infrastructure.

**Delivers:** Tiered T-7/T-3/T-1 deadline alerts (email via SendGrid, in-app via WebSocket), overdue notice escalation, pre-loaded Indian statutory compliance calendar (GSTR-1/3B/9, TDS, Advance Tax, ITR, ROC), deadline recalculation with Indian holiday calendar.

**Addresses:** SendGrid email alerts, Twilio SMS for Critical notices, in-app WebSocket notifications (Redis pub/sub), APScheduler periodic jobs, RegulatoryCalendar table with CBDT/CBIC holiday data, DeadlineExtension table for circular-based deadline changes.

**Avoids:** Pitfall 6 (naive deadline calculation — RegulatoryCalendar table from day one); Pitfall 7 (notification fatigue — CRITICAL/HIGH/MEDIUM/LOW tiers with conservative defaults before first alert fires); Pitfall 15 (WebSocket silent disconnect — 30-second heartbeat with client auto-reconnect).

**Research flag:** Standard patterns for SendGrid/Twilio and WebSocket heartbeat. Operational research needed for RegulatoryCalendar data sourcing (current-year CBDT/CBIC/state holiday lists must be sourced from official publications before pre-loading).

### Phase 4: Response Drafting + Evidence Management

**Rationale:** Response drafting builds on the existing LLM infrastructure (already has 5-provider fallback) and notice classification from Phase 2. Evidence management requires the document-to-notice linking layer and depends on Phase 1 notice data model. These two features are tightly coupled because a response draft without evidence attachment is incomplete for most Indian compliance notices.

**Delivers:** Template library for 20+ notice types, LLM-assisted draft generation using existing LLM service, multi-stage approval workflow, evidence package assembly (link DMS documents to notice response), document preview in response context.

**Addresses:** Response draft service, `response_drafts` table with versioning, `notice_document_links` junction table, multi-stage approval (Drafter to Reviewer to Legal to CFO), approval status in audit trail.

**Avoids:** Pitfall 4 (audit trail — each approval stage must be logged immutably at the DB level); response version control prevents draft data loss.

**Research flag:** LLM response drafting extends existing infrastructure (no research needed for the LLM layer). Needs phase research for the multi-stage approval workflow UX — specifically, how to handle concurrent review by multiple parties without conflicting edits.

### Phase 5: Elasticsearch + Cross-Entity Search

**Rationale:** Elasticsearch is deferred until core tracking, ML, and response workflows are operational. The compliance dashboard must be functional without ES (PostgreSQL FTS fallback is mandatory). Adding ES last means index design can be informed by the actual query patterns observed in Phases 1-4.

**Delivers:** Cross-entity unified search (notices + documents in a single query), compliance dashboard faceted filtering by authority/status/risk/deadline, transactional outbox sync from PostgreSQL to ES, daily reconciliation job.

**Addresses:** `elasticsearch==8.13.0` (Elastic Cloud deployment), ElasticsearchSyncService with transactional outbox pattern, ES health check with automatic fallback to PostgreSQL FTS, `compliance_search` alias across `notices` and `documents` indices.

**Avoids:** Pitfall 2 (Elasticsearch OOM — Elastic Cloud managed service, not self-hosted on Render); Pitfall 10 (ES index drift — transactional outbox, daily reconciliation, `es_indexed_at` timestamp, PostgreSQL FTS fallback always active).

**Research flag:** Standard Elasticsearch integration patterns. Managed Elastic Cloud deployment is well-documented. No phase research needed beyond verifying current Elastic Cloud free/starter tier pricing and limits.

### Phase 6: Government Portal Integration

**Rationale:** Deferred last because portal integration is the highest-risk, lowest-certainty component. GST GSP empanelment, IT portal API availability, and RBI/SEBI scraping stability must all be validated empirically before engineering time is committed. The system is fully functional (Phases 1-5) without portal integration; email parsing and manual upload provide reliable intake channels.

**Delivers:** GST portal notice auto-fetch (pending GSP empanelment validation), IT e-filing portal integration (pending API access validation), RBI/SEBI public notice scraping with bot-detection resistance, email notice parsing (IMAP), PortalFetchLog monitoring, session health checks with automatic re-authentication, Redis distributed lock to prevent duplicate notice creation.

**Addresses:** PortalClientService with per-portal implementations, encrypted credential vault (`portal_credentials` table, Fernet encryption), rate limiting via Redis token buckets, HTML structural validation for scraping responses.

**Avoids:** Pitfall 1 (session expiry silent empty result — explicit three-state fetch status, PortalFetchLog on every run); Pitfall 8 (CAPTCHA blocking — structural validation, admin alert for 48-hour zero-result streaks); Pitfall 13 (CI/CD live portal calls — PortalClientStub via dependency injection); Pitfall 16 (duplicate notices on restart — DB UNIQUE constraint + Redis distributed lock).

**Research flag:** NEEDS phase research. GST API access model for CA firms (ASP vs. GSP empanelment), IT e-filing e-Proceedings API availability, and current RBI/SEBI portal bot-detection behavior all require empirical verification before any implementation begins. This phase cannot be planned without these answers.

### Phase Ordering Rationale

- **Foundation before features:** Every compliance feature depends on the notices data model, client/entity management, and RBAC — these must come first without exception.
- **Data before ML:** The ML classifier needs real labeled notice data to train on. Phase 1 accumulates real data while Phase 2 is being developed, reducing the training data gap.
- **ML before automation:** Automated routing and escalation are only safe after the classifier is calibrated. Building alert infrastructure (Phase 3) after ML (Phase 2) prevents deploying auto-routing on an uncalibrated model.
- **Search last:** Elasticsearch cross-entity search is an enhancement to a functional system. Deferring it to Phase 5 means the compliance dashboard works (via PostgreSQL FTS fallback) throughout Phases 1-4, and ES index design is informed by real query patterns.
- **Portal integration last:** The highest uncertainty feature goes last so its delays or blockers (GSP empanelment, API availability) do not delay the rest of the roadmap.

### Research Flags

**Needs `/gsd:research-phase` during planning:**
- **Phase 2 (ML Classification):** Two-stage BERT classifier design, base model selection for Indian regulatory text, temperature scaling calibration workflow, training data sourcing strategy, and OOD detection implementation are non-trivial and require deeper ML engineering research before implementation can be planned in detail.
- **Phase 6 (Portal Integration):** GST API access model for CA firms (ASP/GSP empanelment status), IT e-filing e-Proceedings API availability, and RBI/SEBI portal scraping feasibility from Render's AWS-hosted IPs all require empirical validation. This phase cannot be planned without verified answers.

**Standard patterns (skip research-phase):**
- **Phase 1 (Foundation):** PostgreSQL schema design, FastAPI CRUD, RBAC extension, and audit trail patterns are fully specified in ARCHITECTURE.md and PITFALLS.md.
- **Phase 3 (Alerts + Calendar):** SendGrid, Twilio, WebSocket heartbeat, and APScheduler patterns are all well-documented with clear integration points.
- **Phase 4 (Response Drafting):** Extends existing LLM infrastructure using established patterns.
- **Phase 5 (Elasticsearch):** Elastic Cloud deployment, transactional outbox sync, and FTS fallback are well-documented patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core library choices (BERT/transformers, spaCy, XGBoost, Elasticsearch, APScheduler, Zustand, React Query) are stable, widely-used, and directly integrate with existing infrastructure. Versions need verify-on-PyPI/npm before pinning. |
| Features | MEDIUM | GST/IT notice taxonomy and compliance calendar deadlines are statutory and HIGH confidence. Indian portal API access models (GSP empanelment, IT e-Proceedings) are LOW confidence — must be verified before Phase 6 planning. |
| Architecture | HIGH | Architecture was derived from direct codebase analysis of the existing system plus established integration patterns. The vertical slice approach with PostgreSQL as system of record and ES as sidecar is a proven pattern. Component boundaries and data model are well-specified. |
| Pitfalls | HIGH | Pitfalls 1-5 (ML miscalibration, portal session expiry, audit trail mutability, PII exposure, v1.0 degradation) are all based on documented, stable technical behaviors with established prevention patterns. Pitfall mitigations are specific enough to implement directly. |

**Overall confidence:** MEDIUM-HIGH. The architecture and stack decisions are solid. The primary uncertainty areas are (1) Indian government portal API access and stability, (2) BERT training data availability and calibration timeline, and (3) specific deadline dates that may have been extended by CBIC/CBDT circulars issued after August 2025 training cutoff.

### Gaps to Address

- **GST API access model for CA firms:** Verify whether direct taxpayer API access vs. GSP empanelment is required. If GSP empanelment is mandatory, Phase 6 portal integration may need to use third-party API aggregators (ClearTax, SignDesk) at licensing cost — this changes the Phase 6 architecture and budget. Verify at `developer.gst.gov.in` before Phase 6 planning.
- **IT e-filing e-Proceedings API:** No public documentation found. Contact CPC Bangalore directly or evaluate third-party API aggregators before committing to Phase 6 scope for IT portal integration.
- **BERT training data volume:** The research assumes 300+ real labeled examples per class (40+ classes). Sourcing this labeled dataset is a project dependency that should be confirmed before Phase 2 begins. If insufficient real examples exist, a synthetic data augmentation strategy is needed.
- **Current-year holiday calendars:** RegulatoryCalendar table seed data (CBDT/CBIC/state gazetted holidays for 2026) must be sourced from official government publications before Phase 3 deadline calculation is implemented. Check `cbic.gov.in` and relevant state government gazettes.
- **Render load balancer idle timeout:** Verify current value in Render documentation to set the correct WebSocket heartbeat interval (research estimates 30-second server-side heartbeat, but this should be confirmed before Phase 3 WebSocket implementation).
- **GSTR-9/9C deadline extensions:** Pre-loaded calendar deadlines for GSTR-9/9C should be verified against the most recent CBIC circular before seeding the compliance calendar, as these are frequently extended by notification.

---

## Sources

### Primary (HIGH confidence)
- HuggingFace `transformers` documentation — BERT fine-tuning, pipeline API, model inference
- spaCy 3.x documentation and model cards — NER training, en_core_web_lg corpus scope
- XGBoost documentation — tabular ML, SHAP integration
- Elasticsearch Python client documentation — ES 8.x indexing, alias, aggregation API
- FastAPI WebSocket documentation — native WebSocket, Starlette integration
- PostgreSQL documentation — triggers, clock_timestamp(), GENERATED ALWAYS AS IDENTITY, RLS
- GST Act, Income Tax Act 1961, Companies Act 2013 — notice taxonomy, statutory deadlines, penalty regimes
- Grinsztajn et al. (2022), NeurIPS — tree-based models vs. deep learning on tabular data (XGBoost rationale)

### Secondary (MEDIUM confidence)
- Indian CA/compliance software patterns (ClearTax, LegalWiz, TallyPrime feature landscape)
- APScheduler documentation — AsyncIOScheduler, FastAPI lifespan integration
- SendGrid Python SDK, Twilio Python helper library documentation
- RBI press release structure (rbi.org.in), SEBI enforcement orders page structure

### Tertiary (LOW confidence — verify before building)
- GST portal developer documentation (`developer.gst.gov.in`) — API access model, session behavior, rate limits
- IT e-filing e-Proceedings API — no public documentation found; verify via CPC Bangalore or ClearTax/SignDesk
- MCA21 v3 API (`developer.mca.gov.in`) — partial documentation; verify current completeness
- RBI/SEBI portal bot detection behavior — empirical verification required before implementing scrapers
- Render load balancer idle timeout — verify in current Render documentation

---

*Research completed: 2026-03-30*
*Scope: v2.0 Compliance Management Milestone additions to existing Smart-Document-Management-System*
*Ready for roadmap: yes*
