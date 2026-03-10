# Roadmap: Smart Document Management System

## Overview

This roadmap transforms the existing working prototype (FastAPI + Next.js + ML pipeline) into a production-ready AI-powered document management system. The 8 phases follow a natural dependency chain: secure the foundation first, then improve the core document processing and ML pipeline, upgrade search, add LLM-powered extraction, implement multi-user access control, polish the UI with analytics, and finalize production readiness. Every phase delivers a coherent, verifiable capability that builds on previous phases.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Security Hardening** - Eliminate critical security vulnerabilities and establish migration framework before adding features
- [x] **Phase 2: Document Processing Pipeline** - Wire async processing, add format support, and improve OCR for reliable document ingestion
- [x] **Phase 3: ML Classification Upgrade** - Train classifier on real datasets and establish model evaluation metrics (completed 2026-03-10)
- [ ] **Phase 4: Search & Retrieval** - Replace ILIKE with PostgreSQL full-text search, filters, and fuzzy matching
- [ ] **Phase 5: Smart Extraction (AI)** - Add LLM-powered metadata extraction, summaries, and configurable AI providers
- [ ] **Phase 6: Access Control & SSO** - Implement role-based access, document-level permissions, and OAuth login
- [ ] **Phase 7: UI & Analytics** - Build analytics dashboard, document preview, version control, and responsive design
- [ ] **Phase 8: Production Readiness** - Add audit logging, CI/CD pipeline, and production deployment documentation

## Phase Details

### Phase 1: Foundation & Security Hardening
**Goal**: The application runs on a secure, properly configured foundation with no hardcoded secrets, proper token management, and structured observability
**Depends on**: Nothing (first phase)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, INFR-01
**Success Criteria** (what must be TRUE):
  1. Application starts with no hardcoded secrets -- all sensitive values come from environment variables, and the app refuses to start if critical env vars are missing
  2. User sessions expire after 30 minutes of inactivity and can be silently refreshed without re-login via refresh tokens
  3. Repeated failed login attempts or rapid-fire upload requests are rate-limited and return 429 responses
  4. All HTTP responses include security headers (HSTS, CSP, X-Frame-Options) verifiable via browser dev tools
  5. Application logs are structured JSON (not print statements) and include request IDs for tracing
**Plans**: 4 plans in 3 waves

Plans:
- [x] 01-01-PLAN.md -- Replace hardcoded secrets and implement environment-based configuration (Wave 1)
- [x] 01-02-PLAN.md -- Implement JWT refresh token mechanism with 30-minute access token expiry (Wave 2)
- [x] 01-03-PLAN.md -- Add rate limiting, security headers, and structured logging (Wave 2, parallel with 01-02)
- [x] 01-04-PLAN.md -- Set up Alembic migration framework with initial migration from current schema (Wave 3)

### Phase 2: Document Processing Pipeline
**Goal**: Users can upload documents in all supported formats and processing happens asynchronously with visible progress
**Depends on**: Phase 1 (migrations framework, structured logging)
**Requirements**: PROC-01, PROC-02, PROC-03, PROC-04, PROC-05, PROC-06, PROC-07, INFR-05
**Success Criteria** (what must be TRUE):
  1. User can drag-and-drop PDF, JPG, PNG, and DOCX files and all are processed correctly
  2. User can upload multiple documents at once and each shows individual processing status
  3. Upload returns immediately (non-blocking) and processing status updates are visible in the UI
  4. Scanned documents with skew, noise, or poor contrast still have readable extracted text
  5. Uploaded documents have automatically extracted metadata (date, amount, vendor) visible on the document detail page
**Plans**: 4 plans in 3 waves

Plans:
- [x] 02-01: Add DOCX support and image preprocessing pipeline (deskew, threshold, noise removal)
- [x] 02-02: Wire Celery async processing with Redis and configure Docker Compose workers
- [x] 02-03: Implement bulk upload, progress indicators, and processing status tracking
- [x] 02-04: Build automatic metadata extraction (date, amount, vendor) from document text

### Phase 3: ML Classification Upgrade
**Goal**: Document classification achieves greater than 85% accuracy on real-world documents with transparent model performance metrics
**Depends on**: Phase 2 (improved text extraction feeds better data to classifier)
**Requirements**: AIML-01, AIML-02, AIML-03, AIML-04
**Success Criteria** (what must be TRUE):
  1. Classifier achieves greater than 85% accuracy on a held-out test set of real documents (not synthetic data)
  2. Each classified document shows a color-coded confidence badge (green above 80%, yellow 50-80%, red below 50%)
  3. Model evaluation report with confusion matrix and per-category precision/recall/F1 is generated and accessible
  4. Classification works reliably across all 6 document categories with real Indian financial documents
**Plans**: 2 plans in 2 waves

Plans:
- [x] 03-01-PLAN.md -- Enhance training pipeline with SVM, tune hyperparameters, and retrain on larger dataset (Wave 1)
- [x] 03-02-PLAN.md -- Add evaluation API endpoint, color-coded confidence badges, and model evaluation page (Wave 2)

### Phase 4: Search & Retrieval
**Goal**: Users can find any document in under 2 seconds using full-text search with filters and fuzzy matching
**Depends on**: Phase 1 (migrations for schema changes), Phase 2 (documents have extracted text)
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SRCH-04
**Success Criteria** (what must be TRUE):
  1. User can search across all document content and results are ranked by relevance (not just substring match)
  2. User can filter search results by category, date range, and amount range -- filters combine with text search
  3. Searching for "electrcity" (typo) still returns electricity bill documents
  4. Search results return in under 2 seconds even with thousands of documents in the database
