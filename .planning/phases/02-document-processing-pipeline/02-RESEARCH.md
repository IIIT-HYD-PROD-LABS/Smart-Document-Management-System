# Phase 2: Document Processing Pipeline - Research

**Researched:** 2026-03-01
**Domain:** Document text extraction (OCR, PDF, DOCX), async task processing (Celery/Redis), metadata extraction, bulk upload UX
**Confidence:** HIGH

## Summary

Phase 2 transforms the existing synchronous document processing into a production-grade asynchronous pipeline. The codebase already has significant infrastructure in place: Celery configuration (`app/tasks/__init__.py`), a document task (`app/tasks/document_tasks.py`), OCR with image preprocessing (`app/ml/ocr.py`), PDF extraction with OCR fallback (`app/ml/pdf_extractor.py`), and a Docker Compose with Redis and a Celery worker service. The upload endpoint currently processes documents **synchronously** despite the async infrastructure existing -- the key work is wiring the async path, adding DOCX support, enhancing image preprocessing, implementing metadata extraction, and building frontend progress tracking.

The primary gaps are: (1) DOCX file type is not in `ALLOWED_EXTENSIONS` and no DOCX extractor exists, (2) the upload endpoint in `documents.py` calls `extract_and_classify()` synchronously instead of dispatching to Celery, (3) the Document model has no metadata fields (date, amount, vendor), (4) there is no `/api/documents/{id}/status` polling endpoint, (5) the frontend has no per-file upload progress via `onUploadProgress` and no polling for processing status, and (6) the Celery worker in Docker Compose references `app.tasks.celery_app` but the actual module exports `celery_app` from `app.tasks` -- this needs verification.

**Primary recommendation:** Wire the existing Celery infrastructure first (Plan 02-02), then add DOCX support and improve preprocessing (Plan 02-01), then metadata extraction (Plan 02-04), then frontend bulk upload with progress (Plan 02-03).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROC-01 | Upload PDF, JPG, PNG, DOCX via drag-and-drop | Add `"docx"` to `ALLOWED_EXTENSIONS`, create `docx_extractor.py` using python-docx, update `extract_and_classify()` to handle DOCX. Frontend dropzone already accepts PDF/PNG/JPG -- add DOCX MIME type. |
| PROC-02 | Tesseract OCR with image preprocessing (deskew, threshold, noise removal) | Existing `ocr.py` already implements grayscale, Gaussian blur, adaptive threshold, and deskew via `cv2.minAreaRect`. Consider adding morphological open/close for better noise removal and median filter as alternative to Gaussian. |
| PROC-03 | Extract text from digital PDFs using pdfplumber | Already implemented in `pdf_extractor.py` with OCR fallback for scanned pages. Works correctly -- verify tolerance settings for edge cases. |
| PROC-04 | Automatic metadata extraction (date, amount, vendor) | New `metadata_extractor.py` using regex patterns for dates (multiple formats), currency amounts (INR/USD), and vendor heuristics (first line, "from:", header patterns). Add `extracted_metadata` JSON column to Document model. |
| PROC-05 | Async processing via Celery (non-blocking uploads) | Switch upload endpoint from synchronous `extract_and_classify()` to `process_document_task.delay(doc.id)`. Celery app and task already exist -- wire them. Add status polling endpoint. |
| PROC-06 | Bulk upload (multiple documents at once) | Frontend already supports multi-file dropzone and queued uploads. Backend needs a bulk upload endpoint or parallel individual uploads. Frontend needs per-file `onUploadProgress` tracking. |
| PROC-07 | Upload progress indicators and processing status | Add `GET /api/documents/{id}/status` endpoint returning Celery task state. Frontend polls after upload returns 202. Add `celery_task_id` column to Document model. Use Celery `update_state(state='PROGRESS', meta={...})`. |
| INFR-05 | Celery workers and Redis in Docker Compose | Docker Compose already has `celery_worker` and `redis` services. Verify the command path, add healthcheck with `celery inspect ping`, add `restart: unless-stopped`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| celery | 5.3.6 | Distributed task queue for async document processing | Already in requirements.txt; industry standard for Python async tasks |
| redis | 5.0.1 | Message broker and result backend for Celery | Already in requirements.txt and docker-compose; fast, reliable |
| pdfplumber | 0.10.3 | Digital PDF text extraction | Already in requirements.txt and implemented; benchmark score 95 on Context7 |
| pytesseract | 0.3.10 | OCR for scanned documents and images | Already in requirements.txt and implemented; standard Python Tesseract wrapper |
| opencv-python-headless | 4.8.1.78 | Image preprocessing for OCR (deskew, threshold, noise) | Already in requirements.txt and implemented; industry standard for image processing |
| python-docx | 1.1.2 | DOCX text extraction | **NEW** -- standard library for reading Word documents; BSD license; actively maintained |
| python-dateutil | 2.8.2 | Fuzzy date parsing from extracted text | Already in requirements.txt; `parse(text, fuzzy=True)` extracts dates from unstructured text |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | 10.1.0 | Image format handling (PIL) | Already in requirements.txt; used by OCR pipeline for image conversion |
| structlog | 25.5.0 | Structured logging throughout pipeline | Already in requirements.txt; all logging must use structlog per project convention |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-docx | docx2python | docx2python extracts headers/footers/footnotes but python-docx is more widely used and sufficient for text extraction |
| python-dateutil (fuzzy) | dateparser | dateparser handles 200+ languages and `search_dates()` finds multiple dates, but python-dateutil is already a dependency and sufficient for v1 |
| pdfplumber | PyMuPDF (fitz) | PyMuPDF is faster but pdfplumber is already implemented and working; no reason to switch |
| Polling for status | SSE (Server-Sent Events) | SSE provides real-time push updates but adds complexity; polling every 2-3 seconds is simpler and sufficient for document processing timescales |

