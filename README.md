# SmartDocs

**AI-powered document management system** built for IIIT Hyderabad Production Labs. Upload any document — PDFs, scanned images, DOCX — and the system automatically extracts text via OCR, classifies it using machine learning, and makes it searchable.

---

## Features

- **ML Document Classification** — Automatically categorizes documents into bills, invoices, tax forms, bank statements, UPI receipts, and tickets using a trained Linear SVC model (85.06% accuracy — exceeds 85% target)
- **OCR Text Extraction** — Extracts text from scanned PDFs and images using Tesseract with adaptive preprocessing (grayscale, blur, thresholding, deskew, morphological ops, multi-PSM retry)
- **Async Processing** — Upload returns immediately (HTTP 202). Celery workers handle OCR + classification in the background with real-time status polling
- **Full-Text Search** — Search across all extracted document content with category filtering
- **Secure Auth** — JWT access tokens + opaque refresh tokens with rotation and reuse detection. bcrypt password hashing. Rate limiting on all endpoints
- **Multi-Format Support** — PDF (text + scanned), PNG, JPG, TIFF, DOCX

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              Next.js Frontend                │
│     Landing · Auth · Dashboard · Search      │
└──────────────────┬───────────────────────────┘
                   │ REST API
┌──────────────────┴───────────────────────────┐
│              FastAPI Backend                  │
│   Auth · Documents API · ML Pipeline         │
├────────────┬────────────┬────────────────────┤
│ PostgreSQL │   Redis    │   Celery Workers   │
│ (Data)     │  (Broker)  │ (OCR + Classify)   │
└────────────┴────────────┴────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy, Pydantic v2, Uvicorn |
| Database | PostgreSQL 14, Alembic migrations |
| ML | scikit-learn (LinearSVC + CalibratedClassifierCV + TF-IDF), Tesseract OCR, pdfplumber, python-docx |
| Async | Celery + Redis |
| Auth | JWT (HS256) + opaque refresh tokens, bcrypt, slowapi rate limiting |
| Infra | Docker, Docker Compose (5 services) |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose

### 1. Clone and configure

```bash
git clone https://github.com/10srav/SMART-DOCUMENT-MANAGEMENT-SYSTEM--IIITHYD-PROD-LABS.git
cd "SMART DOCUMENT MANAGEMENT SYSTEM- IIITHYD PROD LABS"
cp backend/.env.example backend/.env
# Edit backend/.env — set SECRET_KEY (>= 32 chars) and database credentials
```

### 2. Start all services

```bash
docker compose up --build
```

This launches 5 containers:

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Next.js UI |
| Backend | http://localhost:8000 | FastAPI REST API |
| Swagger | http://localhost:8000/docs | Interactive API docs (debug mode) |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Celery message broker |

### 3. Get the trained model (automatic)

The trained model (`document_classifier.pkl` + `tfidf_vectorizer.pkl`) is committed to git — you get it automatically on `git clone` / `git pull`. No training step needed.

### 4. Download datasets (optional — only if you want to retrain)

Datasets are 28 GB and not in git. To download them into `backend/datasets/`:

```bash
# Add to .env:  KAGGLE_USERNAME=xxx  KAGGLE_KEY=xxx
docker compose run backend python -m app.ml.datasets.download
docker compose run backend python -m app.ml.datasets.prepare
```

Once downloaded they are bind-mounted into the container at `/app/datasets` automatically.

To retrain from scratch after downloading:
```bash
# Synthetic data only (no external deps):
docker compose exec backend python -m app.ml.train --synthetic-only

# Real Kaggle datasets:
docker compose exec backend python -m app.ml.train --full-pipeline

# Combined (real + synthetic augmentation — what achieved 85%):
docker compose exec backend python -m app.ml.train --combined
```

### 4. Local development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head
python -m app.ml.train --synthetic-only
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get access + refresh token pair |
| POST | `/api/auth/refresh` | Rotate refresh token |
| POST | `/api/auth/logout` | Revoke refresh token |

### Documents (all require `Authorization: Bearer <token>`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/upload` | Upload file (returns 202, async processing) |
| GET | `/api/documents/{id}/status` | Poll processing status |
| GET | `/api/documents/all` | List all documents (paginated) |
| GET | `/api/documents/{id}` | Get document detail |
| GET | `/api/documents/search?q=…` | Full-text search with optional `category` filter |
| GET | `/api/documents/category/{cat}` | Filter by category |
| GET | `/api/documents/stats` | Dashboard statistics |
| DELETE | `/api/documents/{id}` | Delete document + file |

### ML (requires `Authorization: Bearer <token>`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ml/evaluation` | Model metrics — accuracy, per-category P/R/F1, confusion matrix |

---

## Document Categories

| Category | Examples | Training Data |
|----------|----------|---------------|
| Bills | Utility bills, phone bills | Financial images (India) |
| UPI | UPI transaction receipts | UPI Transactions 2024 (250K records) |
| Tickets | Event/travel tickets | Synthetic |
| Tax | ITR forms, tax documents | ITR Form 16 images |
| Bank | Bank statements, passbooks | Bank statements CSV + images |
| Invoices | Purchase invoices, receipts | Invoice OCR (8K images), RVL-CDIP |

