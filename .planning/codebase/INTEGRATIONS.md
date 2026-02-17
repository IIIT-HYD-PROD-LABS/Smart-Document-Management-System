# External Integrations

**Analysis Date:** 2026-02-17

## APIs & External Services

**AWS S3 (Optional):**
- Cloud file storage for document uploads
  - SDK/Client: boto3 1.33.6
  - Auth: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` env vars
  - Config: `app/config.py` (lines 34-39)
  - Implementation: `app/services/storage_service.py` (upload_to_s3, get_presigned_url)
  - Enabled via: `USE_S3=true` in `.env`
  - Region: `AWS_REGION` (default: ap-south-1)
  - Bucket: `S3_BUCKET_NAME` (default: smart-docs-bucket)

**OCR Service (Tesseract):**
- Local/System OCR for text extraction from scanned documents
  - Binary: Tesseract OCR (system dependency)
  - Configuration: `TESSERACT_CMD` env var (optional, default system path)
  - Implementation: `app/ml/ocr.py`
  - Used for image preprocessing and text extraction

## Data Storage

**Databases:**
- PostgreSQL 14+
  - Connection: `DATABASE_URL` env var
  - Default: postgresql://postgres:postgres@localhost:5432/smart_docs
  - Client: SQLAlchemy 2.0.23 ORM
  - Engine config: `app/database.py` (pool_size=10, max_overflow=20)
  - Models: `app/models/user.py`, `app/models/document.py`
  - Schema: Auto-created via SQLAlchemy metadata

**File Storage:**
- Local filesystem (default): `UPLOAD_DIR` setting in config
  - Default location: `./backend/uploads`
  - File naming: UUID-based with original extension
  - Max file size: 50MB (configurable via `MAX_FILE_SIZE_MB`)
  - Allowed formats: pdf, png, jpg, jpeg, tiff, bmp
- AWS S3 (optional): Enable with `USE_S3=true`
  - Presigned URLs generated for 1-hour expiration by default
  - Bucket key pattern: `documents/{filename}`

**ML Models:**
- Local directory storage
  - Location: `./backend/models` (configurable via `MODEL_DIR`)
  - TF-IDF Vectorizer: `tfidf_vectorizer.pkl`
  - Classifier Model: `document_classifier.pkl`
  - Format: joblib-serialized model files
  - Loaded lazily in `app/ml/classifier.py` (lines 19-29)

**Caching:**
- Redis 7+
  - Connection: `REDIS_URL` env var
  - Default: redis://localhost:6379/0
  - Used for: Celery message broker and result backend
  - Config keys: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`

## Authentication & Identity