**Installation (new dependency only):**
```bash
pip install python-docx==1.1.2
```

## Architecture Patterns

### Recommended Project Structure Changes
```
backend/app/
├── ml/
│   ├── ocr.py               # (existing) Image OCR with preprocessing
│   ├── pdf_extractor.py      # (existing) PDF text extraction + OCR fallback
│   ├── docx_extractor.py     # (NEW) DOCX text extraction
│   ├── metadata_extractor.py # (NEW) Date, amount, vendor extraction
│   ├── classifier.py         # (existing) ML classification -- update extract_and_classify
│   └── text_preprocessor.py  # (existing) Text cleaning for ML
├── tasks/
│   ├── __init__.py           # (existing) Celery app config
│   └── document_tasks.py     # (existing) Update task to include metadata extraction
├── routers/
│   └── documents.py          # (existing) Add status endpoint, switch to async
├── models/
│   └── document.py           # (existing) Add metadata fields, celery_task_id
└── schemas/
    └── document.py           # (existing) Add metadata fields to response schemas
```

### Pattern 1: Async Upload with Celery Dispatch
**What:** Upload endpoint saves file and DB record, dispatches Celery task, returns 202 Accepted immediately.
**When to use:** All document uploads -- never process synchronously in the request handler.
**Example:**
```python
# Source: Celery docs + existing codebase pattern
@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(file: UploadFile = File(...), ...):
    # Validate, save file, create DB record with status=PENDING
    doc = Document(status=DocumentStatus.PENDING, ...)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Dispatch async task
    task = process_document_task.delay(doc.id)

    # Store task ID for status polling
    doc.celery_task_id = task.id
    db.commit()

    return DocumentUploadResponse(
        id=doc.id, filename=doc.original_filename,
        status="pending", task_id=task.id,
        message="Document uploaded. Processing started."
    )
```

### Pattern 2: Celery Task with Progress Updates
**What:** Celery task uses `self.update_state()` to report progress stages (extracting, classifying, extracting metadata).
**When to use:** In `process_document_task` to enable frontend progress tracking.
**Example:**
```python
# Source: Celery docs (https://docs.celeryq.dev/en/stable/userguide/tasks)
@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: int):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        doc.status = DocumentStatus.PROCESSING
        db.commit()

        # Stage 1: Text extraction
        self.update_state(state='PROGRESS', meta={'stage': 'extracting_text', 'progress': 25})
        extracted_text = extract_text(doc.file_path, doc.file_type)

        # Stage 2: Classification
        self.update_state(state='PROGRESS', meta={'stage': 'classifying', 'progress': 50})
        category, confidence = classify_document(extracted_text)

        # Stage 3: Metadata extraction
        self.update_state(state='PROGRESS', meta={'stage': 'extracting_metadata', 'progress': 75})
        metadata = extract_metadata(extracted_text)

        # Stage 4: Save results
        doc.extracted_text = extracted_text
        doc.category = category
        doc.confidence_score = confidence
        doc.extracted_metadata = metadata
        doc.status = DocumentStatus.COMPLETED
        db.commit()
        return {"status": "completed", "document_id": document_id}

    except Exception as e:
        doc.status = DocumentStatus.FAILED
        db.commit()
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()
```

