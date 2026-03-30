# Smart Document Management & Compliance System

## What This Is

An AI-powered platform for document management and regulatory compliance automation. Started as a document management system (Task 1) that classifies, extracts, and organizes personal/business documents. Now expanding into compliance management (Task 2) — automating the tracking, classification, and resolution of legal and financial notices from Indian regulatory authorities (RBI, SEBI, GST, Income Tax, Legal). Built for IIIT Hyderabad Product Labs.

## Core Value

**Automated classification and intelligent management of documents and compliance notices** — upload any document or notice and the system automatically identifies its type, extracts key data, tracks deadlines, and assists with responses. The compliance layer ensures nothing falls through the cracks across RBI, SEBI, GST, Income Tax, and legal authorities.

## Current Milestone: v2.0 Compliance Management System

**Goal:** Add AI-powered compliance notice management for Indian regulatory authorities to the existing document management system, with automated retrieval from government portals, BERT-based classification, risk scoring, AI-assisted response drafting, and full audit trails.

**Target features:**
- Automated notice retrieval from government portals (GST, IT, MCA) + email parsing + manual upload
- AI notice classification (BERT) across 6 authority categories with NER extraction
- Compliance tracking dashboard with status workflow, risk scoring (XGBoost), and priority assessment
- Multi-channel alert system (email, SMS, in-app) with smart escalation reminders
- AI-assisted response drafting (LLM) with reconciliation-powered responses and collaborative workflow
- Regulatory compliance library with regulation repository, compliance calendar, and regulation mapping
- Complete audit trail with immutable logs, compliance reports, and analytics
- Deep integration with existing document management (shared auth, cross-system search, evidence linking)
- Extended RBAC (Compliance Head, Legal Team, Finance Team, Auditor roles) + client management for CAs

## Requirements

### Validated

<!-- Shipped and confirmed valuable in v1.0. -->

- ✓ User authentication (register, login, logout) with JWT token rotation and reuse detection — v1.0 Phase 1
- ✓ OAuth SSO integration (Google, Microsoft) — v1.0 Phase 6
- ✓ Multi-format document upload (PDF, JPG, PNG, DOCX) with file validation — v1.0 Phase 2
- ✓ OCR text extraction with image preprocessing (deskew, threshold, noise removal) — v1.0 Phase 2
- ✓ PDF text extraction (pdfplumber) — v1.0 Phase 2
- ✓ Async document processing via Celery with progress tracking — v1.0 Phase 2
- ✓ ML-powered document classification (85% accuracy, Linear SVC on 7 Kaggle datasets) — v1.0 Phase 3
- ✓ Confidence score display for classifications — v1.0 Phase 3
- ✓ Model evaluation with confusion matrix, precision/recall/F1 — v1.0 Phase 3
- ✓ Full-text search with PostgreSQL FTS (tsvector + GIN + ts_rank) — v1.0 Phase 4
- ✓ Fuzzy search for partial matches (pg_trgm) — v1.0 Phase 4
- ✓ Filter by category, date range, amount — v1.0 Phase 4
- ✓ LLM-powered smart extraction (dates, amounts, vendors) with 5-provider fallback — v1.0 Phase 5
- ✓ AI-powered document summaries and insights — v1.0 Phase 5
- ✓ Role-based access control (admin, editor, viewer) — v1.0 Phase 6
- ✓ Document-level permissions and sharing — v1.0 Phase 6
- ✓ Document preview (PDF/image viewer in browser) — v1.0 Phase 7
- ✓ Analytics dashboard (documents by category, monthly trends, upload stats) — v1.0 Phase 7
- ✓ Version control for documents with rollback — v1.0 Phase 7
- ✓ Production security hardening (structured logging, rate limiting, encryption) — v1.0 Phase 1
- ✓ 180+ automated tests, 4-job CI/CD pipeline — v1.0 Phase 8
- ✓ Production deployment (Vercel frontend, Render backend) — v1.0 Phase 8

