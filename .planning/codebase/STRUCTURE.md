# Codebase Structure

**Analysis Date:** 2026-02-17

## Directory Layout

```
SMART DOCUMENT MANAGEMENT SYSTEM- IIITHYD PROD LABS/
├── backend/                    # FastAPI application (Python)
│   ├── app/                    # Main application package
│   │   ├── main.py             # FastAPI app entry point, middleware setup
│   │   ├── config.py           # Environment configuration (pydantic)
│   │   ├── database.py         # SQLAlchemy session factory, Base model
│   │   ├── models/             # ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py         # User table definition
│   │   │   └── document.py     # Document table definition with indexes
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   └── document.py     # Document schema definitions
│   │   ├── routers/            # API route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py         # Register, login endpoints
│   │   │   └── documents.py    # Upload, search, filter, detail, delete
│   │   ├── services/           # Business logic abstraction
│   │   │   ├── __init__.py
│   │   │   └── storage_service.py  # File save/delete (local or S3)
│   │   ├── ml/                 # Machine learning pipeline
│   │   │   ├── __init__.py
│   │   │   ├── ocr.py          # Image text extraction (Tesseract + OpenCV)
│   │   │   ├── pdf_extractor.py # PDF text extraction (pdfplumber)
│   │   │   ├── text_preprocessor.py # Text cleaning/normalization
│   │   │   ├── classifier.py   # Model inference (TF-IDF + Logistic Regression)
│   │   │   └── train.py        # Model training script with synthetic data
│   │   ├── tasks/              # Celery async tasks (optional)
│   │   │   ├── __init__.py
│   │   │   └── document_tasks.py # Async document processing
│   │   └── utils/              # Utilities
│   │       ├── __init__.py
│   │       └── security.py     # JWT tokens, password hashing
│   ├── uploads/                # Local file storage (created by config)
│   ├── models/                 # ML model artifacts (created by train.py)
│   ├── Dockerfile              # Container image definition
│   ├── requirements.txt        # Python dependencies
│   └── .env.example            # Configuration template
├── frontend/                   # Next.js application (TypeScript)
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   │   ├── layout.tsx      # Root layout with AuthProvider
│   │   │   ├── page.tsx        # Landing page (public)
│   │   │   ├── login/
│   │   │   │   └── page.tsx    # Login form page
│   │   │   ├── register/
│   │   │   │   └── page.tsx    # Registration form page
│   │   │   └── dashboard/      # Protected routes (requires auth)
│   │   │       ├── layout.tsx  # Dashboard layout with sidebar
│   │   │       ├── page.tsx    # Overview with stats and recent documents
│   │   │       ├── upload/
│   │   │       │   └── page.tsx # Drag-drop file upload interface
│   │   │       ├── documents/
│   │   │       │   └── page.tsx # Document list/browser
│   │   │       ├── search/
│   │   │       │   └── page.tsx # Full-text search interface
│   │   │       └── analytics/
│   │   │           └── page.tsx # Charts and insights dashboard
│   │   ├── context/            # React Context providers
│   │   │   └── AuthContext.tsx # Global auth state (user, token, login, logout)
│   │   └── lib/                # Utilities and API clients
│   │       └── api.ts          # Axios instance with auth interceptors
│   ├── public/                 # Static assets (if any)
│   ├── package.json            # npm dependencies and scripts
│   ├── tsconfig.json           # TypeScript configuration
│   ├── next.config.mjs         # Next.js build configuration
│   ├── tailwind.config.ts      # Tailwind CSS configuration
│   ├── postcss.config.mjs      # PostCSS configuration for CSS processing
│   ├── Dockerfile              # Container image definition
│   └── .env.example            # Configuration template
├── docker-compose.yml          # Multi-container orchestration (backend, frontend, db, redis)
└── README.md                   # Project documentation

```

## Directory Purposes

**backend/app/:**
- Purpose: Main FastAPI application code
- Contains: Routes, models, ML pipeline, utilities
- Key files: `main.py` (app entry), `database.py` (ORM setup), `config.py` (settings)

**backend/app/models/:**
- Purpose: SQLAlchemy ORM table definitions
- Contains: User and Document entities with relationships
- Key files: `user.py`, `document.py` with indexed columns and enums

**backend/app/routers/:**
- Purpose: API endpoint definitions
- Contains: Auth endpoints (register, login), document endpoints (upload, search, delete)
- Key files: `auth.py`, `documents.py`

**backend/app/schemas/:**
- Purpose: Pydantic request/response validation schemas
- Contains: Type definitions for API contracts
- Key files: `document.py` (DocumentResponse, DocumentListResponse, etc.)

**backend/app/services/:**
- Purpose: Business logic and external service integration
- Contains: Storage abstraction for local filesystem or S3
- Key files: `storage_service.py` (save_file, delete_file, upload_to_s3)

**backend/app/ml/:**
- Purpose: Machine learning pipeline components
- Contains: Text extraction, preprocessing, classification
- Key files: `ocr.py`, `pdf_extractor.py`, `classifier.py`, `train.py`

