# Codebase Concerns

**Analysis Date:** 2026-02-17

## Tech Debt

### Hardcoded Security Credentials in Config
- **Issue:** Default SECRET_KEY exposed in source code with weak placeholder value
- **Files:**
  - `backend/app/config.py` (line 23): `SECRET_KEY: str = "super-secret-key-change-in-production"`
  - `backend/app/config.py` (line 17): `DEBUG: bool = True` (enabled in production)
  - `docker-compose.yml` (line 45): `SECRET_KEY: super-secret-docker-key`
- **Impact:** Attackers can forge JWT tokens if credentials leak. DEBUG mode exposes sensitive error traces and stack dumps
- **Fix approach:**
  - Move all secrets to environment variables with no defaults
  - Use `python-dotenv` to load from `.env` file (already done but defaults are problematic)
  - Set `DEBUG: bool = False` in production config
  - Implement environment-specific configuration (dev vs prod)
  - Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.) in production

### Generic Exception Handling in ML Pipeline
- **Issue:** Broad exception catching masks real errors, all failures logged as "Processing error" with exception string exposed
- **Files:** `backend/app/routers/documents.py` (lines 69-79)
- **Impact:** Exception details leak in response (`doc.extracted_text = f"Processing error: {str(e)}"`) - information disclosure vulnerability. Difficult to debug real issues
- **Fix approach:**
  - Catch specific exceptions (FileNotFoundError, OCRError, ClassificationError)
  - Log detailed errors to file/logging system, return generic message to client
  - Create custom exception types for different failure modes

### Silent S3 Error Suppression
- **Issue:** S3 deletion errors silently caught and ignored without logging
- **Files:** `backend/app/services/storage_service.py` (lines 90-93)
- **Impact:** Failed file deletions on S3 go undetected, leading to orphaned files and storage cost leaks
- **Fix approach:**
  - Log S3 errors with file key and timestamp
  - Implement retry logic with exponential backoff
  - Add monitoring/alerting for failed deletions
  - Consider soft-delete approach (mark as deleted, cleanup asynchronously)

### Unsafe S3 Key Extraction
- **Issue:** S3 URL parsing uses string split without validation
- **Files:** `backend/app/services/storage_service.py` (line 83): `s3_key = s3_url.split(f".amazonaws.com/")[-1]`
- **Impact:** Malformed URL could extract wrong key, deleting unintended files or failing silently
- **Fix approach:**
  - Use urllib.parse.urlparse instead of string splitting
  - Validate URL format before extraction
  - Store original S3 key in database instead of re-parsing URL
  - Add unit tests for URL parsing

### No Input Validation on String Parameters
- **Issue:** Some query parameters accepted but not sanitized against SQL injection or code execution
- **Files:**
  - `backend/app/routers/documents.py` (line 96): Search query accepts up to 500 chars but no sanitization
  - Database queries use SQLAlchemy ORM (safer) but user input passed directly to .ilike()
- **Impact:** Low risk due to ORM parameterization, but defense-in-depth missing
- **Fix approach:**
  - Add schema validation with Pydantic for all inputs
  - Sanitize special characters in search queries
  - Add length limits (already has max_length=500)

### Plaintext Error Messages to Frontend
- **Issue:** Backend returns error details that expose system internals
- **Files:**
  - `backend/app/routers/documents.py` (line 36): Returns full list of allowed file extensions
  - `backend/app/routers/documents.py` (line 157): Returns all valid category enum values
- **Impact:** Information disclosure - attackers learn system capabilities
- **Fix approach:**
  - Return generic error messages to frontend ("Invalid file type")
  - Log detailed errors server-side only
  - Create API documentation with allowed values (separate from error responses)

## Known Bugs

### Concurrent Upload Counter Miscalculation
- **Symptoms:** Upload confirmation shows wrong count when some uploads fail
- **Files:** `frontend/src/app/dashboard/upload/page.tsx` (line 65)
  ```typescript
  const doneCount = uploads.filter((u) => u.status === "done").length + queued.length;
  ```
