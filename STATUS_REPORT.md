# Smart Document Management System — Status Report

**Organization:** Product Labs, IIIT Hyderabad
**Last Updated:** 2026-03-23
**Overall Progress:** 6 of 8 phases complete (76%)

---

## Executive Summary

The Smart Document Management System (SmartDocs) is an AI-powered document management platform that automatically classifies, extracts, and searches personal and business documents. The system has completed 6 of 8 phases: security hardening, document processing pipeline, ML classification (85.06% accuracy), full-text search, LLM smart extraction, multi-user RBAC with OAuth SSO, and a comprehensive end-to-end security audit with 21 fixes across 17 files.

---

## Phase Completion Status

| Phase | Title | Status | Completed |
|-------|-------|--------|-----------|
| 1 | Foundation & Security Hardening | ✅ Complete | 2026-02-17 |
| 2 | Document Processing Pipeline | ✅ Complete | 2026-03-09 |
| 3 | ML Classification Upgrade | ✅ Complete | 2026-03-10 |
| 4 | Search & Retrieval Engine | ✅ Complete | 2026-03-11 |
| 5 | LLM Smart Extraction | ✅ Complete | 2026-03-15 |
| 6 | Multi-User & RBAC | ✅ Complete | 2026-03-20 |
| — | End-to-End Security Audit | ✅ Complete | 2026-03-23 |
| 7 | Analytics Dashboard | 🔜 Next | — |
| 8 | Production Readiness | ⬜ Planned | — |

---

## Completed Phases — Detail

### Phase 1: Foundation & Security Hardening ✅
**Goal:** Eliminate critical vulnerabilities and establish migration framework.

**What was built:**
- Environment-based config — app refuses to start without `SECRET_KEY`, `DATABASE_URL`
- JWT access tokens (30 min) + opaque refresh tokens with rotation and reuse detection
- Rate limiting (slowapi) on auth + upload endpoints → 429 responses on abuse
- Security headers middleware: HSTS (2yr + preload), CSP, X-Frame-Options, X-Content-Type
- Swagger/ReDoc disabled in production (`DEBUG=False`)
- Structured JSON logging (structlog) with correlation IDs on all requests
- Alembic migration framework with initial migration from existing schema

**Requirements completed:** SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, INFR-01

---

### Phase 2: Document Processing Pipeline ✅
**Goal:** Async document processing with full format support and metadata extraction.

**What was built:**
- DOCX text extraction via python-docx (paragraphs + tables)
- OCR preprocessing pipeline: grayscale → Gaussian blur → adaptive threshold → deskew → morphological ops → multi-PSM retry (PSM 6 → PSM 3 fallback)
- Celery async processing wired to Redis — upload returns HTTP 202 immediately
- Celery task stages: reading (10%) → extracting (30%) → metadata (60%) → saving (80%)
- Exponential backoff retry on task failure (60s × 2^retries)
- Frontend bulk upload with per-file progress indicators + real-time status polling (every 2.5s)
- Automatic metadata extraction: dates (dateutil fuzzy, Indian formats), amounts (0.01–10M range validation), vendor names

**Requirements completed:** PROC-01 through PROC-07, INFR-05

---

### Phase 3: ML Classification Upgrade ✅
**Goal:** Document classification >85% accuracy on real-world documents with transparent metrics.

**What was built:**

**Plan 03-01 — Model Upgrade:**
- Added LinearSVC (with CalibratedClassifierCV for probability output) as third model candidate
- 3-model comparison: Logistic Regression vs Naive Bayes vs Linear SVC
- TF-IDF vocabulary: 5K → 15K features, unigrams → trigrams (1,3) ngrams
- Synthetic augmentation factor raised to 10 for underrepresented categories
- **Result: 85.06% test accuracy** (up from 76.4% baseline), Linear SVC selected as best

**Plan 03-02 — Evaluation Dashboard:**
- ML evaluation API endpoint: `GET /api/ml/evaluation` — serves accuracy, per-category P/R/F1, confusion matrix
- Color-coded confidence badges on all document views (green ≥80%, yellow 50–79%, red <50%)
- Model evaluation dashboard page with confusion matrix (intensity-based red shading for misclassifications)

**Docker & Dataset Access:**
- Trained model `.pkl` files (3.6 MB total) committed to git — team gets them on `git pull`
- `docker-compose.yml` updated: bind mounts for `./backend/models` and `./backend/datasets`
- 28 GB Kaggle datasets accessible to team via `python -m app.ml.datasets.download`

**Requirements completed:** AIML-01, AIML-02, AIML-03, AIML-04

#### Per-Category Accuracy (Test Set, 308 samples)

| Category | Precision | Recall | F1 | Samples |
|----------|-----------|--------|----|---------|
| UPI | 100% | 100% | 100% | 48 |
| Tickets | 100% | 100% | 100% | 33 |
| Tax | 97% | 95% | 96% | 38 |
| Bank | 71% | 89% | 79% | 82 |
| Bills | 97% | 64% | 77% | 45 |
| Invoices | 75% | 69% | 72% | 62 |
| **Overall** | **86%** | **85%** | **85%** | **308** |

---

### Phase 4: Search & Retrieval Engine ✅
**Goal:** Replace ILIKE with PostgreSQL full-text search, add filters, fuzzy matching.

**What was built:**

**Plan 04-01 — Full-Text Search:**
- PostgreSQL `tsvector` column with GIN index on `documents` table
- Trigger-based `search_vector` auto-update (fires only when text actually changes)
- `plainto_tsquery` + `ts_rank` relevance ranking replaces naive ILIKE
- Alembic migration `0003_add_fts_and_trgm`: creates `pg_trgm` extension, TSVECTOR column, 2 GIN indexes, trigger function, backfill

