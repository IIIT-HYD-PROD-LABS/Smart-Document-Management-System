# Smart Document Management System

> AI-powered document management system with intelligent ML classification, OCR text extraction, async processing, and real dataset training. Built for IIIT Hyderabad Production Labs.

## Architecture

```
+----------------------------------------------+
|              Next.js Frontend                |
|   (Dashboard, Upload, Search, Analytics)     |
+----------------------------------------------+
|              FastAPI Backend                 |
|   (Auth, Documents API, ML Pipeline)         |
+----------+----------+-----------------------+
| PostgreSQL|  Redis   |  Celery Workers       |
| (Database)| (Broker) |  (Async Processing)   |
+----------+----------+-----------------------+
|              ML Pipeline                     |
|  (OCR -> Text Extraction -> Classification)  |
+----------------------------------------------+
```

## Tech Stack

| Layer      | Technology                                     |
|------------|------------------------------------------------|
| Frontend   | Next.js 14, TypeScript, Tailwind CSS, Framer Motion |
| Backend    | FastAPI, SQLAlchemy, Pydantic, Uvicorn         |
| Database   | PostgreSQL 14, Alembic migrations              |
| ML/NLP     | scikit-learn, Tesseract OCR, pdfplumber, python-docx |
| Async      | Celery + Redis (non-blocking document processing) |
| Auth       | JWT access + opaque refresh tokens, bcrypt     |
| Storage    | Local filesystem / AWS S3                      |
| DevOps     | Docker, Docker Compose                         |

## Project Status

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation & Security Hardening | COMPLETE | 4/4 |
| 2 | Document Processing Pipeline | COMPLETE | 4/4 |
| 3 | ML Classification Upgrade | Next | 0/3 |
| 4 | Search & Retrieval Engine | Pending | 0/4 |
| 5 | LLM Smart Extraction | Pending | 0/4 |
| 6 | Multi-User & RBAC | Pending | 0/4 |
| 7 | Analytics Dashboard | Pending | 0/3 |
| 8 | Production Deployment | Pending | 0/3 |

**Overall Progress:** 8/29 plans complete (28%)

### Phase 1 - Foundation & Security Hardening (COMPLETE)
- Environment-based configuration (no hardcoded secrets)
- JWT refresh token rotation with reuse detection
- Rate limiting on auth and upload endpoints
- Security headers (HSTS, CSP, X-Frame-Options)
- Structured JSON logging with correlation IDs
- Alembic migration framework

### Phase 2 - Document Processing Pipeline (COMPLETE)
- DOCX text extraction (paragraphs + tables)
- Enhanced OCR with morphological preprocessing and multi-PSM retry
- Async processing via Celery (upload returns 202 Accepted)
- Frontend bulk upload with per-file progress bars
- Processing status polling (2.5s interval)
- Automatic metadata extraction (dates, amounts, vendor)

### Dataset Pipeline (Phase 3 Groundwork)
- 7 Kaggle datasets downloaded (~19 GB)
- Automated download/prepare/train pipeline
- Initial real-data training: 76.4% accuracy (Logistic Regression)
- Target: >85% accuracy in Phase 3

## Project Structure

```
backend/
    app/
        main.py              # FastAPI application
        config.py            # Environment configuration
        database.py          # SQLAlchemy setup
        models/              # DB models (User, Document, RefreshToken)
        schemas/             # Pydantic request/response schemas
        routers/             # API routes (auth, documents)
        services/            # Storage service (local/S3)
        middleware/           # Security headers, request logging
        ml/                  # ML pipeline
            ocr.py           # Image preprocessing + Tesseract OCR
            pdf_extractor.py # PDF text extraction (pdfplumber)
            docx_extractor.py # DOCX text extraction (python-docx)
            text_preprocessor.py # Text cleaning for ML
            classifier.py    # Document classification orchestrator
            metadata_extractor.py # Date/amount/vendor extraction
            train.py         # Model training (synthetic + real data)
            datasets/        # Dataset download & preparation
                download.py  # Kaggle dataset downloader
                prepare.py   # OCR-based data preparation pipeline
        tasks/               # Celery async tasks
        utils/               # JWT, rate limiter, security
    alembic/                 # Database migrations
    Dockerfile
    requirements.txt
frontend/
    src/
        app/                 # Next.js pages
            page.tsx         # Landing page
            login/           # Login page
            register/        # Register page
            dashboard/       # Dashboard (protected)
                page.tsx     # Overview + stats
                upload/      # Drag-drop bulk upload with progress
                documents/   # Document browser
                search/      # Full-text search
                analytics/   # Charts & insights
        context/             # React auth context
        lib/                 # API client (Axios + token refresh)
    Dockerfile
    package.json
docker-compose.yml           # 5-service orchestration
```

## Quick Start

### 1. Clone & Configure

```bash
cd "SMART DOCUMENT MANAGEMENT SYSTEM- IIITHYD PROD LABS"
cp backend/.env.example backend/.env
# Edit backend/.env with your settings (SECRET_KEY must be >= 32 chars)
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

This starts all 5 services:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (disabled in production)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 3. Train ML Model

```bash
# Train with synthetic data (default, no external datasets needed):
docker compose exec backend python -m app.ml.train --synthetic-only

# Train with real Kaggle datasets (requires KAGGLE_USERNAME/KAGGLE_KEY):
docker compose exec backend python -m app.ml.train --full-pipeline

# Train with combined real + synthetic data:
docker compose exec backend python -m app.ml.train --combined
```

### 4. Run Locally (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Train the ML model first
python -m app.ml.train

# Run server
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Document Categories

The ML classifier automatically categorizes documents into:

| Category  | Description                     | Real Data Sources |
|-----------|---------------------------------|-------------------|
| Bills     | Utility bills, phone bills      | Financial images India |
| UPI       | UPI transaction receipts        | UPI Transactions 2024 (250K records) |
| Tickets   | Event/travel tickets            | Synthetic (real dataset pending) |
| Tax       | Tax documents, ITR forms        | ITR Form 16 images |
| Bank      | Bank statements, passbooks      | Bank statements CSV + images |
| Invoices  | Purchase invoices, receipts     | Invoice OCR (8K images), RVL-CDIP |

## API Endpoints

| Method | Endpoint                        | Description              | Auth |
|--------|---------------------------------|--------------------------|------|
| POST   | `/api/auth/register`            | Register new user        | No |
| POST   | `/api/auth/login`               | Login & get token pair   | No |
| POST   | `/api/auth/refresh`             | Refresh access token     | No |
| POST   | `/api/auth/logout`              | Revoke refresh token     | Yes |
| POST   | `/api/documents/upload`         | Upload doc (returns 202) | Yes |
| GET    | `/api/documents/{id}/status`    | Processing status        | Yes |
| GET    | `/api/documents/all`            | List all documents       | Yes |
| GET    | `/api/documents/{id}`           | Get document details     | Yes |
| POST   | `/api/documents/search`         | Full-text search         | Yes |
| GET    | `/api/documents/category/{cat}` | Filter by category       | Yes |
| GET    | `/api/documents/stats`          | Dashboard statistics     | Yes |
| DELETE | `/api/documents/{id}`           | Delete document          | Yes |

## Prerequisites

- **Docker & Docker Compose** (recommended)
- **Python 3.11+** (for local backend)
- **Node.js 18+** (for local frontend)
- **PostgreSQL 14+** (for local DB)
- **Tesseract OCR** (for image text extraction)

## Team

- **Sravan** (10srav) - Development Lead
- **Jyothika** - Team Member
- **Organization**: Product Labs, IIIT Hyderabad

## License

Built for IIIT Hyderabad Production Labs.