- **Trigger:** Upload some files, some succeed, some fail, then click "Upload All" again
- **Issue:** Line 65 adds `queued.length` (from beginning of function) to done count, but queue has been modified by uploads. This counts both completed and failed items
- **Workaround:** Refresh page to see accurate count
- **Fix approach:** Track success count separately from initial queue length. Use `uploads.filter(u => u.status === "done").length` only

### Browser Cookie Storage of Sensitive Data
- **Symptoms:** User data exposed in plain cookies viewable in browser DevTools
- **Files:** `frontend/src/context/AuthContext.tsx` (line 49)
  ```typescript
  Cookies.set("user", JSON.stringify(userData), { expires: 7 });
  ```
- **Trigger:** Any authenticated user on a shared device
- **Issue:** Full user object (email, username) stored in cookies, visible in browser
- **Workaround:** Only store token in httpOnly cookie, load user data from API
- **Fix approach:**
  - Move token to httpOnly, secure, sameSite=strict cookie (requires backend coordination)
  - Store user data in-memory only or fetch from `/api/auth/me` on app load
  - Remove `Cookies.set("user", ...)` entirely

### Search Endpoint Accepts Both Query Positions
- **Symptoms:** Same endpoint `/search` accepts query param but route definition says query is required
- **Files:** `backend/app/routers/documents.py` (line 94-102)
- **Issue:** Endpoint path is `/search` but query parameter `q` is extracted via Query() without path context. Router doesn't include query param in path
- **Impact:** Works correctly but confusing for API consumers. OpenAPI docs might misrepresent endpoint
- **Fix approach:** Document properly that `/api/documents/search?q=term` is the correct format (already implemented, just confusing naming)

## Security Considerations

### CORS Configuration Allows Any Origin
- **Risk:** Wildcard allow_origins=["*"] enables cross-site request forgery attacks
- **Files:** `backend/app/main.py` (line 29): `allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"]`
- **Current mitigation:** Development-only addresses plus wildcard (wildcard negates all restrictions)
- **Recommendations:**
  - Remove wildcard "*" from allow_origins
  - Use environment-specific CORS config (dev allows localhost, prod only allows frontend domain)
  - Implement CSRF token validation for state-changing operations
  - Add `allow_credentials=False` in production if not cross-domain cookies needed

### No Rate Limiting on Authentication Endpoints
- **Risk:** Brute force attacks on login/register endpoints
- **Files:** `backend/app/routers/auth.py` (lines 14, 48)
- **Current mitigation:** None
- **Recommendations:**
  - Implement rate limiting (e.g., 5 attempts per 15 minutes per IP)
  - Use libraries like `slowapi` or manual Redis-based counter
  - Add account lockout after N failed attempts
  - Log suspicious activity

### No Password Complexity Requirements
- **Risk:** Users set weak passwords (minimum 6 chars, no complexity rules)
- **Files:** `backend/app/schemas/__init__.py` (line 12): `password: str = Field(..., min_length=6, max_length=128)`
- **Current mitigation:** Only minimum length
- **Recommendations:**
  - Require uppercase, lowercase, number, special character
  - Check against common password lists (HIBP API)
  - Implement password history (prevent reuse)
  - Add frontend validation with strength meter

### No Input Sanitization on File Upload Names
- **Risk:** Path traversal attacks if filename contains "../" sequences
- **Files:** `backend/app/routers/documents.py` (line 56): `os.path.basename(file_path) if file_path else file.filename`
- **Current mitigation:** `os.path.basename()` strips directory separators (safe for local storage)
- **Recommendations:**
  - Keep current basename() usage
  - Add explicit validation: reject filenames containing null bytes, control characters
  - Consider whitelist-only allowed characters (alphanumeric + safe punctuation)

