# Project Research Summary

**Project:** Smart Document Management System for IIIT Hyderabad Product Labs
**Domain:** AI-Powered Legal/Financial Document Management SaaS
**Researched:** 2026-02-17
**Confidence:** HIGH

## Executive Summary

This is an AI-powered document management system for legal and finance teams (5-20 users) with a working prototype built on FastAPI, Next.js, and PostgreSQL. The system already handles 6 document categories with ML classification, OCR extraction, and basic search. Research focused on how to extend this foundation with smart data extraction, advanced search, RBAC, and production security without introducing the critical failures that have plagued enterprise document management deployments.

The recommended approach builds on the existing stack rather than replacing it. Add LangChain + OpenAI/Anthropic for intelligent extraction, upgrade to PostgreSQL Full-Text Search (avoiding Elasticsearch complexity), implement hierarchical RBAC with document-level permissions, and integrate OAuth via battle-tested libraries. The architecture follows a "service layer" pattern where new components (extraction, search, permissions, audit) integrate behind existing API routers, preserving the clean separation of concerns.

The three critical risks are: (1) LLM hallucination on legal documents (69-88% hallucination rate on legal queries per Stanford research), (2) data privacy violations from sending confidential documents to external APIs without proper DPAs, and (3) permission bypass vulnerabilities from incomplete RBAC implementations. Mitigate with mandatory confidence scoring + human review, explicit data processing agreements + PII redaction, and comprehensive permission checks at every database query with automated security testing.

## Key Findings

### Recommended Stack

The existing stack (FastAPI + Next.js + PostgreSQL) is production-ready. New dependencies add capabilities without replacing foundations.

**Core technologies:**
- **LangChain Core + Providers** (openai, anthropic): Abstraction layer for user-configurable LLM backend with structured output parsing — enables provider switching without rewriting extraction logic
- **PostgreSQL Full-Text Search** (tsvector + GIN indexes): Scale-appropriate search for 5-20 user teams with millions of documents — no new infrastructure, native relevance ranking, same-transaction consistency
- **spaCy + dateparser**: Local NER for dates, amounts, entities — runs offline, no API costs, complements LLM extraction for sensitive documents
- **Authlib + NextAuth.js**: OAuth/SSO integration — handles Google/Microsoft quirks, state validation, token management automatically
- **structlog + slowapi + secure**: Production hardening — structured JSON logging, rate limiting, security headers (HSTS, CSP)
- **Celery (already configured)**: Wire up async document processing — unblock upload endpoints, handle LLM timeouts gracefully

**Explicit exclusions:**
- Elasticsearch/OpenSearch: Overkill infrastructure for your scale; PostgreSQL FTS sufficient
- Casbin/OPA: Policy engine overkill for 3-role RBAC (Admin, Editor, Viewer)
- Clerk/Auth0: Hosted auth vendor lock-in; self-hosted control critical for legal documents

### Expected Features

**Must have (table stakes):**
- Matter-centric organization (group docs by case/client/matter) — core organizational primitive for legal teams
- Enhanced metadata schema with user-editable fields — foundation for filtering, search, and permissions
- Full-text search with filters (category, date range, amount) — baseline expectation for any DMS
- Document-level RBAC + permissions — security requirement for multi-user legal/finance teams
- Audit trail logging — legal compliance requires "who accessed what when"
- In-browser PDF viewer — users shouldn't download to preview
- Version control with history — track document revisions, enable rollback

**Should have (competitive differentiators):**
- Contract data extraction (parties, dates, amounts, clauses) — AI-first killer feature
- Invoice processing (vendor, total, line items, payment terms) — structured format, high ROI
- Document summarization — LLM-generated 1-paragraph summaries
- Analytics dashboard (upload trends, document types, user activity) — visibility into system usage
- Semantic search (natural language queries) — "find contracts expiring in Q2"
- Extraction confidence scores — show "High/Medium/Low" with color coding

