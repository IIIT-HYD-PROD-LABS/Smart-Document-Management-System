# Architecture

**Analysis Date:** 2026-02-17

## Pattern Overview

**Overall:** Layered Full-Stack with ML Pipeline Integration

**Key Characteristics:**
- Clean separation between frontend (Next.js), backend (FastAPI), and ML services
- Request-response architecture with authentication middleware
- Document processing pipeline with three stages: extraction → classification → persistence
- User-scoped data isolation (all documents filtered by `user_id`)
- Async processing capability via Celery/Redis (optional, currently synchronous)

## Layers

**Presentation Layer (Frontend):**
- Purpose: Render UI, handle user interactions, manage authentication state
- Location: `frontend/src/app/` (Next.js App Router pages), `frontend/src/context/` (state), `frontend/src/lib/` (API client)
- Contains: Page components, layout files, form submissions, document browsing, search interface
- Depends on: Axios HTTP client, Next.js routing, Framer Motion for animations
- Used by: End users accessing the web application

**API Layer (FastAPI Backend):**
- Purpose: Expose REST endpoints, handle authentication, coordinate document processing
- Location: `backend/app/routers/` (auth.py, documents.py)
- Contains: Route handlers, request validation, response formatting, status codes
- Depends on: SQLAlchemy ORM, JWT token validation, ML classifier, storage service
- Used by: Frontend making HTTP requests, Celery tasks reading document data

**Data Access Layer:**
- Purpose: Manage database connections and ORM operations
- Location: `backend/app/database.py`, `backend/app/models/` (user.py, document.py)
- Contains: Session factory, table definitions with relationships, database indexes
- Depends on: SQLAlchemy, PostgreSQL connection
- Used by: All routers and tasks that query/write data

**ML/NLP Pipeline Layer:**
- Purpose: Extract text and classify documents
- Location: `backend/app/ml/` (ocr.py, pdf_extractor.py, classifier.py, text_preprocessor.py)
- Contains: Text extraction engines, ML model inference, text normalization
- Depends on: Tesseract OCR, pdfplumber, scikit-learn trained models, OpenCV preprocessing
- Used by: Document upload handler and async tasks

**Storage Layer:**
- Purpose: Abstract file persistence (local or S3)
- Location: `backend/app/services/storage_service.py`
- Contains: File save/delete logic, S3 upload, local filesystem management, filename generation
- Depends on: boto3 (AWS), filesystem, configured storage backend
- Used by: Document router on upload and delete operations

**Security Layer:**
- Purpose: JWT token management, password hashing, user authentication
- Location: `backend/app/utils/security.py`
- Contains: Token creation/verification, bcrypt hashing, HTTP Bearer dependency
- Depends on: PyJWT, passlib, SQLAlchemy user model
- Used by: Auth router, protected document endpoints

## Data Flow

**Document Upload & Processing:**

1. User selects file from dropzone (`frontend/src/app/dashboard/upload/page.tsx`)
2. Frontend sends multipart form to `POST /api/documents/upload`
3. Backend handler in `backend/app/routers/documents.py` receives file bytes
4. Validates file type and size using `backend/app/config.py` settings
5. Storage service (`backend/app/services/storage_service.py`) saves file to disk or S3
6. Document record created in DB with `status=PROCESSING`
7. ML pipeline invoked:
   - `extract_and_classify()` dispatches to `ocr.py` or `pdf_extractor.py`
   - Text extraction applies preprocessing (`text_preprocessor.py`)
   - TF-IDF vectorizer transforms text
   - Trained classifier predicts category and confidence
8. Database record updated with extracted text, category, confidence score, status
9. Response sent to frontend with classification result
10. User sees confirmation message with category and confidence

**User Authentication:**

1. User submits credentials on login/register page
2. Frontend calls `authApi.login()` from `frontend/src/lib/api.ts`
3. Backend route in `backend/app/routers/auth.py` validates credentials
4. Password verified with `verify_password()` from `backend/app/utils/security.py`
5. JWT token created via `create_access_token()` (expires in 24 hours)
6. Token and user data returned to frontend
7. Frontend stores in cookies via `js-cookie`
8. Axios interceptor (`frontend/src/lib/api.ts`) attaches token to all requests
9. Protected endpoints validate token via `get_current_user()` dependency

**Document Search:**