### Pattern 3: Status Polling Endpoint
**What:** GET endpoint returns current processing status by querying Celery AsyncResult.
**When to use:** Frontend polls this after upload returns 202.
**Example:**
```python
# Source: Celery AsyncResult docs
from celery.result import AsyncResult

@router.get("/{document_id}/status")
def get_document_status(document_id: int, db: Session = Depends(get_db), ...):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404)

    response = {"document_id": doc.id, "status": doc.status.value}

    if doc.celery_task_id and doc.status == DocumentStatus.PROCESSING:
        task_result = AsyncResult(doc.celery_task_id, app=celery_app)
        if task_result.state == 'PROGRESS':
            response["progress"] = task_result.info
    return response
```

### Pattern 4: DOCX Text Extraction
**What:** Extract text from DOCX files preserving paragraph and table content order.
**When to use:** When `file_type == "docx"`.
**Example:**
```python
# Source: python-docx docs (https://python-docx.readthedocs.io)
from docx import Document as DocxDocument

def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    parts = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                parts.append(" | ".join(row_text))
    return "\n".join(parts)
```

### Pattern 5: Regex-Based Metadata Extraction
**What:** Extract dates, amounts, and vendor names from OCR/PDF extracted text using regex + dateutil.
**When to use:** After text extraction, before saving to DB.
**Example:**
```python
# Source: python-dateutil docs, regex patterns for Indian financial documents
import re
from dateutil.parser import parse as dateutil_parse

def extract_dates(text: str) -> list[str]:
    """Extract dates using regex + fuzzy dateutil parsing."""
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',          # DD/MM/YYYY or MM-DD-YY
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4}',
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}',
    ]
    dates = []
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                parsed = dateutil_parse(m, fuzzy=True)
                dates.append(parsed.isoformat())
            except (ValueError, OverflowError):
                pass
    return dates

def extract_amounts(text: str) -> list[dict]:
    """Extract currency amounts (INR/USD)."""
    patterns = [
        (r'(?:Rs\.?|INR|₹)\s*([\d,]+\.?\d*)', 'INR'),
        (r'\$([\d,]+\.?\d*)', 'USD'),
        (r'(?:Total|Amount|Grand Total|Net Amount)[:\s]*(?:Rs\.?|INR|₹|\$)?\s*([\d,]+\.?\d*)', 'INR'),
    ]
    amounts = []
    for pattern, currency in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(1).replace(',', '')
            try:
                amounts.append({"amount": float(value), "currency": currency})
            except ValueError:
                pass
    return amounts
```

### Anti-Patterns to Avoid
- **Synchronous processing in request handler:** Never call `extract_and_classify()` directly in the upload endpoint. Always dispatch to Celery. The current code does this -- it must be changed.
- **Shared DB session across threads:** Celery workers run in separate processes. Always create a new `SessionLocal()` per task (already done correctly in existing task code).
- **Polling too frequently:** Frontend should poll every 2-3 seconds, not every 100ms. Use exponential backoff if task is long-running.
- **Large file bytes in Celery task arguments:** Never pass file bytes as task arguments. Pass the document ID and read from storage in the worker (already done correctly).
- **Blocking Celery worker with CPU-bound preprocessing:** Image preprocessing and OCR are CPU-intensive. Set `worker_concurrency` based on available cores, not higher.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date parsing from text | Custom regex-only date parser | python-dateutil `parse(fuzzy=True)` | Handles dozens of date formats, timezone awareness, edge cases |
| DOCX parsing | Manual XML/ZIP extraction | python-docx `Document()` | DOCX is a complex ZIP+XML format with styles, headers, footnotes |
| PDF text extraction | Raw PDF byte parsing | pdfplumber (already used) | PDF is notoriously complex; pdfplumber handles fonts, encodings, layouts |
| Task queue | Threading or asyncio background tasks | Celery (already configured) | Process isolation, retry logic, result backend, monitoring |
| Image deskew angle detection | Manual Hough transform | OpenCV `minAreaRect` (already used) | Tested, optimized C++ underneath, handles edge cases |
| File upload progress | Custom byte counting | Axios `onUploadProgress` | Built into Axios, uses XMLHttpRequest progress events |

