# Smart Document Management System

## What This Is

An intelligent document management SaaS platform for legal and finance professionals. It automatically extracts key data (dates, amounts, parties, clauses) from contracts, invoices, legal filings, and financial reports — eliminating manual document review. Built for small teams of 5-20 users who need to organize, search, and extract insights from large volumes of documents.

## Core Value

**Accurate, automated extraction of key data points (dates, deadlines, financial amounts, parties, and critical clauses) from legal and financial documents** — so professionals spend time acting on information, not hunting for it.

## Requirements

### Validated

- ✓ User authentication (register, login, logout) with JWT — existing
- ✓ Document upload with file validation (type, size) — existing
- ✓ OCR text extraction from scanned documents (Tesseract) — existing
- ✓ PDF text extraction (pdfplumber) — existing
- ✓ ML-powered document classification (TF-IDF + scikit-learn) — existing
- ✓ Basic document search with ILIKE text matching — existing
- ✓ Local and S3 file storage abstraction — existing
- ✓ User-scoped data isolation (documents filtered by user_id) — existing
- ✓ Next.js frontend with dashboard, upload, and search pages — existing
- ✓ Docker containerization with docker-compose — existing

### Active

- [ ] Smart data extraction (dates, deadlines, amounts, parties, clauses) from legal/financial docs
- [ ] AI-powered document summaries and insights
- [ ] Advanced full-text search with relevance ranking
- [ ] Role-based access control (admin, editor, viewer)
- [ ] Document-level permissions
- [ ] SSO / OAuth integration (Google, Microsoft)
- [ ] Support for all four document types: contracts, invoices, legal filings, financial reports
- [ ] Flexible ML backend (local models + LLM APIs, user-configurable)
- [ ] Polished, production-ready UI for legal/finance professionals
- [ ] Production security hardening

### Out of Scope

- Mobile native apps — web-first, responsive design sufficient for v1
- Multi-tenant SaaS architecture — single-tenant for v1, small team focus
- Real-time collaboration — document management, not co-editing
- Workflow automation (approval chains, routing) — v2 feature
- E-signature integration — separate concern, defer

## Context

**Existing Codebase:**
Working prototype with FastAPI backend, Next.js frontend, and ML pipeline. Core document upload → OCR/extraction → classification flow is functional. The codebase has clean layered architecture but several areas need hardening for production use (see `.planning/codebase/CONCERNS.md`).

**Tech Stack:**
- Backend: Python 3.x, FastAPI 0.104.1, SQLAlchemy 2.0.23, PostgreSQL
- Frontend: Next.js 14.2.5, React 18, TypeScript, Tailwind CSS
- ML: scikit-learn, Tesseract OCR, pdfplumber, OpenCV
- Infra: Docker, Redis/Celery (configured but async processing not fully wired)
- Storage: Local filesystem (primary for v1), S3 support exists

**Target Users:**
Legal and finance professionals dealing with contracts, invoices, regulatory filings, and financial statements. They need fast, accurate data extraction and organized document access for small teams.

**Known Issues:**
- Hardcoded security credentials in config (SECRET_KEY defaults)
- Generic exception handling in ML pipeline leaks error details
- Silent S3 error suppression
- No structured logging
- ILIKE search is basic — needs full-text search for production
- ML classifier trained on synthetic data — needs real-world training data
- Document categories are finance-specific (bills, UPI, tax) — need legal document types

## Constraints

- **Storage**: Local filesystem for v1 — keeps deployment simple for small teams
- **ML Flexibility**: Must support both local models and LLM APIs (user choice) — different users have different privacy/cost requirements
- **Security**: Legal/financial documents are sensitive — encryption at rest, audit logging, and proper access controls are non-negotiable
- **Team Size**: Designed for 5-20 users per deployment — don't over-engineer for enterprise scale yet
- **Existing Stack**: Build on current FastAPI + Next.js + PostgreSQL stack — don't rewrite what works

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep FastAPI + Next.js stack | Working prototype, team familiar with it, good ecosystem | — Pending |
| Local filesystem storage for v1 | Simplifies deployment, S3 support exists for later | — Pending |
| Hybrid ML approach (local + LLM APIs) | Legal/finance users have varying privacy needs; let them choose | — Pending |
| Small team scope (5-20 users) | Focus on doing it well for one scale before expanding | — Pending |
| Legal + finance document focus | Clear domain focus enables better extraction models and UI | — Pending |

---
*Last updated: 2026-02-17 after initialization*