**Defer (v2+):**
- Real-time collaborative editing — users already have Office 365/Google Docs
- E-signature integration — DocuSign/Adobe Sign dominate, integrate later via API
- Email integration — parsing complexity high, drag-and-drop attachments sufficient for v1
- Workflow automation — approval chains defer to v2
- Mobile native apps — responsive web design sufficient, focus on core product first

### Architecture Approach

New capabilities integrate as service layers behind existing API routers, preserving the clean layered architecture. The document upload flow extends from `file_bytes → OCR → classification → DB` to include `→ LLM extraction → AI summary → search index` steps.

**Major components:**

1. **LLM Extraction Service** (`backend/app/services/extraction_service.py`) — Provider abstraction (OpenAI, Anthropic, local patterns) with prompt templates per document type; consumes text from existing ML classifier, returns structured JSON via Pydantic models; called by document router or Celery task

2. **Search Service** (`backend/app/services/search_service.py`) — PostgreSQL FTS implementation using tsvector columns with GIN indexes and ts_rank for relevance; auto-updated via database triggers on INSERT/UPDATE; replaces current ILIKE queries

3. **Permissions Service** (`backend/app/services/permissions_service.py`) — Hierarchical RBAC (Organization → Matter → Document) with document-level permissions; new models: Team, TeamMember, DocumentPermission; replaces simple `user_id` filtering with "accessible documents" queries

4. **OAuth Service** (`backend/app/services/oauth_service.py`) — SSO integration via Authlib (backend) + NextAuth.js (frontend); handles provider-specific quirks (Google prompt=consent, Microsoft offline_access); augments existing email/password auth

5. **Audit Logging Service** (`backend/app/services/audit_service.py`) — Records security-relevant actions (upload, access, download, permission changes); implemented as HTTP middleware + explicit business event logging via BackgroundTasks for non-blocking writes

6. **AI Features Service** (`backend/app/services/ai_service.py`) — Document summaries, insights, Q&A; shares provider abstraction with extraction service; uses Redis for response caching; exposed via new `/api/ai` router

**Integration strategy:** All services integrate via dependency injection at the router layer. Existing `documents.py` router calls extraction service after classification. Permission service wraps database queries via custom SQLAlchemy filters. Audit middleware logs all requests automatically.

### Critical Pitfalls

1. **LLM Hallucination on Legal Documents** — Stanford research found 69-88% hallucination rates on legal queries (ChatGPT-4 at 58%, Llama 2 at 88%); lower court cases hallucinate 75%+ on holdings. **Avoid:** Never use raw LLM output for legal facts without human verification; implement confidence thresholds AND manual review workflows; show extraction confidence prominently; log all LLM I/O for audit trails; use RAG with verified legal databases for Phase 3

2. **Data Privacy Violations with External LLM APIs** — Sending confidential documents to OpenAI/Anthropic violates attorney-client privilege and GDPR Article 44 without proper safeguards; 77% of orgs cite compliance as barrier to gen AI. **Avoid:** Sign Data Processing Agreements with LLM providers; enable opt-out from training data; ensure EU data stays in EU data centers; redact PII before API calls (names, SSNs, account numbers); add user consent tracking; implement client-side encryption for ultra-sensitive clients