**Key insight:** Document processing has decades of accumulated edge cases (PDF encodings, image noise, date format variations). Every component that touches document content should use a mature library, not custom code.

## Common Pitfalls

### Pitfall 1: Celery Worker Cannot Import App Modules
**What goes wrong:** Celery worker fails to start with `ModuleNotFoundError` because PYTHONPATH is not set correctly in Docker.
**Why it happens:** Docker container runs Celery from a different working directory than expected, or the `WORKDIR` in Dockerfile doesn't match the import paths.
**How to avoid:** Ensure `WORKDIR /app` in Dockerfile and that the Celery command is `celery -A app.tasks worker`. The existing docker-compose uses `celery -A app.tasks.celery_app worker` -- verify this resolves correctly (should be `celery -A app.tasks worker` since `celery_app` is defined in `app/tasks/__init__.py`).
**Warning signs:** Worker logs show `ImportError` or `ModuleNotFoundError` on startup.

### Pitfall 2: Database Session Leaks in Celery Tasks
**What goes wrong:** Database connections are exhausted because Celery tasks don't properly close sessions.
**Why it happens:** Exception paths skip `db.close()`, or sessions are shared between tasks.
**How to avoid:** Always use `try/finally` with `db.close()` in Celery tasks. The existing code does this correctly -- maintain this pattern. Consider using a context manager.
**Warning signs:** `sqlalchemy.exc.TimeoutError: QueuePool limit reached` in logs.

### Pitfall 3: File Not Found in Celery Worker
**What goes wrong:** Celery task cannot find the uploaded file because the worker runs in a different container/volume.
**Why it happens:** Upload directory is not shared between backend and worker containers.
**How to avoid:** Docker Compose already shares `backend_uploads` volume between `backend` and `celery_worker` services. Verify both mount to the same path (`/app/uploads`).
**Warning signs:** `FileNotFoundError` in task logs; status shows FAILED for all documents.

### Pitfall 4: OCR Returns Empty String for Low-Quality Scans
**What goes wrong:** Tesseract returns empty or garbage text from poorly scanned documents.
**Why it happens:** Image preprocessing is insufficient for the specific degradation type (heavy noise, extreme skew, low DPI).
**How to avoid:** Apply multiple preprocessing stages in sequence: (1) resize to minimum 300 DPI, (2) grayscale, (3) median blur for salt-and-pepper noise, (4) adaptive threshold, (5) morphological open to remove small noise, (6) deskew. The existing code does steps 1-4 but misses morphological operations. Also consider trying both `--psm 6` (uniform block) and `--psm 3` (auto) and picking the result with more text.
**Warning signs:** `extracted_text` is empty or very short for image uploads.

### Pitfall 5: DOCX Files With Embedded Images
**What goes wrong:** DOCX files contain scanned images as the document content (common with "scanned to Word" workflows), and python-docx only extracts text paragraphs, missing the image content entirely.
**Why it happens:** python-docx reads text elements but doesn't OCR embedded images.
**How to avoid:** After extracting text from paragraphs/tables, check if the result is very short. If so, extract embedded images from the DOCX and run OCR on them. python-docx provides access to images via `doc.inline_shapes`.
**Warning signs:** DOCX uploads produce empty or very short extracted text.

### Pitfall 6: Race Condition Between Upload Response and Task Start
**What goes wrong:** Frontend polls for status before Celery task has picked up the job, gets PENDING status forever.
**Why it happens:** There's a delay between `task.delay()` and the worker actually starting the task.
**How to avoid:** The Document model status starts as PENDING, and the Celery task updates it to PROCESSING when it starts. Frontend should treat PENDING as "queued, waiting to process" and display appropriately. Don't show an error until status is FAILED.
**Warning signs:** Status shows PENDING for extended periods; user thinks upload failed.

### Pitfall 7: Metadata Extraction Regex Too Greedy
**What goes wrong:** Date/amount regex matches unintended text (phone numbers as amounts, reference numbers as dates).
**Why it happens:** Simple regex patterns without context boundaries match too broadly.
**How to avoid:** Use word boundary anchors (`\b`), require currency symbols or keywords before amounts, validate parsed dates are within reasonable ranges (e.g., 2000-2030), deduplicate results.
**Warning signs:** Metadata shows obviously wrong values (phone numbers as amounts, years in the future).