---

## Processing Pipeline

```
Upload (HTTP 202)
  │
  ▼
Celery Worker picks up task
  │
  ├─ PDF? ──► pdfplumber text extraction
  │            └─ fallback to OCR if < 50 chars
  ├─ DOCX? ─► python-docx (paragraphs + tables)
  ├─ Image? ► Tesseract OCR
  │            ├─ Grayscale → Gaussian blur → Adaptive threshold
  │            ├─ Deskew correction
  │            ├─ Morphological open/close
  │            └─ Multi-PSM retry (PSM 6 → PSM 3)
  │
  ▼
Text Preprocessing (clean, normalize, preserve financial patterns)
  │
  ▼
TF-IDF + Linear SVC Classification
  │
  ▼
Metadata Extraction (dates, amounts, vendor — regex + dateutil)
  │
  ▼
Status: COMPLETED (category + confidence score + metadata)
```

---

## Project Structure

```
backend/
  app/
    main.py                  # FastAPI app, middleware, routes
    config.py                # Pydantic settings from .env
    database.py              # SQLAlchemy engine + session
    models/                  # User, Document, RefreshToken
    schemas/                 # Request/response Pydantic models
    routers/                 # auth.py, documents.py
    services/                # storage_service.py (local/S3)
    middleware/               # Security headers, request logging
    ml/
      ocr.py                 # Image preprocessing + Tesseract
      pdf_extractor.py       # pdfplumber + OCR fallback
      docx_extractor.py      # python-docx extraction
      text_preprocessor.py   # Text cleaning for ML
      classifier.py          # Classification orchestrator
      metadata_extractor.py  # Date/amount/vendor regex extraction
      train.py               # Model training pipeline
      datasets/              # Kaggle download + data preparation
    tasks/                   # Celery task definitions
    utils/                   # JWT, rate limiter, logging
  alembic/                   # Database migrations
  Dockerfile
  requirements.txt

frontend/
  src/
    app/
      page.tsx               # Landing page
      login/                 # Sign in
      register/              # Sign up
      dashboard/
        page.tsx             # Overview (stats, categories, recent)
        upload/              # Drag-drop upload with progress
        documents/           # Document list with category filters
        search/              # Full-text search
        analytics/           # Category distribution, processing status
    context/                 # Auth context (token management)
    lib/                     # Axios API client with refresh interceptor
  Dockerfile

docker-compose.yml           # PostgreSQL, Redis, Backend, Celery, Frontend
```

---

## Development Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation & Security Hardening | ✅ Done |
| 2 | Document Processing Pipeline | ✅ Done |
| 3 | ML Classification Upgrade | ✅ Done (85.06% accuracy) |
| 4 | Search & Retrieval Engine | ✅ Done (FTS + fuzzy + filters) |
| 5 | LLM Smart Extraction | Next |
| 6 | Multi-User & RBAC | Planned |
| 7 | Analytics Dashboard | Planned |
| 8 | Production Deployment | Planned |

### Completed

**Phase 1** — JWT refresh token rotation with reuse detection, bcrypt auth, rate limiting (slowapi), security headers (HSTS, CSP, X-Frame-Options), structured JSON logging with correlation IDs, Alembic migration framework.

**Phase 2** — Multi-format text extraction (PDF, DOCX, images), OCR with adaptive preprocessing, async Celery processing (202 Accepted + status polling), frontend bulk upload with per-file progress, metadata extraction (dates, amounts, vendor).

**Phase 3** — Upgraded classifier from Logistic Regression (76.4%) to Linear SVC (85.06%, exceeds >85% target). 7 Kaggle datasets (28 GB), TF-IDF 15K vocab + trigrams, class-balanced training with synthetic augmentation (factor=10). ML evaluation API + model evaluation dashboard page with confusion matrix and per-category P/R/F1 badges. Trained model committed to git; datasets bind-mounted in Docker for team access.

**Phase 4** — PostgreSQL full-text search replacing ILIKE: stored tsvector column with GIN index, ts_rank relevance ordering, `pg_trgm` trigram fuzzy matching (OR-combine: FTS for stems + trigram for typos). Category, date range, and amount filters with JSONB NULL guards. Frontend filter UI. Rate-limited search endpoint (30/min). Opus code review applied 6 fixes (pattern injection, date validation, amount cast safety, trigger optimization).

**UI Redesign** — Minimalist dark theme (Linear/Notion-inspired), Inter font, zinc/neutral palette, no glassmorphism. Clean dashboard with stats, category filters, full-text search, analytics.

---

## Environment Variables

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smart_docs
SECRET_KEY=your-secret-key-minimum-32-characters
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=50
USE_S3=false
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
ML_CONFIDENCE_THRESHOLD=0.3
DEBUG=true
```

See `backend/.env.example` for the full list.

---

## Team

**Sravan** (10srav) — Development Lead
**Jyothika** — CORE MEMBER

Built for **Product Labs, IIIT Hyderabad**.