**backend/app/utils/:**
- Purpose: Cross-cutting utility functions
- Contains: Security, hashing, token management
- Key files: `security.py` (JWT, password utilities)

**backend/uploads/:**
- Purpose: Local file storage for uploaded documents
- Contains: Generated by save_file_local() on document upload
- Generated: Yes (not committed to git)

**backend/models/:**
- Purpose: Trained ML model artifacts
- Contains: Pickled sklearn models (document_classifier.pkl, tfidf_vectorizer.pkl)
- Generated: Yes, by `python -m app.ml.train`

**frontend/src/app/:**
- Purpose: Next.js App Router page structure
- Contains: Page components organized by route hierarchy
- Key files: `page.tsx` files for each route, `layout.tsx` for nested layouts

**frontend/src/context/:**
- Purpose: React Context for global state management
- Contains: Authentication state provider
- Key files: `AuthContext.tsx` (user, token, login, logout, isLoading)

**frontend/src/lib/:**
- Purpose: Shared utilities and API client
- Contains: Axios HTTP client with request/response interceptors
- Key files: `api.ts` (authApi, documentsApi with typed endpoints)

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI application initialization, middleware setup, router registration
- `frontend/src/app/layout.tsx`: Root Next.js layout with AuthProvider wrapper
- `frontend/src/app/page.tsx`: Public landing page

**Configuration:**
- `backend/app/config.py`: Pydantic Settings for database URL, JWT secret, file limits, ML thresholds
- `frontend/src/lib/api.ts`: API base URL configuration (NEXT_PUBLIC_API_URL env var)
- `docker-compose.yml`: Service definitions and port mappings

**Core Logic:**
- `backend/app/routers/documents.py`: Upload, search, filter, detail, delete endpoints
- `backend/app/routers/auth.py`: Registration and login logic
- `backend/app/ml/classifier.py`: Document classification inference
- `frontend/src/context/AuthContext.tsx`: Auth state management and token persistence

**Testing:**
- No test files detected in current codebase (test coverage gaps present)

## Naming Conventions

**Files:**
- Python: `snake_case.py` (e.g., `document_tasks.py`, `text_preprocessor.py`)
- TypeScript/React: `camelCase.ts` or `PascalCase.tsx` for components (e.g., `AuthContext.tsx`, `api.ts`)
- Routes: Use directory structure (Next.js convention: `app/dashboard/upload/page.tsx` maps to `/dashboard/upload`)

**Directories:**
- Feature-based grouping: `routers/`, `models/`, `schemas/` (backend); `app/`, `context/`, `lib/` (frontend)
- Single responsibility: Each directory has a clear purpose

**Functions:**
- Backend: `snake_case` (e.g., `extract_and_classify()`, `get_current_user()`)
- Frontend: `camelCase` for regular functions, `PascalCase` for React components (e.g., `DashboardPage`, `AuthProvider`)

**Variables:**
- Backend: `snake_case` (e.g., `user_id`, `extracted_text`)
- Frontend: `camelCase` (e.g., `isDragActive`, `isLoading`)

**Types/Enums:**
- Backend: `PascalCase` with Enum suffix (e.g., `DocumentCategory`, `DocumentStatus`)
- Frontend: `PascalCase` interface/type names (e.g., `User`, `Stats`)

## Where to Add New Code

**New Feature (e.g., document tagging):**
- Backend: Add router in `backend/app/routers/`, add model to `backend/app/models/`, add schema to `backend/app/schemas/`
- Frontend: Add feature pages under `frontend/src/app/dashboard/[feature]/page.tsx`, use context for global state if needed
- Tests: Create test files adjacent to implementation (e.g., `backend/app/routers/test_documents.py`)

**New Component/Module:**
- Frontend React component: Create `.tsx` file in appropriate `app/` subdirectory, export as default export
- Backend service: Create file in `backend/app/services/`, follow dependency injection pattern
- ML enhancement: Add function in appropriate `backend/app/ml/` module (ocr.py, classifier.py, etc.)

**Utilities:**
- Shared helpers: Backend → `backend/app/utils/`, Frontend → `frontend/src/lib/`
- API endpoints: Backend → `backend/app/routers/` (group by feature)
- React hooks: Frontend → Consider adding `frontend/src/hooks/` directory (currently doesn't exist)

**Configuration:**
- Environment variables: Update `backend/app/config.py` (pydantic Settings) and `frontend/.env.example`
- Build settings: `frontend/next.config.mjs` or `backend/Dockerfile`

## Special Directories

**backend/uploads/:**
- Purpose: Local file storage location for uploaded documents
- Generated: Yes (created by `os.makedirs()` in config.py)
- Committed: No (.gitignore should exclude)

**backend/models/:**
- Purpose: ML model artifacts and vectorizers
- Generated: Yes (created by `train.py` via joblib.dump())
- Committed: No (models are large binary files)

**frontend/.next/:**
- Purpose: Next.js build output and cache
- Generated: Yes (created by `npm run build`)
- Committed: No

**frontend/node_modules/:**
- Purpose: npm package dependencies
- Generated: Yes (created by `npm install`)
- Committed: No

---

*Structure analysis: 2026-02-17*