## Code Examples

### DOCX Text Extraction Module
```python
# Source: python-docx docs (https://python-docx.readthedocs.io)
"""DOCX text extraction module."""
import io
import structlog
from docx import Document as DocxDocument

logger = structlog.stdlib.get_logger()

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file, including paragraphs and tables."""
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        parts = []

        # Extract paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                parts.append(text)

        # Extract table content
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))

        return "\n".join(parts)

    except Exception as e:
        logger.error("docx_extraction_failed", error=str(e))
        return ""
```

### Updated extract_and_classify with DOCX Support
```python
# Source: Existing classifier.py pattern
def extract_and_classify(file_bytes: bytes, file_type: str) -> tuple[str, str, float]:
    from app.ml.ocr import extract_text_from_image
    from app.ml.pdf_extractor import extract_text_from_pdf
    from app.ml.docx_extractor import extract_text_from_docx  # NEW

    if file_type == "pdf":
        extracted_text = extract_text_from_pdf(file_bytes)
    elif file_type == "docx":
        extracted_text = extract_text_from_docx(file_bytes)
    else:
        extracted_text = extract_text_from_image(file_bytes)

    if not extracted_text:
        return "", "unknown", 0.0

    category, confidence = classify_document(extracted_text)
    return extracted_text, category, confidence
```

### Metadata Extraction Module
```python
# Source: python-dateutil docs + regex patterns
"""Metadata extraction from document text."""
import re
from dateutil.parser import parse as dateutil_parse
import structlog

logger = structlog.stdlib.get_logger()

def extract_metadata(text: str) -> dict:
    """Extract date, amount, and vendor from document text."""
    return {
        "dates": extract_dates(text),
        "amounts": extract_amounts(text),
        "vendor": extract_vendor(text),
    }

def extract_dates(text: str) -> list[str]:
    patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}\b',
        r'\b\d{4}-\d{2}-\d{2}\b',
    ]
    dates = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                parsed = dateutil_parse(match.group(), fuzzy=True)
                if 2000 <= parsed.year <= 2030:
                    dates.append(parsed.strftime("%Y-%m-%d"))
            except (ValueError, OverflowError):
                pass
    return list(set(dates))[:5]  # Deduplicate, limit to 5

def extract_amounts(text: str) -> list[dict]:
    patterns = [
        (r'(?:Rs\.?|INR|₹)\s*([\d,]+\.?\d*)', 'INR'),
        (r'\$\s*([\d,]+\.?\d*)', 'USD'),
    ]
    amounts = []
    for pattern, currency in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value_str = match.group(1).replace(',', '')
            try:
                value = float(value_str)
                if 0.01 <= value <= 10_000_000:
                    amounts.append({"amount": value, "currency": currency})
            except ValueError:
                pass
    return amounts[:10]

def extract_vendor(text: str) -> str | None:
    lines = [l.strip() for l in text.split('\n') if l.strip()][:10]
    vendor_keywords = ['from:', 'vendor:', 'seller:', 'biller:', 'company:',
                       'merchant:', 'paid to:', 'payee:']
    for line in lines:
        lower = line.lower()
        for keyword in vendor_keywords:
            if keyword in lower:
                vendor = line[lower.index(keyword) + len(keyword):].strip()
                if vendor:
                    return vendor[:100]
    # Heuristic: first non-empty, non-date, non-amount line is often the vendor
    if lines:
        first_line = lines[0]
        if len(first_line) > 3 and not re.match(r'^[\d\s/.-]+$', first_line):
            return first_line[:100]
    return None
```

### Axios Upload with Per-File Progress
```typescript
// Source: Axios docs (https://axios-http.com/docs/req_config)
// Updated documentsApi.upload with progress callback
upload: (file: File, onProgress?: (percent: number) => void) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post("/documents/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (progressEvent) => {
            if (onProgress && progressEvent.total) {
                const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                onProgress(percent);
            }
        },
    });
},
```