### Active

<!-- v2.0 Compliance Management System scope. -->

**Notice Retrieval & Classification:**
- [ ] Auto-fetch notices from GST portal API
- [ ] Auto-fetch notices from Income Tax e-filing portal API
- [ ] Auto-fetch notices from MCA portal API
- [ ] Web scraping for RBI/SEBI notices (no official API)
- [ ] Email integration to capture notices sent via official email
- [ ] Manual upload option for physical/postal notices
- [ ] OCR-based text extraction from scanned notices
- [ ] BERT-based notice classification across 6 authority categories
- [ ] NER extraction (notice number, date, authority, deadline, penalty, legal sections)

**Compliance Tracking & Dashboard:**
- [ ] Multi-GSTIN/PAN centralized dashboard
- [ ] Status workflow (Received -> Under Review -> Response Drafted -> Submitted -> Resolved)
- [ ] Filter by authority, notice type, status, priority, deadline
- [ ] Link related notices (show cause -> assessment order)
- [ ] AI risk scoring (XGBoost) based on penalty, deadline, authority, history
- [ ] Automatic escalation for high-risk notices

**Alert System:**
- [ ] Email alerts for new notices and approaching deadlines
- [ ] SMS alerts for critical/high-priority notices
- [ ] In-app push notifications
- [ ] Smart reminder system (T-7, T-3, T-1, overdue)
- [ ] Customizable alert rules per notice type
- [ ] Calendar integration (Google Calendar, Outlook)

**AI Response Management:**
- [ ] AI-powered response draft generation (LLM)
- [ ] Template library for common notice types
- [ ] Reconciliation-powered responses (GSTR-2A/2B vs 3B, ITC mismatch analysis)
- [ ] Multi-stage approval workflow (Reviewer -> Legal -> CFO -> Submit)
- [ ] Version control for response drafts
- [ ] Document attachment from existing document system

**Regulatory Library:**
- [ ] Master regulation repository (RBI, SEBI, GST, IT, Companies Act)
- [ ] Regulation-to-notice mapping
- [ ] Compliance calendar with pre-loaded statutory deadlines
- [ ] Track regulation changes with version history

**Audit Trail & Reporting:**
- [ ] Immutable timestamped audit logs for all activities
- [ ] Compliance reports (by authority, type, status)
- [ ] Penalty analysis (paid vs avoided)
- [ ] Response time analytics
- [ ] Compliance health score
- [ ] Auditor-ready export (PDF, Excel)

**Integration with Document Management:**
- [ ] Auto-link documents from Task 1 to compliance notices
- [ ] Unified search across documents and notices
- [ ] Two-way sync for compliance-related documents
- [ ] Evidence management for notice responses

**Extended User Roles:**
- [ ] Compliance Head role (view all notices, approve responses, reports)
- [ ] Legal Team role (draft responses, access regulation library)
- [ ] Finance Team role (view tax notices, reconciliation data)
- [ ] Auditor role (read-only access for inspections)
- [ ] Client management for CAs/tax consultants (multi-client dashboard)

### Out of Scope

- Mobile native apps — web-first, responsive design sufficient for v2
- Multi-tenant SaaS architecture — single-tenant for v2
- Real-time collaboration (co-editing) — document management, not co-editing
- Blockchain audit trail — unnecessary complexity for v2
- Multi-language OCR (regional languages) — v3 feature
- WhatsApp notifications — v3 feature, requires Business API setup
- Predictive compliance analytics — v3 feature
- External counsel portal — v3 feature
- Advanced legal AI (case law search, Indian Kanoon integration) — v3 feature
- Kubernetes orchestration — Docker Compose sufficient for v2
- Automated folder-based organization (from v1.0 PRD) — deferred, low priority

## Context