3. **RBAC Permission Bypass Vulnerabilities** — Current code only checks `Document.user_id == current_user.id`; adding team/matter-based sharing will break this model; horizontal privilege escalation (User A sees User B's docs) is common failure. **Avoid:** Implement hierarchical permissions (Organization → Matter → Document); add permission checks at EVERY database query with JOINs, not Python loops; test with automated security tests ("user1 cannot access user2's docs"); audit all permission changes; default to "least privilege" (no access unless granted)

4. **Document Encryption Implementation Failures** — Encryption at rest but keys in same database provides false security; current issues: hardcoded SECRET_KEY, no S3 encryption, extracted_text stored as plaintext. **Avoid:** Use S3 SSE-KMS (not SSE-S3), rotate keys quarterly; encrypt sensitive DB fields (extracted_text, filename) with pgcrypto; store keys in AWS Secrets Manager; enforce TLS 1.3 for all traffic; remove hardcoded SECRET_KEY immediately

5. **Database Migration Failures on Production Data** — 80%+ of migrations run over time/budget; TSB Bank migration created "most significant IT disaster in UK banking history" with millions of data inconsistencies. **Avoid:** Set up Alembic immediately with versioned migrations; test on production-scale data in staging (not 100-row test data); write rollback scripts for every migration; validate data integrity post-migration (row counts, foreign key validity); take full backup before migration and test restore

6. **JWT Security Weaknesses** — Current config: 24-hour tokens (too long), symmetric HS256 (asymmetric RS256 preferred), hardcoded SECRET_KEY, no refresh mechanism. **Avoid:** Reduce token lifetime to 30 minutes; implement refresh tokens (7 days) in httpOnly cookies; rotate signing keys monthly; switch to RS256; add token revocation capability; store tokens in httpOnly/secure/SameSite cookies, not localStorage

7. **ML Model Accuracy Degradation** — 91% of ML models degrade over time (MIT); classifier trained on synthetic finance data won't recognize new legal document types or language evolution. **Avoid:** Add "Report Incorrect Classification" feedback UI; log user corrections as ground truth; retrain monthly with production labels; track confidence scores over time (alert if avg drops below 70%); sample 5% of predictions for human review

## Implications for Roadmap

Based on research, suggested 4-phase structure follows dependency chains and risk mitigation priorities:

### Phase 1: Foundation & Security Hardening (Weeks 1-2)
**Rationale:** Eliminate CRITICAL security issues before adding features — hardcoded secrets, weak JWT config, missing encryption block production launch. Set up migration framework and audit logging foundation that all subsequent phases depend on.

**Delivers:**
- Alembic migration framework with initial migration
- Hardcoded SECRET_KEY replaced with environment variables
- JWT token lifetime reduced to 30 minutes with refresh token mechanism
- S3 SSE-KMS encryption enabled
- Structured logging (structlog) throughout codebase
- Audit logging table + service + middleware
- Security headers (HSTS, CSP) via secure package
- Rate limiting (slowapi) on upload/search endpoints

**Addresses (from FEATURES.md):**
- Encryption at rest (table stakes security)
- Audit trail (table stakes compliance)
- Enhanced metadata schema (foundation for Phase 2 features)

**Avoids (from PITFALLS.md):**
- Pitfall 1.4: Encryption implementation failures (S3 encryption, key management)
- Pitfall 1.5: JWT security weaknesses (short-lived tokens, refresh mechanism)
- Pitfall 1.6: Database migration failures (Alembic setup before schema changes)
- Technical Debt 4.1: "We'll add logging later" syndrome (structured logging now)

### Phase 2: RBAC & Advanced Search (Weeks 3-4)
**Rationale:** RBAC is foundational for document-level permissions and matter organization (Phase 3 depends on it). PostgreSQL FTS replaces ILIKE bottleneck before adding smart extraction (which needs good search). These features are independent and can be built in parallel.

**Delivers:**
- Team, TeamMember, DocumentPermission models
- Hierarchical RBAC (Organization → Matter → Document)
- Permission service with "accessible documents" filtering
- Replace ILIKE with PostgreSQL FTS (tsvector + GIN indexes)
- Search service with relevance ranking, highlighted snippets
- Metadata filters (category, date range, amount)
- Security tests for permission boundaries

**Addresses (from FEATURES.md):**
- Matter-centric organization (table stakes, HIGH value/LOW cost)
- Document-level RBAC (table stakes security)
- Full-text search upgrade (table stakes, HIGH value/LOW cost)
- Metadata filters (table stakes)

**Avoids (from PITFALLS.md):**
- Pitfall 1.3: RBAC permission bypass (comprehensive permission checks)
- Pitfall 2.2: Search index sync issues (triggers auto-update tsvector)
- Performance Trap 6.2: ILIKE without indexes (GIN index on tsvector)

**Uses (from STACK.md):**
- PostgreSQL Full-Text Search (tsvector + GIN)
- No new external dependencies (uses existing PostgreSQL)

### Phase 3: LLM Extraction & AI Features (Weeks 5-7)
**Rationale:** Now that security hardening (Phase 1) and RBAC (Phase 2) are in place, add the AI differentiators. LLM integration requires audit logging (Phase 1) for tracking data sent to external APIs and permission checks (Phase 2) for document access control.

**Delivers:**
- LLM Extraction Service with provider abstraction (OpenAI, Anthropic)
- spaCy NER for local extraction (dates, amounts, entities)
- Contract extraction (parties, dates, amounts, clauses)
- Invoice processing (vendor, total, line items)
- Extraction confidence scoring with UI color coding
- Document summarization with Redis caching
- AI Features Service (summaries, insights)
- Wire Celery for full async document processing pipeline
- Data Processing Agreements with LLM providers
- PII redaction before API calls

**Addresses (from FEATURES.md):**
- Contract data extraction (differentiator, HIGH value)
- Invoice processing (differentiator, HIGH value/MEDIUM cost)
- Document summarization (differentiator, HIGH value/LOW-MED cost)
- Extraction confidence scores (differentiator, MEDIUM value/LOW cost)

**Avoids (from PITFALLS.md):**
- Pitfall 1.1: LLM hallucination (confidence scores + human review workflow)
- Pitfall 1.2: Data privacy violations (DPAs, PII redaction, consent tracking)
- Pitfall 2.1: LLM cost explosion (caching, tiered models, cost monitoring)
- Technical Debt 4.2: Synchronous processing (Celery async pipeline)

**Uses (from STACK.md):**
- LangChain Core + openai + anthropic
- spaCy + dateparser + price-parser
- Celery (wire up existing Redis/Celery config)

### Phase 4: SSO, Analytics & Production Hardening (Weeks 8-10)
**Rationale:** With core features complete, add enterprise authentication, visibility dashboards, and production polish. SSO depends on RBAC (Phase 2) for role assignment. Analytics need audit logs (Phase 1) and extracted metadata (Phase 3).

**Delivers:**
- OAuth/SSO integration (Google, Microsoft) via Authlib + NextAuth.js
- Analytics dashboard (upload trends, document types, user activity)
- In-browser PDF viewer (PDF.js or react-pdf)
- Document thumbnails generated on upload
- Version control with revision history
- Bulk upload support (multi-file drag-and-drop)
- Column-level encryption for sensitive DB fields (pgcrypto)
- Prometheus metrics instrumentation
- Production deployment guide

**Addresses (from FEATURES.md):**
- SSO/OAuth integration (enterprise requirement)
- Analytics dashboard (table stakes, HIGH value/LOW cost)
- In-browser PDF viewer (table stakes)
- Version control (table stakes)
- Bulk upload (UX improvement, avoids Pitfall 3.2)

**Avoids (from PITFALLS.md):**
- Pitfall 2.3: OAuth state management bugs (NextAuth.js handles this)
- Pitfall 3.2: Lack of bulk operations (batch upload endpoint)
- Pitfall 3.4: No document preview (PDF.js viewer)

**Uses (from STACK.md):**
- Authlib (backend OAuth)
- next-auth (frontend OAuth)
- react-pdf (PDF viewer)
- @tanstack/react-query (server state management)
- prometheus-fastapi-instrumentator (metrics)

### Phase Ordering Rationale

- **Security first:** Hardcoded secrets, weak JWT, missing encryption block production launch — eliminate before feature development
- **Foundation before features:** RBAC and search are dependencies for extraction (permission checks, searchable extracted data)
- **Audit from day 1:** Logging infrastructure (Phase 1) captures LLM API calls (Phase 3) and OAuth flows (Phase 4) from the start
- **Async before scale:** Celery integration (Phase 3) unblocks upload endpoints before adding bulk operations (Phase 4)
- **Avoid pitfall cascade:** Migration framework (Phase 1) prevents schema change failures in Phases 2-4

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 3 (LLM Extraction):** LLM provider API details, prompt engineering for specific document types, hallucination testing on real legal documents — use `/gsd:research-phase` for extraction accuracy benchmarks and cost modeling
- **Phase 4 (SSO):** OAuth provider-specific quirks (Google vs. Microsoft vs. Okta), token refresh flows, account linking logic — verify with provider documentation

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Foundation):** Alembic migrations, JWT refresh tokens, S3 encryption — well-documented, established patterns
- **Phase 2 (RBAC & Search):** PostgreSQL FTS setup, RBAC models — reference existing implementations, no novel integration

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations based on official docs + production use cases; versions need verification against PyPI/npm but architecture choices sound |
| Features | HIGH | Based on competitor analysis (NetDocuments, iManage, M-Files, DocuWare) and domain-specific research; prioritization matrix validated against legal/finance DMS requirements |
| Architecture | HIGH | Integration strategy leverages existing clean layered architecture; service boundaries well-defined; migration path from current codebase clear |
| Pitfalls | HIGH | Backed by real-world incidents (TSB Bank migration disaster, ChatGPT lawyer sanctions) and recent research (Stanford LLM hallucination study 2024, JWT CVEs 2025) |

