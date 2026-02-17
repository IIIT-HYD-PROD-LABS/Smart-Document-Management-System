# Technology Stack

**Analysis Date:** 2026-02-17

## Languages

**Primary:**
- Python 3.x - Backend services (FastAPI, ML, OCR, PDF processing)
- TypeScript 5.5.3 - Frontend type safety
- JavaScript (React 18) - Frontend runtime

**Secondary:**
- SQL - Database queries via SQLAlchemy
- JSX/TSX - React component definitions

## Runtime

**Environment:**
- Node.js (Next.js 14.2.5) - Frontend development and build
- Python 3.x - Backend runtime with FastAPI/Uvicorn
- Docker - Containerized deployment

**Package Manager:**
- npm - Frontend dependency management (`frontend/package.json`)
- pip - Backend dependency management (`backend/requirements.txt`)
- Lockfile: package-lock.json present for frontend

## Frameworks

**Core:**
- FastAPI 0.104.1 - Backend REST API framework
- Next.js 14.2.5 - Frontend React framework with SSR
- React 18.3.1 - UI component library
- React DOM 18.3.1 - DOM rendering

**Async Processing:**
- Celery 5.3.6 - Distributed task queue for async document processing
- Redis 5.0.1 - Message broker and result backend

**Testing:**
- pytest 7.4.3 - Python testing framework
- httpx 0.25.2 - HTTP client for async tests

**Build/Dev:**
- TypeScript 5.5.3 - Type checking
- Tailwind CSS 3.4.4 - Utility-first CSS framework
- PostCSS 8.4.38 - CSS transformation
- Autoprefixer 10.4.19 - CSS vendor prefixing

## Key Dependencies

**Backend - Database:**
- SQLAlchemy 2.0.23 - ORM for database operations
- psycopg2-binary 2.9.9 - PostgreSQL adapter
- Alembic 1.13.0 - Database migration tool

**Backend - Authentication:**
- PyJWT 2.8.0 - JWT token generation and validation
- bcrypt 4.1.2 - Password hashing
- passlib[bcrypt] 1.7.4 - Password hashing utilities
- python-multipart 0.0.6 - Multipart form parsing for file uploads

**Backend - ML & NLP:**
- scikit-learn 1.3.2 - Machine learning models (TF-IDF, document classification)
- numpy 1.26.2 - Numerical computing
- pandas 2.1.4 - Data manipulation
- joblib 1.3.2 - Model serialization (loading `.pkl` model files)

**Backend - Document Processing:**
- pytesseract 0.3.10 - OCR text extraction from images
- opencv-python-headless 4.8.1.78 - Image preprocessing (grayscale, threshold, deskew)
- Pillow 10.1.0 - Image format handling
- pdfplumber 0.10.3 - PDF text extraction (text-based and scanned)
- PyPDF2 3.0.1 - PDF manipulation

**Backend - Cloud Storage:**
- boto3 1.33.6 - AWS S3 client for cloud file storage

**Backend - Configuration:**
- python-dotenv 1.0.0 - Environment variable loading from `.env`
- pydantic-settings 2.1.0 - Settings validation and management

**Backend - Utilities:**
- uvicorn[standard] 0.24.0 - ASGI server for FastAPI
- aiofiles 23.2.1 - Async file operations
- python-dateutil 2.8.2 - Date/time utilities

**Frontend - HTTP:**
- axios 1.7.2 - HTTP client with interceptor support for JWT auth

**Frontend - UI/UX:**
- react-dropzone 14.2.3 - File upload dropzone component
- react-hot-toast 2.4.1 - Toast notifications
- react-icons 5.2.1 - Icon library
- recharts 2.12.7 - Data visualization/charting
- framer-motion 11.2.12 - Animation library

**Frontend - Utilities:**
- date-fns 3.6.0 - Date formatting and manipulation
- js-cookie 3.0.5 - Cookie management (JWT token storage)

## Configuration

**Environment:**
- Backend: `.env` file (see `backend/.env.example`)
- Frontend: Environment variables via `next.config.mjs` (`NEXT_PUBLIC_API_URL`)
- Configuration managed via `app/config.py` using Pydantic settings

**Key Env Variables:**
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key
- `REDIS_URL` - Redis broker URL
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - S3 credentials (optional)
- `NEXT_PUBLIC_API_URL` - Frontend API endpoint

**Build:**
- `tsconfig.json` - TypeScript compiler configuration
- `next.config.mjs` - Next.js configuration (standalone output)
- `tailwind.config.ts` - Tailwind CSS configuration
- `postcss.config.mjs` - PostCSS pipeline configuration

## Platform Requirements

**Development:**
- Python 3.8+ with pip
- Node.js 18+ with npm
- PostgreSQL 14+ (via Docker)
- Redis 7+ (via Docker)
- Tesseract OCR (system dependency)

**Production:**
- Docker & Docker Compose for containerization
- PostgreSQL database
- Redis instance
- AWS S3 (optional, for cloud storage)
- Tesseract OCR binary installed on system or container

**Deployment:**
- Docker containers: `backend/Dockerfile`, `frontend/Dockerfile`
- Docker Compose orchestration: `docker-compose.yml`
- Standalone Next.js output enabled

---

*Stack analysis: 2026-02-17*