**Plan 04-02 — Advanced Filters:**
- Category filter (exact match on `category` column)
- Date range filter with Pydantic `date` type auto-validation, inclusive end boundary (+1 day)
- Amount range filter with regex guard for non-numeric JSONB values
- ILIKE pattern injection protection (SQL wildcard escaping)
- Frontend 2×2 filter panel (date range + amount range pickers)

**Plan 04-03 — Fuzzy Search + Performance:**
- `pg_trgm` trigram similarity for typo-tolerant matching
- OR-combine pattern: FTS for stems + trigram for typos in single query
- `gin_trgm_ops` index on `extracted_text` for sub-2s response times
- Rate limiting (30/min) on search endpoint

**Opus Code Review & Hardening:**
- 4 critical input validation bugs fixed (ILIKE injection, date parsing crash, boundary bug, amount cast crash)
- Trigger optimization: skip recompute when text unchanged
- Dead code removal (`SearchRequest` schema)

**Requirements completed:** SRCH-01, SRCH-02, SRCH-03, SRCH-04

---

### Phase 5: LLM Smart Extraction ✅
**Goal:** Add LLM-powered intelligent data extraction and summarization.

**What was built:**
- LLM extraction service with provider abstraction (Ollama, Gemini, Anthropic, OpenAI, local regex fallback)
- Category-specific extraction prompts with structured JSON output
- AI summaries and extracted fields stored per document
- LLM configuration integrated into async Celery pipeline
- Document detail page extended with AI extraction display

**Requirements completed:** AIML-05, AIML-06, AIML-07, AIML-08

---

### Phase 6: Multi-User & RBAC ✅
**Goal:** Implement multi-user access with role-based permissions and OAuth SSO.

**What was built:**
- Three-tier role system: admin, editor, viewer with permission enforcement at API level
- Admin panel for user management (list, search, role change, activate/deactivate)
- Document-level sharing with view/edit permissions and revocation
- Google OAuth and Microsoft OAuth/SSO login integration
- OAuth exchange code flow with frontend callback handling
- Alembic migrations for roles, permissions, and OAuth fields

**Requirements completed:** RBAC-01, RBAC-02, RBAC-03, RBAC-04

---

### End-to-End Security Audit ✅ (March 23, 2026)
**Goal:** Comprehensive security review and hardening across the full stack.

**10 parallel investigation agents** audited: secrets exposure, OAuth CSRF, JWT sessions, input validation, CORS/headers, Google sign-in E2E, login/register flow, token refresh, document API authorization, and frontend dashboard pages.

**21 fixes applied across 17 files (252 additions, 69 deletions):**

| Category | Key Fixes |
|----------|-----------|
| OAuth Security | Added CSRF state parameter, email verified check, error param handling |
| Authentication | is_active check on refresh, token revocation on user deactivation, refresh token row lock |
| Rate Limiting | Fixed X-Forwarded-For spoofing bypass (use direct client IP) |
| Security Headers | Fixed CORP for cross-origin API, removed bad CSP from API, added Cache-Control no-store |
| Frontend Security | Added CSP + HSTS + X-XSS-Protection, cookie expiry, logout race guard |
| Input Validation | Username regex, email regex + lowercase, filename sanitization path |
| Auth Flow | React StrictMode double-fire guard, login/register redirect, role guards on pages |
| Error Handling | Normalized error messages (no auth provider disclosure), 429 rate-limit handling |

**Areas confirmed secure:** SQL injection (parameterized ORM), path traversal (realpath + prefix), IDOR (consistent auth checks), XSS (React auto-escaping, no unsafe innerHTML), admin endpoints (require_admin), token type validation.

---

## Next: Phase 7 — Analytics Dashboard

**Goal:** Deliver polished UI with analytics, document preview, and responsive design.

**Planned deliverables:**
- Analytics dashboard with category breakdown, upload trends, and usage statistics
- In-browser document preview (PDF.js for PDFs, native for images)
- Document version control with revision history
- Responsive design across all pages

---

## Repository & Docker

**GitHub:** https://github.com/IIIT-HYD-PROD-LABS/Smart-Document-Management-System

**Docker Setup:**
```bash
git clone <repo>
cd "SMART DOCUMENT MANAGEMENT SYSTEM- IIITHYD PROD LABS"
cp backend/.env.example backend/.env
# Set SECRET_KEY, DATABASE_URL, KAGGLE credentials in .env
docker compose up --build
```

**Services after `docker compose up`:**

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs (debug only) |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

**Trained model** is included in git — no retraining needed on first run.

**To get datasets** (optional, for retraining only):
```bash
# Add KAGGLE_USERNAME + KAGGLE_KEY to .env first
docker compose run backend python -m app.ml.datasets.download
```

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn |
| Database | PostgreSQL (Supabase Cloud), Alembic migrations |
| ML | scikit-learn (LinearSVC + CalibratedClassifierCV + TF-IDF 15K), Tesseract OCR, pdfplumber, python-docx, OpenCV |
| AI/LLM | Multi-provider: Ollama, Gemini, Anthropic, OpenAI, local regex fallback |
| Async | Celery + Redis |
| Auth | JWT HS256 (30min) + opaque refresh tokens with rotation, bcrypt, OAuth (Google/Microsoft), slowapi rate limiting |
| Infra | Docker, Docker Compose (5 services), Supabase Cloud |

---

## Team

**Sravan** — Development Lead
**Jyothika** — Core Member

**Organization:** Product Labs, IIIT Hyderabad