### Database Credentials in Docker Compose
- **Risk:** Hardcoded postgres:postgres credentials in docker-compose.yml
- **Files:** `docker-compose.yml` (lines 9-11, 41, 62)
- **Current mitigation:** Development-only file
- **Recommendations:**
  - Use .env file for docker-compose
  - Add docker-compose.yml to .gitignore (it is currently tracked)
  - Use secrets management for container orchestration (Docker Swarm secrets / Kubernetes)
  - Different credentials for dev/test/prod

### Missing HTTPS/TLS in Frontend API Calls
- **Risk:** Tokens sent over HTTP in development, MITM attack possible
- **Files:** `frontend/src/lib/api.ts` (line 4): `http://localhost:8000` (hardcoded in dev)
- **Current mitigation:** Only in development
- **Recommendations:**
  - Enforce HTTPS in production
  - Add HSTS header to backend responses
  - Frontend should validate SSL certificates
  - Use environment variables for API URL scheme

## Performance Bottlenecks

### Synchronous ML Processing Blocks Requests
- **Problem:** Document upload waits for full ML classification before returning response
- **Files:** `backend/app/routers/documents.py` (lines 69-79): `try: extract_and_classify()` blocks the request
- **Cause:** No async/background task processing. Tesseract OCR + TF-IDF classification is CPU-intensive
- **Bottleneck:** Single request can take 5-30 seconds, blocking other uploads
- **Improvement path:**
  - Move to async Celery task (infrastructure exists: Redis broker configured)
  - Return 202 Accepted with task ID immediately
  - Implement polling endpoint `/api/documents/{id}/status` for task progress
  - Add WebSocket endpoint for real-time progress updates
  - Set up Celery worker with CPU-focused optimization

### N+1 Query Problem in Document Stats
- **Problem:** Category counts loop executes separate query for each category
- **Files:** `backend/app/routers/documents.py` (lines 194-197)
  ```python
  for cat in DocumentCategory:
      count = user_docs.filter(Document.category == cat).count()
  ```
- **Cause:** 7 categories = 7 separate SQL COUNT queries instead of single GROUP BY
- **Current impact:** Low (only 7 categories) but sets bad precedent
- **Improvement path:**
  - Use single GROUP BY query: `db.query(Document.category, func.count()).group_by(Document.category)`
  - Cache category counts in Redis (invalidate on document create/delete)
  - Add database indexes (already exists: `idx_documents_category_user`)

### Full Text Search Uses ILIKE Without Indexes
- **Problem:** Search across extracted_text (full document content) with ILIKE pattern match
- **Files:** `backend/app/routers/documents.py` (line 113): `Document.extracted_text.ilike(search_term)`
- **Cause:** No full-text search index on extracted_text field
- **Impact:** Slow for large documents with lots of text, O(n) table scan
- **Improvement path:**
  - Add PostgreSQL tsvector/tsquery full-text search index
  - Use `@@@` operator instead of ILIKE: more efficient for 100+ KB documents
  - Implement Elasticsearch/OpenSearch for distributed search at scale
  - Add pagination (already implemented) with limit on text matching

### Unscaled Document Retrieval
- **Problem:** No pagination limits when fetching all documents
- **Files:** `backend/app/routers/documents.py` (lines 222-246): Default limit is 50 per page
- **Impact:** User with 10,000+ documents could request page 1 with 50 items, still needs to iterate 200 pages
- **Improvement path:**
  - Add caching for recent documents (Redis)
  - Implement cursor-based pagination (more scalable than offset)
  - Add sorting options and default to recent-first
  - Consider archival strategy for old documents

## Fragile Areas

### ML Classifier Hard-Depends on External Model Files
- **Files:** `backend/app/ml/classifier.py` (lines 9-10, 19-29)
- **Why fragile:** Silent degradation if model files missing - returns "unknown" category with 0% confidence
- **Safety concerns:**
  - No validation that model files exist on startup
  - If models deleted, all new uploads classified as "unknown" silently
  - Tests likely don't catch this (no model files in test env)
