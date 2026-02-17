# Smart Document Management System

> AI-powered document management system with intelligent ML classification, OCR text extraction, and full-text search. Built for IIIT Hyderabad Production Labs.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────┐
│              Next.js Frontend                │
│   (Dashboard, Upload, Search, Analytics)     │
├──────────────────────────────────────────────┤
│              FastAPI Backend                 │
│   (Auth, Documents API, ML Pipeline)         │
├───────────┬──────────┬───────────────────────┤
│ PostgreSQL│  Redis   │  Celery Workers       │
│ (Database)│ (Broker) │  (Async Processing)   │
├───────────┴──────────┴───────────────────────┤
│              ML Pipeline                     │
│  (OCR → Text Extraction → Classification)    │
└──────────────────────────────────────────────┘
```

## 🚀 Tech Stack

| Layer      | Technology                                     |
|------------|------------------------------------------------|
| Frontend   | Next.js 14, TypeScript, Tailwind CSS, Framer Motion |
| Backend    | FastAPI, SQLAlchemy, Pydantic, Uvicorn         |
| Database   | PostgreSQL 14                                  |
| ML/NLP     | scikit-learn, Tesseract OCR, pdfplumber        |
| Async      | Celery + Redis                                 |
| Auth       | JWT (PyJWT) + bcrypt                           |
| Storage    | Local filesystem / AWS S3                      |
| DevOps     | Docker, Docker Compose                         |

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Environment configuration
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models/              # DB models (User, Document)
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API routes (auth, documents)
│   │   ├── services/            # Storage service (local/S3)
│   │   ├── ml/                  # ML pipeline
│   │   │   ├── ocr.py           # Image preprocessing + OCR
│   │   │   ├── pdf_extractor.py # PDF text extraction
│   │   │   ├── text_preprocessor.py # Text cleaning
│   │   │   ├── classifier.py    # Document classification
│   │   │   └── train.py         # Model training script
│   │   ├── tasks/               # Celery async tasks
│   │   └── utils/               # JWT security utilities
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages
│   │   │   ├── page.tsx         # Landing page
│   │   │   ├── login/           # Login page
│   │   │   ├── register/        # Register page
│   │   │   └── dashboard/       # Dashboard (protected)
│   │   │       ├── page.tsx     # Overview + stats
│   │   │       ├── upload/      # Drag-drop upload
│   │   │       ├── documents/   # Document browser
│   │   │       ├── search/      # Full-text search
│   │   │       └── analytics/   # Charts & insights
│   │   ├── context/             # React auth context
│   │   └── lib/                 # API client (Axios)
│   ├── Dockerfile
│   └── package.json
└── docker-compose.yml
```

## ⚡ Quick Start

### 1. Clone & Configure

```bash
cd "SMART DOCUMENT MANAGEMENT SYSTEM- IIITHYD PROD LABS"
cp backend/.env.example backend/.env
# Edit backend/.env with your settings
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

This starts all 5 services:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 3. Run Locally (without Docker)

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

## 🔑 Document Categories

The ML classifier automatically categorizes documents into:

| Category  | Description                     |
|-----------|---------------------------------|
| Bills     | Utility bills, phone bills      |
| UPI       | UPI transaction receipts        |
| Tickets   | Event/travel tickets            |
| Tax       | Tax documents, ITR forms        |
| Bank      | Bank statements, passbooks      |
| Invoices  | Purchase invoices, receipts     |
| Unknown   | Unclassifiable documents        |

## 🔒 API Endpoints

| Method | Endpoint                        | Description              |
|--------|---------------------------------|--------------------------|
| POST   | `/api/auth/register`            | Register new user        |
| POST   | `/api/auth/login`               | Login & get JWT token    |
| POST   | `/api/documents/upload`         | Upload & classify doc    |
| GET    | `/api/documents/all`            | List all documents       |
| GET    | `/api/documents/{id}`           | Get document details     |
| POST   | `/api/documents/search`         | Full-text search         |
| GET    | `/api/documents/category/{cat}` | Filter by category       |
| GET    | `/api/documents/stats`          | Dashboard statistics     |
| DELETE | `/api/documents/{id}`           | Delete document          |

## 📋 Prerequisites

- **Docker & Docker Compose** (recommended)
- **Python 3.11+** (for local backend)
- **Node.js 18+** (for local frontend)
- **PostgreSQL 14+** (for local DB)
- **Tesseract OCR** (for image text extraction)

## 📝 License

Built for IIIT Hyderabad Production Labs.