### Frontend Status Polling
```typescript
// Source: Standard polling pattern
const pollStatus = async (documentId: number, interval = 2000) => {
    const poll = async () => {
        const { data } = await api.get(`/documents/${documentId}/status`);
        if (data.status === 'completed' || data.status === 'failed') {
            return data;
        }
        await new Promise(r => setTimeout(r, interval));
        return poll();
    };
    return poll();
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Synchronous processing in request handler | Celery async dispatch with immediate 202 response | Standard practice 2020+ | Upload returns in <1s regardless of document size |
| Polling for task status | SSE or WebSockets for real-time updates | 2023+ | Lower latency, but polling is still simpler and sufficient for this use case |
| Simple Otsu thresholding for OCR | Adaptive thresholding + morphological ops pipeline | Ongoing best practice | Better OCR accuracy on varied scan quality |
| Regex-only metadata extraction | NER models + regex hybrid | 2024+ for production systems | Better vendor extraction; but regex sufficient for v1 with known document types |

**Deprecated/outdated:**
- PyPDF2 for text extraction: pdfplumber is superior (already used in this project). PyPDF2 is in requirements.txt but appears unused -- can be removed.
- Celery 4.x patterns: Project uses Celery 5.3.6 which is current. Task configuration syntax is the same.

## Open Questions

1. **Celery worker command path**
   - What we know: Docker Compose uses `celery -A app.tasks.celery_app worker --loglevel=info`
   - What's unclear: Whether `-A app.tasks.celery_app` correctly resolves. Typically `-A app.tasks` is used when `celery_app` is defined in `__init__.py`. The `.celery_app` suffix tells Celery the variable name, which should work.
   - Recommendation: Test the existing command; if it fails, change to `celery -A app.tasks worker`.

2. **Document model schema migration for metadata**
   - What we know: Need to add `extracted_metadata` (JSON), `celery_task_id` (String) columns
   - What's unclear: Whether to use a single JSON column or separate columns for date/amount/vendor
   - Recommendation: Use a single `extracted_metadata` JSON column (PostgreSQL JSONB) for flexibility. Separate columns can be added later for indexing if search performance requires it.

3. **Max file size for DOCX**
   - What we know: Current max is 50MB in config but 16MB in frontend dropzone
   - What's unclear: Whether DOCX files in the expected use case (financial documents) will be large
   - Recommendation: Keep 16MB frontend limit. Financial DOCX files are typically small (<5MB). Align backend `MAX_FILE_SIZE_MB` with frontend if needed.

4. **Vendor extraction accuracy**
   - What we know: Regex + heuristic approach works for structured documents with clear headers
   - What's unclear: Accuracy on real Indian financial documents where vendor info may be in regional languages or non-standard positions
   - Recommendation: Start with regex/heuristic approach for v1. Phase 5 (Smart Extraction with LLM) will provide much better vendor extraction. Flag low-confidence extractions.

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/celeryq_dev_en_stable` - Celery task states, update_state, AsyncResult, result backend configuration
- Context7 `/websites/python-docx_readthedocs_io_en` - Document iteration, paragraph/table text extraction
- Context7 `/jsvine/pdfplumber` - Text extraction, table extraction, page-to-image conversion
- Existing codebase: `app/tasks/`, `app/ml/`, `app/routers/documents.py`, `docker-compose.yml`

### Secondary (MEDIUM confidence)
- [Tesseract OCR docs - Improve Quality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html) - Image preprocessing best practices
- [TestDriven.io - FastAPI and Celery](https://testdriven.io/blog/fastapi-and-celery/) - FastAPI + Celery integration patterns
- [Celery School - Docker Health Check](https://celery.school/docker-health-check-for-celery-workers) - Celery Docker healthcheck configuration
- [python-dateutil docs](https://dateutil.readthedocs.io/en/stable/parser.html) - Fuzzy date parsing from text

### Tertiary (LOW confidence)
- WebSearch for vendor extraction patterns - limited authoritative sources; regex approach is standard but accuracy depends heavily on document format

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All core libraries are already in the project or are well-established with Context7/official docs verification
- Architecture: HIGH - Celery async pattern is well-documented and the existing codebase already has the infrastructure scaffolded
- Pitfalls: HIGH - Common issues verified across multiple sources (Celery docs, Docker best practices, OCR preprocessing guides)
- Metadata extraction: MEDIUM - Regex patterns for dates and amounts are reliable; vendor extraction is heuristic-based and may need iteration

**Research date:** 2026-03-01
**Valid until:** 2026-03-31 (stable domain; libraries are mature)