- **Safe modification approach:**
  - Add startup check: raise FastAPI.on_event("startup") exception if models missing
  - Add health check endpoint `/api/health/ml` returning model status
  - Pre-load and cache models in app startup, not lazy-load
  - Unit tests must include model loading verification

### OCR Text Extraction No Error Handling
- **Files:** `backend/app/ml/ocr.py` (not shown, but called from classifier.py:68)
- **Why fragile:** If Tesseract not installed or corrupted image, unknown behavior
- **Safe modification approach:**
  - Wrap with try/except for system unavailability
  - Check Tesseract installation in app startup
  - Return partial results if OCR partial fails
  - Add timeout on OCR processing (prevent hung processes)

### Database Session Management Implicit
- **Files:** `backend/app/database.py` (lines 19-25)
- **Why fragile:** Session cleanup relies on exception handling. If endpoint doesn't complete normally, session might leak
- **Safe modification approach:**
  - Current implementation is safe (try/finally pattern)
  - Add logging on finally block to detect leaked sessions
  - Monitor pool_overflow (set to 20, could grow unbounded)
  - Add max_overflow limit or connection pooling timeout

### Frontend Auth State Not Synced with Server
- **Files:** `frontend/src/context/AuthContext.tsx` (lines 30-43)
- **Why fragile:** App loads user from cookies but doesn't validate with server. Stale/revoked tokens undetected
- **Safe modification approach:**
  - Add `/api/auth/verify` endpoint to validate token on app load
  - Set token expiration lower (currently 24 hours)
  - Implement refresh token pattern (short-lived access + longer-lived refresh)
  - Add logout from all devices endpoint (invalidate old tokens)

## Scaling Limits

### Local File Storage Has No Distribution
- **Current capacity:** Single machine filesystem (settings.UPLOAD_DIR)
- **Limit:** Disk space of single server. At 50 MB max per document, fills quickly
- **Scaling path:**
  - Already supports S3 via `USE_S3` flag but not tested/documented
  - For high-volume: switch to S3/GCS from day one
  - Implement multipart uploads for large files (currently single write)
  - Add storage quota per user

### PostgreSQL Connection Pool Fixed at 10
- **Current capacity:** 10 connections + 20 overflow = 30 max concurrent requests
- **Files:** `backend/app/database.py` (lines 9-12): `pool_size=10, max_overflow=20`
- **Limit:** Hard-coded. If 31+ concurrent requests, connection rejected
- **Scaling path:**
  - Make pool size configurable via environment variable
  - Use connection pooling proxy (PgBouncer) in front of PostgreSQL
  - Implement read replicas for search/stats queries (different pool)
  - Monitor connection usage, alert when >80% saturated

### Redis Single Node
- **Current capacity:** Single Redis instance for Celery broker/results (settings.REDIS_URL)
- **Limit:** One failure = all background tasks lost
- **Scaling path:**
  - Switch to Redis Sentinel for HA with automatic failover
  - Use Redis Cluster for distributed caching
  - Implement message queue fallback (SQS, RabbitMQ)

### Celery Not Actually Implemented
- **Issue:** Tasks configured but no usage in code. Document processing runs synchronously
- **Files:** `backend/app/routers/documents.py` (line 69): Synchronous extraction_and_classify, no task queuing
- **Impact:** Can't scale beyond single server capacity
- **Scaling path:**
  - Refactor to `.delay()` Celery tasks
  - Scale worker count independently from API servers
  - Add task monitoring/dead letter queue

## Dependencies at Risk

### Tesseract OCR System Dependency
- **Risk:** External binary dependency not managed by pip. System install required
- **Files:** `backend/app/config.py` (line 51): `TESSERACT_CMD: str = ""`
- **Impact:** Fails silently if Tesseract not installed. Hard to diagnose in production
- **Migration plan:**
  - Consider pytesseract wrapper but still needs system Tesseract
  - Evaluate cloud OCR APIs (AWS Textract, Google Vision) as alternative
  - Docker Dockerfile must install tesseract-ocr package (verify)
  - Add health check for Tesseract availability