**Organization:** Product Labs, IIIT Hyderabad
**Project Type:** ML/AI Product Development — Compliance Automation
**Timeline:** 10-12 weeks for v2.0
**Task Classification:** Task 2 (Compliance Automation), building on Task 1 (Document Management)

**Existing Codebase (v1.0):**
10,286 LOC (6,372 Python + 3,914 TypeScript). Working system with FastAPI backend, Next.js frontend, ML pipeline, full auth, RBAC, analytics, and production deployment. 42/42 v1.0 requirements validated across 8 phases.

**Tech Stack (established):**
- Backend: Python 3.x, FastAPI, SQLAlchemy 2.0, PostgreSQL, Celery + Redis
- Frontend: Next.js 14, React 18, TypeScript, Tailwind CSS
- ML: scikit-learn, Tesseract OCR, pdfplumber, OpenCV
- Infra: Docker, GitHub Actions CI/CD
- Deployed: Vercel (frontend), Render (backend)

**New Tech for v2.0:**
- ML: BERT (notice classification), spaCy NER, XGBoost (risk scoring)
- Search: Elasticsearch (cross-system notice search)
- Scheduling: APScheduler (periodic compliance checks)
- Real-time: WebSocket (live notifications)
- Integrations: GST Portal API, Income Tax API, MCA API, SendGrid, Twilio
- State: Zustand + React Query (frontend state management upgrade)

**Indian Regulatory Landscape:**
- RBI: 200+ circulars, Master Directions, penalties ₹10L-₹25L per violation
- SEBI: LODR, Insider Trading, SCRR regulations, penalties ₹1L-₹25L
- GST: GSTR-1/3B mismatches, ITC discrepancies, late filing ₹200/day
- Income Tax: TDS, scrutiny, assessment, penalties 50-200% of tax
- Legal: Court summons, contract disputes, consumer protection

**Success Metrics:**
- Notice classification accuracy: >92%
- 95% notices responded before deadline
- 80% reduction in manual tracking time
- Compliance health score >85%
- Page load <3s, API response <500ms

## Constraints

- **Timeline**: 10-12 weeks for v2.0 scope
- **Architecture**: Extend existing FastAPI + Next.js + PostgreSQL codebase — no separate app
- **Portal Access**: Government portal APIs may have access restrictions; web scraping as fallback for RBI/SEBI
- **ML Training Data**: Need 5,000+ labeled notices across categories; may need synthetic data augmentation
- **Security**: Financial/legal notices are highly sensitive — encryption, audit trails, RBAC mandatory
- **Existing Stack**: Build on current stack; new additions (Elasticsearch, BERT, WebSocket) must integrate cleanly
- **Deployment**: Continue with Vercel + Render; Docker Compose for local dev
- **Budget**: Infrastructure ~₹1.1L/month (Elasticsearch, SendGrid, Twilio, LLM APIs)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep FastAPI + Next.js stack | Working prototype, good ecosystem | ✓ Good |
| Local filesystem storage for v1 | Simplifies deployment, S3 support exists for later | ✓ Good |
| scikit-learn for doc classification | Meets 85%+ accuracy target, fast training, interpretable | ✓ Good |
| PostgreSQL FTS over Elasticsearch (v1) | Already have PostgreSQL, sufficient for doc search scale | ✓ Good |
| 6 Indian document categories | Matches PRD scope and available datasets | ✓ Good |
| Optional LLM integration (v1) | Adds advanced extraction without being required for core flow | ✓ Good |
| Extend existing app for v2 (not separate) | Client wants integration; shared auth, DB, UI eliminates bridge overhead | — Pending |
| BERT for notice classification (v2) | Higher accuracy needed for legal/compliance (>92% target) | — Pending |
| Elasticsearch for v2 search | Cross-system search across documents + notices at scale | — Pending |
| Real government portal integration | Client requirement; GST/IT APIs available, RBI/SEBI via scraping | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30 after v2.0 milestone initialization*