**Plans**: TBD

Plans:
- [ ] 04-01: Implement PostgreSQL FTS with tsvector columns, GIN indexes, and relevance ranking
- [ ] 04-02: Add category, date range, and amount filters to search API and frontend
- [ ] 04-03: Implement fuzzy matching with pg_trgm and verify sub-2-second response times

### Phase 5: Smart Extraction (AI)
**Goal**: Documents are automatically enriched with LLM-extracted structured data, summaries, and confidence-scored fields
**Depends on**: Phase 1 (structured logging for API audit trail), Phase 2 (async processing for LLM calls), Phase 4 (extracted data becomes searchable)
**Requirements**: EXTR-01, EXTR-02, EXTR-03, EXTR-04, EXTR-05
**Success Criteria** (what must be TRUE):
  1. After upload, documents have structured extracted fields (dates, amounts, parties, key terms) displayed on the detail page
  2. User can choose which LLM provider to use (OpenAI, Anthropic, or local-only) from a settings page
  3. Each document has an AI-generated one-paragraph summary visible on the document detail view
  4. Each extracted field shows a confidence score so users know which extractions to trust vs. verify
  5. Extraction works asynchronously -- users are not blocked waiting for LLM responses
**Plans**: TBD

Plans:
- [ ] 05-01: Build LLM extraction service with provider abstraction (OpenAI, Anthropic, local fallback)
- [ ] 05-02: Implement document-type-specific extraction prompts and structured JSON output
- [ ] 05-03: Add AI summarization, confidence scoring, and extraction results UI
- [ ] 05-04: Build provider configuration settings page and integrate with async pipeline

### Phase 6: Access Control & SSO
**Goal**: Multiple users can share a system with role-based permissions, document-level sharing, and enterprise login options
**Depends on**: Phase 1 (migrations, security foundation), Phase 2 (document ownership model)
**Requirements**: RBAC-01, RBAC-02, RBAC-03, RBAC-04, RBAC-05, RBAC-06
**Success Criteria** (what must be TRUE):
  1. Admin user can create accounts, assign roles (admin/editor/viewer), and manage users from an admin panel
  2. Editor can upload, edit metadata, and delete their own documents but cannot access other users' documents unless shared
  3. Viewer can only see documents explicitly shared with them and cannot upload or modify anything
  4. User can share a specific document with a specific user and set their permission level (view or edit)
  5. User can log in via Google or Microsoft account as an alternative to email/password
**Plans**: TBD

Plans:
- [ ] 06-01: Implement role model (admin, editor, viewer) with database schema and permission checks
- [ ] 06-02: Build admin panel for user management and role assignment
- [ ] 06-03: Implement document-level permissions and sharing
- [ ] 06-04: Integrate Google and Microsoft OAuth/SSO login

### Phase 7: UI & Analytics
**Goal**: Users have a polished interface with analytics, in-browser document preview, version tracking, and responsive design
**Depends on**: Phase 4 (search results to preview from), Phase 5 (extracted data and summaries to display), Phase 6 (user activity data for analytics)
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, SRCH-05
**Success Criteria** (what must be TRUE):
  1. Dashboard shows document counts by category, monthly upload trends chart, and usage statistics at a glance
  2. User can click on any document and preview it in-browser (PDF viewer for PDFs, image viewer for images) without downloading
  3. User can view revision history for a document and rollback to a previous version
  4. Document detail page shows extracted metadata, AI summary, classification info, and confidence scores in a unified view
  5. All pages are usable on both desktop monitors and tablet-sized screens without horizontal scrolling
**Plans**: TBD

Plans:
- [ ] 07-01: Build analytics dashboard with category breakdown, upload trends, and usage statistics
- [ ] 07-02: Implement in-browser document preview (PDF.js for PDFs, native for images)
- [ ] 07-03: Add document version control with revision history and rollback
- [ ] 07-04: Build unified document detail page and ensure responsive design across all pages

### Phase 8: Production Readiness
**Goal**: The system is auditable, continuously tested, and documented for production deployment
**Depends on**: Phase 6 (audit logging needs RBAC context), Phase 7 (all features complete before deployment docs)
**Requirements**: INFR-02, INFR-03, INFR-04
**Success Criteria** (what must be TRUE):
  1. Every document access, upload, modification, and deletion is recorded in an audit log with who, what, and when
  2. Pushing to main triggers automated tests and deployment via GitHub Actions pipeline
  3. A new developer can follow the deployment documentation to stand up the full system (Docker + cloud) without asking questions
**Plans**: TBD

Plans:
- [ ] 08-01: Implement audit logging service with middleware and business event recording
- [ ] 08-02: Set up GitHub Actions CI/CD pipeline with automated testing
- [ ] 08-03: Write production deployment documentation (Docker, AWS/Render setup)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Security Hardening | 4/4 | Complete | 2026-02-25 |
| 2. Document Processing Pipeline | 4/4 | Complete | 2026-03-01 |
| 3. ML Classification Upgrade | 2/2 | Complete   | 2026-03-10 |
| 4. Search & Retrieval | 0/3 | Not started | - |
| 5. Smart Extraction (AI) | 0/4 | Not started | - |
| 6. Access Control & SSO | 0/4 | Not started | - |
| 7. UI & Analytics | 0/4 | Not started | - |
| 8. Production Readiness | 0/3 | Not started | - |

---
*Roadmap created: 2026-02-17*
*Last updated: 2026-03-10*