### TensorFlow/sklearn Models Not Version Locked
- **Risk:** Model serialization format incompatible across versions
- **Files:** `backend/app/ml/classifier.py` (lines 24-25): Uses joblib to load pickled models
- **Impact:** Python/joblib/scikit-learn version mismatch breaks model loading
- **Migration plan:**
  - Pin joblib/scikit-learn versions in requirements.txt
  - Add model version metadata (saved alongside .pkl files)
  - Implement model versioning and migration path
  - Consider ONNX format for model interoperability

### No Requirements.txt or Lock File Found
- **Risk:** Unable to determine exact dependencies for reproduction/security updates
- **Impact:** Different developers/CI systems might use incompatible library versions
- **Current mitigation:** Likely using pip freeze or poetry
- **Migration plan:**
  - Ensure requirements.txt exists with pinned versions
  - Use pip-tools or Poetry for deterministic installs
  - Add pre-commit hook to validate requirements are locked

## Test Coverage Gaps

### No Unit Tests for ML Pipeline
- **Untested area:** Document classification, OCR extraction, text preprocessing
- **Files:** `backend/app/ml/` directory (all files)
- **Risk:** Silent failures in core ML functionality. False confidence scores undetected
- **Priority:** High
- **Fix approach:**
  - Mock TensorFlow/OCR dependencies in tests
  - Create fixtures with known document samples and expected classifications
  - Test edge cases: empty documents, corrupted images, unknown file types
  - Add integration tests with real model files (in CI environment)

### No Auth Endpoint Tests
- **Untested area:** Register/login/token validation flows
- **Files:** `backend/app/routers/auth.py`
- **Risk:** Security bugs in authentication (timing attacks, weak token validation, etc.)
- **Priority:** Critical
- **Fix approach:**
  - Test successful register/login flows
  - Test duplicate email/username rejection
  - Test invalid password attempts
  - Test token expiration and refresh
  - Test unauthorized endpoint access without token

### No Storage Service Tests
- **Untested area:** File upload/deletion, S3 integration
- **Files:** `backend/app/services/storage_service.py`
- **Risk:** File corruption, orphaned files on S3, race conditions in deletion
- **Priority:** High
- **Fix approach:**
  - Mock boto3 S3 client
  - Test local file save/delete
  - Test S3 URL generation and presigned URLs
  - Test file size validation and extension filtering

### No Frontend Component Tests
- **Untested area:** All React components
- **Files:** `frontend/src/app/**/*.tsx`, `frontend/src/context/**/*.tsx`
- **Risk:** UI bugs undetected, auth state management failures
- **Priority:** Medium
- **Fix approach:**
  - Set up Jest/React Testing Library
  - Add tests for critical components: Auth, Upload, Document List
  - Mock API responses with MSW (Mock Service Worker)
  - Test async behaviors (upload progress, error handling)

### No API Integration Tests
- **Untested area:** Full request/response flows, database state changes
- **Files:** All routers in `backend/app/routers/`
- **Risk:** Endpoint contract changes, permission bypasses
- **Priority:** High
- **Fix approach:**
  - Use pytest with FastAPI TestClient
  - Create test database that resets per test
  - Test authenticated vs unauthenticated access
  - Verify response schemas match OpenAPI spec

### No Database Migration Tests
- **Untested area:** Schema changes, data migrations
- **Files:** `backend/app/models/` (no migrations directory found)
- **Risk:** Data loss on schema upgrade, deployment failures
- **Priority:** Medium
- **Fix approach:**
  - Implement Alembic for migration management
  - Add tests for forward/backward migrations
  - Test zero-downtime migration patterns

---

*Concerns audit: 2026-02-17*
