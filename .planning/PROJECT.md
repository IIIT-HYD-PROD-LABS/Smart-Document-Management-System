# Smart Document Management System

## What This Is

An AI-powered document management system that automatically organizes and manages uploaded documents including bills, invoices, UPI receipts, travel tickets, tax documents, and bank statements. Built for IIIT Hyderabad Product Labs. Leverages ML for document classification, OCR for text extraction, and provides intelligent search and retrieval. Designed to scale from the core 6-category academic scope to an enterprise-ready SaaS platform with AI-powered extraction, advanced search, team collaboration, and production security.

## Core Value

**Automated classification and intelligent organization of personal and business documents** — upload any document and the system automatically identifies its type, extracts key data (dates, amounts, vendors), and makes it instantly searchable.

## Requirements

### Validated

- ✓ User authentication (register, login, logout) with JWT — existing
- ✓ Multi-format document upload (PDF, JPG, PNG) with file validation — existing
- ✓ OCR text extraction from scanned documents (Tesseract) — existing
- ✓ PDF text extraction (pdfplumber) — existing
- ✓ ML-powered document classification with TF-IDF + scikit-learn (6 categories) — existing
- ✓ Confidence score display for classifications — existing
- ✓ Basic document search with ILIKE text matching — existing
- ✓ Local and S3 file storage abstraction — existing
- ✓ User-scoped data isolation (documents filtered by user_id) — existing
- ✓ Next.js frontend with dashboard, upload (drag-and-drop), and search pages — existing
- ✓ Docker containerization with docker-compose — existing
- ✓ 6 document categories: utility bills, UPI transactions, travel tickets, tax documents, bank statements, shopping invoices — existing

### Active

**PRD Core (from original spec):**
- ✓ Automatic metadata extraction (date, amount, vendor) from documents — Phase 2
- [ ] Full-text search with PostgreSQL FTS (replace ILIKE) — Phase 4
- [ ] Filter by category, date range, amount — Phase 4
- [ ] Fuzzy search for partial matches — Phase 4
- [ ] Document preview functionality (PDF/image viewer in browser) — Phase 7
- [ ] Analytics dashboard (documents by category, monthly trends, upload stats) — Phase 7
- ✓ DOCX upload support — Phase 2
- ✓ ML model improvement: train on real datasets (RVL-CDIP, Indian financial docs) — Phase 3 (85.06% Linear SVC)
- ✓ Model evaluation with confusion matrix, precision/recall/F1 — Phase 3
- [ ] Automated folder-based organization — Phase 7
- [ ] Version control for updated documents — Phase 7
- ✓ Image preprocessing for better OCR (deskew, threshold, noise removal) — Phase 2

**Advanced Features (beyond PRD):**
- [ ] Smart data extraction (dates, deadlines, amounts, parties, clauses) via LLM APIs — Phase 5
- [ ] AI-powered document summaries and insights — Phase 5
- [ ] Role-based access control (admin, editor, viewer) — Phase 6
- [ ] Document-level permissions and sharing — Phase 6
- [ ] SSO / OAuth integration (Google, Microsoft) — Phase 6
- [ ] Flexible ML backend (local models + LLM APIs, user-configurable) — Phase 5
- [ ] Polished, production-ready UI — Phase 7
- ✓ Production security hardening (structured logging, rate limiting, encryption) — Phase 1
- [ ] Audit logging for compliance — Phase 8
- ✓ Async document processing via Celery (currently configured but not wired) — Phase 2

### Out of Scope

- Mobile native apps — web-first, responsive design sufficient for v1
- Multi-tenant SaaS architecture — single-tenant for v1
- Real-time collaboration — document management, not co-editing
- Workflow automation (approval chains, routing) — v2 feature
- E-signature integration — separate concern, defer
- Blockchain integration — unnecessary complexity for v1
- Email auto-import — v2 feature
- Multi-language OCR (regional languages) — v2 feature

## Context

**Organization:** Product Labs, IIIT Hyderabad
**Project Type:** ML/AI Product Development
**Timeline:** 8-10 weeks (academic), with ambition to extend to production-ready SaaS

**Existing Codebase:**
Working prototype with FastAPI backend, Next.js frontend, and ML pipeline. Core document upload → OCR/extraction → classification flow is functional. The codebase has clean layered architecture but several areas need hardening for production use (see `.planning/codebase/CONCERNS.md`).

**Tech Stack:**
- Backend: Python 3.x, FastAPI 0.104.1, SQLAlchemy 2.0.23, PostgreSQL
- Frontend: Next.js 14.2.5, React 18, TypeScript, Tailwind CSS
- ML: scikit-learn, Tesseract OCR, pdfplumber, OpenCV
- Infra: Docker, Redis/Celery (configured but async processing not fully wired)
- Storage: Local filesystem (primary), S3 support exists

**Document Categories (6 primary):**
1. Utility Bills (electricity, water, gas, internet)
2. UPI Transactions (PhonePe, GPay, Paytm receipts)
3. Travel Tickets (flight, train, bus tickets, boarding passes)
4. Tax Documents (ITR forms, Form 16, tax receipts)
5. Bank Statements (monthly statements, transaction summaries)
6. Shopping Invoices (e-commerce orders, retail receipts)

**Target Datasets:**
- RVL-CDIP (400K documents, 16 classes) — foundation dataset
- Financial Document Classification (Kaggle) — Indian-specific
- Invoice-OCR Dataset — with text annotations
- UPI Transactions datasets (2023, 2024)
- Synthetic data for tax documents and bank statements

**Success Metrics (from PRD):**
- Classification accuracy: >85%
- Text extraction accuracy: >90%
- Search response time: <2 seconds
- User satisfaction: intuitive UI/UX

**Known Issues:**
- Hardcoded security credentials in config (SECRET_KEY defaults)
- Generic exception handling in ML pipeline leaks error details
- Silent S3 error suppression
- No structured logging
- ILIKE search is basic — needs full-text search for production
- ML classifier trained on synthetic data — needs real-world training data
- Celery/Redis configured but async processing not wired

## Constraints

- **Timeline**: 8-10 week academic timeline for core features; advanced features can extend beyond
- **Storage**: Local filesystem primary — keeps deployment simple
- **ML Flexibility**: Support both local scikit-learn models and optional LLM APIs for advanced extraction
- **Security**: Financial documents are sensitive — proper auth, validation, and error handling required
- **Existing Stack**: Build on current FastAPI + Next.js + PostgreSQL stack — don't rewrite what works
- **Datasets**: Use publicly available datasets (RVL-CDIP, Kaggle) + synthetic data; avoid PII

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep FastAPI + Next.js stack | Working prototype, good ecosystem | — Pending |
| Local filesystem storage for v1 | Simplifies deployment, S3 support exists for later | — Pending |
| scikit-learn for classification | Meets 85%+ accuracy target, fast training, interpretable | — Pending |
| PostgreSQL FTS over Elasticsearch | Already have PostgreSQL, sufficient for this scale | — Pending |
| 6 Indian document categories | Matches PRD scope and available datasets | — Pending |
| Optional LLM integration | Adds advanced extraction without being required for core flow | — Pending |

---
*Last updated: 2026-02-17 after initialization (updated with PRD context)*