**Auth Provider:**
- Custom JWT-based authentication (no external provider)
  - Implementation: `app/utils/security.py`
  - Token type: JWT with HS256 algorithm
  - Signing key: `SECRET_KEY` env var
  - Expiration: `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 1440 = 24 hours)

**Endpoints:**
- Register: `POST /api/auth/register` - `app/routers/auth.py`
- Login: `POST /api/auth/login` - `app/routers/auth.py`
- Get current user: Dependency injection via `get_current_user()` in `app/utils/security.py` (lines 57-80)

**Password Security:**
- Hashing: bcrypt via passlib
- Verification: passlib.context.CryptContext with bcrypt schemes
- Functions: `hash_password()`, `verify_password()` in `app/utils/security.py`

**Frontend Token Management:**
- Storage: HTTP-only cookies (via js-cookie)
- Cookie name: `token`
- Cookie duration: 7 days
- Interception: Axios interceptors in `frontend/src/lib/api.ts` (lines 13-34)
- Auto-logout on 401 responses

## Monitoring & Observability

**Error Tracking:**
- Not detected - No external error tracking service configured
- Errors logged to console or application logs

**Logs:**
- Python logging via print statements and exception handling
- Backend: Uvicorn and FastAPI default logging
- Celery: Configured with `--loglevel=info` in docker-compose.yml
- Frontend: Browser console logs only

## CI/CD & Deployment

**Hosting:**
- Docker containers locally or on server
- Services: PostgreSQL, Redis, FastAPI backend, Celery worker, Next.js frontend
- Orchestration: Docker Compose (docker-compose.yml)

**CI Pipeline:**
- Not detected - No GitHub Actions, GitLab CI, or Jenkins configuration

**Deployment:**
- Docker Compose stack with 5 services:
  1. PostgreSQL database (postgres:14-alpine)
  2. Redis broker (redis:7-alpine)
  3. FastAPI backend (custom image from ./backend/Dockerfile)
  4. Celery worker (custom image from ./backend/Dockerfile)
  5. Next.js frontend (custom image from ./frontend/Dockerfile)
- Health checks configured for postgres and redis
- Volume mounts for persistence: postgres_data, backend_uploads, backend_models

## Environment Configuration

**Required env vars:**
- Database: `DATABASE_URL`
- Authentication: `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- File Storage: `UPLOAD_DIR`, `MAX_FILE_SIZE_MB`
- Redis/Celery: `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- ML: `MODEL_DIR`, `ML_CONFIDENCE_THRESHOLD`
- OCR: `TESSERACT_CMD` (optional)
- AWS (optional): `USE_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME`
- Frontend: `NEXT_PUBLIC_API_URL`

**Secrets location:**
- Backend: `.env` file (not committed, see `.env.example`)
- Docker Compose: environment variables in `docker-compose.yml` (hardcoded for local dev)
- Production: Should use secrets management or environment variables from container orchestration

**Example .env file:**
- Location: `backend/.env` (copy from `backend/.env.example`)
- Format: KEY=VALUE pairs
- Loaded via: python-dotenv in `app/config.py` (line 8)

## Webhooks & Callbacks

**Incoming:**
- Not detected - No webhook endpoints for external services

**Outgoing:**
- Not detected - No outgoing webhooks to third-party services

## Data Processing Pipeline

**Document Upload Flow:**
1. Frontend: File uploaded via `POST /api/documents/upload`
2. Backend validates: file type, file size
3. Storage: Saves to local filesystem or S3 via `app/services/storage_service.py`
4. Processing: Synchronous extraction and classification in `app/routers/documents.py` (lines 69-81) OR async via Celery task `app/tasks/document_tasks.py`
5. ML Pipeline:
   - Text extraction: `app/ml/pdf_extractor.py` (PDF) or `app/ml/ocr.py` (images)
   - Image preprocessing: Grayscale, denoise, threshold, deskew via OpenCV
   - PDF processing: pdfplumber for text-based, OCR fallback for scanned
   - Text cleanup: `app/ml/text_preprocessor.py`
   - Classification: TF-IDF vectorization + scikit-learn model in `app/ml/classifier.py`
6. Database: Document record stored with extracted_text, category, confidence_score, status

**Supported Document Types:**
- PDF files: Text-based and scanned (OCR)
- Images: PNG, JPG, JPEG, TIFF, BMP with OCR

**ML Classification:**
- 6 document categories: bills, upi, tickets, tax, bank, invoices
- Default: "unknown" for low-confidence or unrecognized documents
- Confidence threshold: `ML_CONFIDENCE_THRESHOLD` env var (default: 0.3)

## Search & Retrieval

**Full-Text Search:**
- Implementation: `app/routers/documents.py` (lines 94-100+)
- Query parameter: `q` (search query, 1-500 chars)
- Filters: Optional category filter
- Pagination: page, per_page parameters
- Database: SQLAlchemy ORM with full-text query operators

**Frontend API Calls:**
- Search: `POST /api/documents/search` (documentsApi.search in `frontend/src/lib/api.ts`)
- Get all: `GET /api/documents/all?skip={skip}&limit={limit}`
- Get by category: `GET /api/documents/category/{category}`
- Get detail: `GET /api/documents/{id}`
- Stats: `GET /api/documents/stats`

---

*Integration audit: 2026-02-17*