**Overall confidence:** HIGH

### Gaps to Address

- **LLM extraction accuracy on YOUR document types:** Research cites general legal document hallucination rates (69-88%) but actual performance depends on your specific contract/invoice formats — validate with real documents during Phase 3 implementation, not assumptions
- **PostgreSQL FTS scale limits:** Research confirms FTS handles millions of documents but breaking point depends on query complexity and concurrent load — monitor query performance in production, plan Elasticsearch migration if p95 latency exceeds 1 second
- **Compliance certifications timeline:** Research identifies SOC 2, GDPR, HIPAA as requirements but doesn't estimate audit timeline — consult compliance specialist during Phase 4 to set realistic expectations (typically 3-6 months)
- **ML model retraining pipeline:** Research documents degradation risk (91% of models degrade over time) but specific retraining cadence depends on production feedback volume — implement classification correction UI in Phase 3, evaluate monthly retraining in Phase 4 based on data

## Sources

### Primary (HIGH confidence)
- **Stack Research:** Official documentation (FastAPI, LangChain, PostgreSQL, Authlib, NextAuth.js); PyPI/npm package repositories; vendor-specific guides (OpenAI, Anthropic APIs)
- **Features Research:** Competitor product reviews (DocuWare, M-Files, iManage, NetDocuments); legal tech trend reports (NetDocuments 2026 Legal Tech Trends); DMS buyer guides (Clinked, MyLegalSoftware)
- **Architecture Research:** FastAPI design patterns; LangChain integration guides; PostgreSQL Full-Text Search documentation; SQLAlchemy best practices
- **Pitfalls Research:** Stanford Law (Hallucinating Law study 2024); security vulnerability databases (CVE-2024-10318 OAuth, JWT CVE list 2025); incident post-mortems (TSB Bank migration 2018)

### Secondary (MEDIUM confidence)
- Industry benchmarks (Bloor Group migration failure rates 80%+, MIT model degradation 91%)
- Best practice guides (FastAPI production deployment, RBAC implementation patterns)
- DMS implementation challenges (LexWorkplace, Filevine)

### Tertiary (LOW confidence, needs validation)
- LLM API pricing estimates (subject to provider changes)
- Performance benchmarks (PostgreSQL FTS scale limits vary by hardware)
- Emerging features (semantic search, Q&A over documents — defer to Phase 5+)

---
*Research completed: 2026-02-17*
*Ready for roadmap: yes*