1. User enters query on search page (`frontend/src/app/dashboard/search/page.tsx`)
2. Frontend sends `POST /api/documents/search?q=...&category=...`
3. Backend filters documents by user_id and applies text search using `ILIKE` (case-insensitive)
4. Optional category filter applied via enum validation
5. Results paginated (default 20 per page)
6. Results returned with extracted text snippets, categories, confidence scores
7. Frontend renders results with highlighting and sorting

**State Management:**

- Frontend: React Context (`AuthContext.tsx`) holds auth state (user, token, isLoading)
- Backend: SQLAlchemy ORM manages model state; FastAPI dependencies inject database sessions
- Authentication state persists across page refreshes via cookies
- Document lists fetched on-demand (no client-side cache)

## Key Abstractions

**Document Entity:**
- Purpose: Represents a file with metadata and processing results
- Examples: `backend/app/models/document.py`, Pydantic schemas in `backend/app/schemas/document.py`
- Pattern: SQLAlchemy ORM model with relationships to User, indexed columns for search performance

**User Entity:**
- Purpose: Represents an authenticated account with password security
- Examples: `backend/app/models/user.py`
- Pattern: ORM model with cascade delete to documents, unique constraints on email/username

**Authentication Dependency:**
- Purpose: FastAPI security dependency for route protection
- Examples: `get_current_user()` in `backend/app/utils/security.py`
- Pattern: HTTPBearer scheme with JWT token validation and user lookup

**Document Category Enum:**
- Purpose: Type-safe classification categories
- Examples: `DocumentCategory` in `backend/app/models/document.py` (bills, upi, tickets, tax, bank, invoices, unknown)
- Pattern: Python Enum backing SQLAlchemy column with ILIKE filtering

**ML Classifier Module:**
- Purpose: Encapsulate trained model inference with lazy loading
- Examples: `backend/app/ml/classifier.py`
- Pattern: Singleton pattern via global variables; vectorizer + model loaded once on first use

## Entry Points

**Frontend Entry Point:**
- Location: `frontend/src/app/layout.tsx` (root layout), wrapped with `AuthProvider` context
- Triggers: User navigates to any URL in the application
- Responsibilities: Auth state initialization, cookie restoration, layout structure

**Backend Entry Point:**
- Location: `backend/app/main.py`
- Triggers: Application startup (uvicorn server)
- Responsibilities: FastAPI initialization, CORS middleware setup, router registration, static file mounting

**Document Upload Endpoint:**
- Location: `backend/app/routers/documents.py:upload_document()`
- Triggers: User submits file via form
- Responsibilities: Validate auth, validate file, save file, extract+classify, persist record

**Search Endpoint:**
- Location: `backend/app/routers/documents.py:search_documents()`
- Triggers: User submits search query with optional category filter
- Responsibilities: Validate auth, build query, apply filters, paginate, return results

**Auth Register Endpoint:**
- Location: `backend/app/routers/auth.py:register()`
- Triggers: User submits registration form
- Responsibilities: Validate input, check uniqueness, hash password, create user, issue token

**ML Training Entry Point:**
- Location: `backend/app/ml/train.py:train_model()`
- Triggers: Manual execution via `python -m app.ml.train`
- Responsibilities: Generate synthetic data, train classifier, save model artifacts

## Error Handling

**Strategy:** Explicit exception raising with HTTP status codes

**Patterns:**
- `HTTPException` with specific status codes (400, 401, 403, 404, 409, 500)
- Try-catch blocks in ML pipeline with fallback to "unknown" classification
- Database operation failures trigger 500 responses
- Validation failures (file type, size, auth) trigger 400/409 responses
- Missing resources (document, user) trigger 404 responses
- Insufficient permissions trigger 403 responses
- Document processing failures mark status as FAILED and store error message in `extracted_text` field

## Cross-Cutting Concerns

**Logging:** Print statements in ML pipeline (`app/ml/ocr.py`, `app/ml/pdf_extractor.py`); no structured logging configured

**Validation:**
- Pydantic schemas enforce input validation (`app/schemas/`)
- File extension whitelist in config
- File size limits in config
- Enum validation for categories and status values

**Authentication:**
- JWT token middleware via FastAPI dependencies
- HTTPBearer scheme in `utils/security.py`
- Token expiry set to 24 hours
- User status check (is_active flag)

**Data Isolation:**
- All document queries filter by `current_user.id`
- No cross-user data access possible via API
- Frontend enforces routing rules (redirect unauthenticated to login)

---

*Architecture analysis: 2026-02-17*
