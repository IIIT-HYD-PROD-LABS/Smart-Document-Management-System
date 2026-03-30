# Architecture Patterns: Compliance Management Integration

**Domain:** Compliance management layer on top of existing document management system
**Researched:** 2026-03-30
**Confidence:** HIGH (based on direct codebase analysis + established integration patterns)

---

## Recommended Architecture

The compliance system is a **vertical slice extension** of the existing application, not a separate service. New modules are added within the existing FastAPI and Next.js codebases, sharing all infrastructure (PostgreSQL, Redis, Celery, auth, storage). Elasticsearch runs as a sidecar search index — PostgreSQL remains the system of record.

### High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND (Next.js 14 on Vercel)                                     │
│  /dashboard/...                /compliance/...                       │
│  documents/* (existing)        notices/*, alerts/*, calendar/*       │
│  shared components: Badges, LoadingSpinner, StatusBadge              │
│  NEW: ComplianceContext (Zustand), useNotices/useAlerts (ReactQuery)  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ HTTPS + WebSocket
┌─────────────────────────────────▼───────────────────────────────────┐
│  FASTAPI BACKEND (on Render)                                          │
│                                                                       │
│  Existing routers:     NEW compliance routers:                        │
│  /api/auth             /api/compliance/notices                        │
│  /api/documents        /api/compliance/alerts                         │
│  /api/ml               /api/compliance/regulations                    │
│  /api/admin            /api/compliance/calendar                       │
│                        /api/compliance/responses                      │
│                        /api/compliance/reports                        │
│                        /ws/notifications  (WebSocket)                 │
│                                                                       │
│  Existing services:    NEW services:                                  │
│  audit_service         compliance_classifier_service                  │
│  llm_service           notice_ingestion_service                       │
│  storage_service       risk_scoring_service                           │
│                        portal_client_service                          │
│                        notification_service                           │
│                        response_draft_service                         │
│                        elasticsearch_sync_service                     │
│                                                                       │
│  Existing ML:          NEW ML:                                        │
│  scikit-learn/LinearSVC    BERT (transformers)                        │
│  TF-IDF                    spaCy NER                                  │
│  Tesseract OCR             XGBoost risk scorer                        │
└──────────┬───────────────────────────────┬──────────────────────────┘
           │                               │
┌──────────▼──────┐    ┌───────────────────▼───────┐    ┌────────────┐
│  PostgreSQL      │    │  Celery Workers            │    │  Elastic-  │
│  (Render)        │    │  (existing worker +        │    │  search    │
│  System of       │◄───│   NEW compliance worker)   │───►│  (cloud)   │
│  record          │    │                            │    │  Search    │
│  16 tables total │    │  NEW: APScheduler runs     │    │  index     │
│  (8 existing +   │    │  inside backend process    │    │  only      │
│   8 new)         │    │  for portal polling        │    │            │
└─────────────────┘    └──────────┬─────────────────┘    └────────────┘
                                  │
                   ┌──────────────▼──────────────────────┐
                   │  External Services                   │
                   │  GST Portal API / IT e-filing API    │
                   │  MCA API                             │
                   │  RBI/SEBI (web scraping)             │
                   │  SendGrid (email)                    │
                   │  Twilio (SMS)                        │
                   │  LLM API (response drafting)         │
                   └─────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **NoticeIngestionService** | Receive notices from portals, email, manual upload; trigger processing pipeline | PortalClientService, Celery tasks, Document model (for OCR reuse) |
| **ComplianceClassifierService** | BERT-based notice classification + spaCy NER extraction | ML layer (extends existing), NoticeModel |
| **RiskScoringService** | XGBoost risk scoring based on penalty, deadline proximity, authority, history | NoticeModel, ComplianceStatusModel |
| **PortalClientService** | API clients + scrapers for government portals; credential vault | GST/IT/MCA APIs, RBI/SEBI scrapers, credentials in encrypted DB fields |
| **NotificationService** | Route alerts via email/SMS/WebSocket based on rules; deduplicate | SendGrid, Twilio, WebSocket manager, AlertModel |
| **ResponseDraftService** | LLM-powered draft generation; version control; approval workflow | Existing LLMService (reuse providers), ResponseDraftModel, DocumentModel |
| **ElasticsearchSyncService** | Sync PostgreSQL notice/document changes to ES index; routing queries | PostgreSQL CDC (polling), Elasticsearch client |
| **APScheduler (in-process)** | Periodic jobs: portal polling, deadline scans, ES sync, report generation | Calls PortalClientService, NotificationService directly |

---

## Database Schema Design

### New Tables (8 additions to existing 8)

All new tables live in the same PostgreSQL database. Foreign keys to `users` and `documents` tables are the primary integration points.

```
┌──────────────────────────────────────────────────────────┐
│  EXISTING TABLES (unchanged schema)                       │
│  users, documents, document_permissions,                  │
│  document_versions, refresh_tokens, audit_logs            │
└────────────────────────┬─────────────────────────────────┘
                         │ FK: user_id, document_id
┌────────────────────────▼─────────────────────────────────┐
│  NEW COMPLIANCE TABLES                                    │
│                                                           │
│  notices                                                  │
│    id, user_id FK→users, document_id FK→documents(NULL)  │
│    notice_number, authority, notice_type, notice_date     │
│    deadline, penalty_amount, status, source               │
│    raw_text, classification_confidence, risk_score        │
│    risk_level, extracted_fields JSONB                     │
│    parent_notice_id FK→notices(self-ref, nullable)        │
│    gstin, pan, entity_name                                │
│    search_vector TSVECTOR (for PG FTS fallback)           │
│    created_at, updated_at                                 │
│                                                           │
│  compliance_statuses                                      │
│    id, notice_id FK→notices, user_id FK→users            │
│    status ENUM, notes TEXT, changed_at                    │
│    (full history: one row per transition)                 │
│                                                           │
│  alert_rules                                              │
│    id, user_id FK→users, notice_type, authority          │
│    days_before_deadline, channels JSONB                   │
│    severity_threshold, is_active                          │
│                                                           │
│  alerts                                                   │
│    id, notice_id FK→notices, user_id FK→users            │
│    channel ENUM(email,sms,in_app), status, sent_at        │
│    content JSONB, retry_count                             │
│                                                           │
│  response_drafts                                          │
│    id, notice_id FK→notices, created_by FK→users         │
│    version INTEGER, content TEXT, template_used           │
│    llm_provider, approval_status, approved_by FK→users   │
│    submitted_at, attachments JSONB                        │
│    (one notice can have many versioned drafts)            │
│                                                           │
│  regulations                                              │
│    id, authority, regulation_code, title                  │
│    content TEXT, effective_date, version                  │
│    search_vector TSVECTOR                                 │
│    created_at, updated_at                                 │
│                                                           │
│  notice_document_links                                    │
│    id, notice_id FK→notices, document_id FK→documents    │
│    link_type ENUM(evidence,attachment,related)            │
│    linked_by FK→users, linked_at                         │
│    (many-to-many bridge: notices ↔ documents)            │
│                                                           │
│  portal_credentials                                       │
│    id, user_id FK→users, portal ENUM, identifier         │
│    encrypted_credentials BYTEA (Fernet-encrypted)        │
│    last_sync_at, sync_status, is_active                  │
└──────────────────────────────────────────────────────────┘
```

### Schema Integration Notes

1. `notices.document_id` is nullable — manually uploaded notices get a document record created for them (OCR reuse); portal-fetched notices may not have a backing document file.
2. `notices.parent_notice_id` is a self-referential FK for notice chains (show cause → assessment order → penalty order).
3. The existing `audit_logs` table is **extended, not replaced** — compliance events use the same `log_audit_event()` service with `resource_type = "notice"` or `resource_type = "response_draft"`. No schema change needed.
4. `UserRole` enum in `app/models/user.py` gains 4 new values: `compliance_head`, `legal_team`, `finance_team`, `auditor`. This is a **migration-only change** — existing `role` column is VARCHAR(20), no Enum type change in PostgreSQL needed.
5. `portal_credentials.encrypted_credentials` uses Fernet symmetric encryption (Python `cryptography` library). The encryption key is stored in environment variables, never in the database.

---

## Backend Module Structure

### New Files to Create

```
backend/app/
  compliance/                          # New top-level package
    __init__.py
    routers/
      notices.py                       # CRUD + status workflow
      alerts.py                        # Alert rules + notification history
      regulations.py                   # Regulation library + calendar
      responses.py                     # Draft management + approval workflow
      reports.py                       # Analytics + audit export
      portals.py                       # Portal credential management + sync trigger
    models/
      notice.py
      compliance_status.py
      alert_rule.py
      alert.py
      response_draft.py
      regulation.py
      notice_document_link.py
      portal_credential.py
    schemas/
      notice.py
      alert.py
      regulation.py
      response_draft.py
      report.py
    services/
      notice_ingestion_service.py
      compliance_classifier_service.py
      risk_scoring_service.py
      portal_client_service.py
      notification_service.py
      response_draft_service.py
      elasticsearch_sync_service.py
    ml/
      bert_classifier.py               # BERT inference (loads from disk)
      ner_extractor.py                 # spaCy NER pipeline
      risk_scorer.py                   # XGBoost inference
      model_loader.py                  # Shared loader with caching
    tasks/
      compliance_tasks.py              # Celery tasks for compliance
      portal_tasks.py                  # Portal polling tasks
      notification_tasks.py            # Async notification delivery
    scheduler.py                       # APScheduler setup + job definitions
    websocket.py                       # WebSocket connection manager
```

### Existing Files Modified

| File | Change | Risk |
|------|--------|------|
| `app/main.py` | Include compliance routers; register WebSocket endpoint; add APScheduler lifespan | LOW — additive |
| `app/models/user.py` | Extend `UserRole` enum values | LOW — VARCHAR column, no PG type change |
| `app/tasks/__init__.py` | Add `app.compliance.tasks.*` to `include` list | LOW — additive |
| `app/config.py` | Add 15+ new config vars (ES, SendGrid, Twilio, portal credentials, scheduler) | LOW — additive |
| `app/database.py` | No change needed — existing `Base` and `SessionLocal` are reused as-is | NONE |
| `docker-compose.yml` | Add Elasticsearch service; add compliance_worker service; add APScheduler env vars | MEDIUM — new services |

### Router Registration in main.py

```python
# Existing (unchanged)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(ml.router)
app.include_router(admin.router)

# New compliance routers (all under /api/compliance prefix)
from app.compliance.routers import notices, alerts, regulations, responses, reports, portals
app.include_router(notices.router)     # /api/compliance/notices
app.include_router(alerts.router)      # /api/compliance/alerts
app.include_router(regulations.router) # /api/compliance/regulations
app.include_router(responses.router)   # /api/compliance/responses
app.include_router(reports.router)     # /api/compliance/reports
app.include_router(portals.router)     # /api/compliance/portals

# WebSocket for live notifications
from app.compliance.websocket import ws_router
app.include_router(ws_router)          # /ws/notifications
```

---

## Elasticsearch Integration

### Decision: Sidecar Search Index, Not System of Record

PostgreSQL is the authoritative source. Elasticsearch provides cross-entity search (notices + documents in one query) and faceted filtering at scale. The two systems stay consistent via an async sync service, not CDC triggers.

### Index Structure

Two indices, one alias for cross-index search:

```json
Index: "notices" {
  "notice_id": integer,
  "notice_number": keyword,
  "authority": keyword,
  "notice_type": keyword,
  "notice_date": date,
  "deadline": date,
  "status": keyword,
  "risk_level": keyword,
  "penalty_amount": float,
  "raw_text": text (analyzed),
  "extracted_fields": object,
  "user_id": integer,
  "gstin": keyword,
  "pan": keyword
}

Index: "documents" (mirror of existing PG data) {
  "document_id": integer,
  "category": keyword,
  "original_filename": text,
  "extracted_text": text (analyzed),
  "user_id": integer,
  "created_at": date
}

Alias: "compliance_search" -> [notices, documents]
```

### Sync Strategy

Sync is **polling-based** (not Logstash/Debezium) to avoid infrastructure complexity:

```
APScheduler job: sync_to_elasticsearch()
  runs every 30 seconds
  queries: SELECT * FROM notices WHERE updated_at > last_sync_checkpoint
  queries: SELECT * FROM documents WHERE updated_at > last_sync_checkpoint
  bulk indexes to Elasticsearch
  updates checkpoint in Redis (key: "es_sync_checkpoint")
```

Write path: all writes go to PostgreSQL first. ES sync is eventually consistent (max 30s lag).
Read path for cross-system search: query ES alias "compliance_search", return IDs, hydrate from PostgreSQL.
Read path for single-entity queries: query PostgreSQL directly (no ES needed).

### Search Routing Decision

```
Query type                    → Route to
─────────────────────────────────────────────────────
Simple notice list/filter     → PostgreSQL (direct query)
Full-text search (notices)    → Elasticsearch
Full-text search (documents)  → Elasticsearch (OR PostgreSQL FTS if ES unavailable)
Cross-entity unified search   → Elasticsearch alias
Analytics aggregations        → PostgreSQL (GROUP BY, window functions)
Audit log queries             → PostgreSQL (compliance requirement: authoritative source)
```

ES failure fallback: `ElasticsearchSyncService` exposes a health check; if ES is down, search routes automatically degrade to PostgreSQL FTS on `notices.search_vector`.

---

## Government Portal Integration Layer

### Architecture: Client-Per-Portal Behind a Unified Interface

```python
class PortalClient(ABC):
    """Unified interface for all government portal integrations."""
    async def fetch_notices(self, credentials: dict, since: datetime) -> list[RawNotice]: ...
    async def validate_credentials(self, credentials: dict) -> bool: ...
    async def health_check(self) -> PortalHealth: ...

class GSTPortalClient(PortalClient):    # Uses official GSTN API
class ITPortalClient(PortalClient):     # Uses IT e-filing API (limited official access)
class MCAPortalClient(PortalClient):    # Uses MCA21 API
class RBIScraperClient(PortalClient):   # httpx + BeautifulSoup scraping
class SEBIScraperClient(PortalClient):  # httpx + BeautifulSoup scraping
class EmailParserClient(PortalClient):  # IMAP integration for notice emails
```

### Credential Management

Credentials are stored encrypted in `portal_credentials` table using Fernet symmetric encryption. The encryption key (`PORTAL_CREDENTIAL_KEY`) is an environment variable, never stored in PostgreSQL. Decryption happens in-memory only during portal calls and is not logged.

```
portal_credentials row:
  encrypted_credentials = Fernet(key).encrypt(json.dumps({
    "username": "...",
    "password": "...",
    "client_id": "...",
    "otp_seed": "..."  # for TOTP-based portals
  }).encode())
```

### Rate Limiting Strategy

Each portal client enforces its own rate limit using token bucket algorithm in Redis:

```
Redis key: "portal_ratelimit:{portal}:{user_id}"
GST API:   max 100 req/min (per GSTN docs)
IT Portal: max 60 req/min (conservative — no official docs)
MCA API:   max 120 req/min
RBI/SEBI:  max 10 req/min (scraping — respect robots.txt)
```

### Scraping Approach for RBI/SEBI

RBI and SEBI have no official APIs. Approach: scrape public notice pages only (no authentication scraping), cache results for 4 hours, match against user's registered entity names.

RBI: `https://rbi.org.in/Scripts/Notifications.aspx` — paginated HTML
SEBI: `https://www.sebi.gov.in/enforcement/orders/` — paginated HTML

Tools: `httpx` (already likely in use) + `BeautifulSoup4`. Rate-limited to 10 req/min per IP. User-agent identifies the system. This is public data scraping, not credential-based access.

---

## ML Pipeline Extension

### Integration Strategy: Parallel Pipelines, Shared Infrastructure

Existing scikit-learn document classifier (`app/ml/classifier.py`) is **not modified**. New BERT/spaCy/XGBoost components live in `app/compliance/ml/` and load lazily with model caching.

```
Existing document pipeline (unchanged):
  file → OCR/PDF extractor → TF-IDF → LinearSVC → DocumentCategory

New notice pipeline (additive):
  notice text → BERT classifier → NoticeAuthority + NoticeType
                                ↓
                           spaCy NER → notice_number, deadline, penalty,
                                        legal_sections, authority_name
                                ↓
                           XGBoost → risk_score (0.0-1.0), risk_level
```

### Model Loading and Memory Management

BERT models are 400MB+. Loading strategy:

```python
# app/compliance/ml/model_loader.py
_model_cache: dict[str, Any] = {}

def get_bert_classifier() -> BertPipeline:
    if "bert" not in _model_cache:
        _model_cache["bert"] = pipeline(
            "text-classification",
            model="backend/compliance_models/bert_notice_classifier",
            device=-1  # CPU inference
        )
    return _model_cache["bert"]
```

Models are loaded once per **worker process** (not per request). Celery worker startup signal (`worker_process_init`) triggers model preloading. Memory budget per compliance_worker: 2GB (BERT ~400MB + spaCy ~200MB + XGBoost ~50MB + working memory).

### Model Storage

Models stored in `backend/compliance_models/` (gitignored, volume-mounted in Docker). On Render, models are loaded from a persistent disk or downloaded from S3 on first startup.

### BERT for Notice Classification

Pre-trained: `bert-base-multilingual-cased` or `ai4bharat/indic-bert` (better for Indian regulatory text). Fine-tuned on labeled notice dataset. Output: authority (RBI/SEBI/GST/IT/MCA/Legal) + notice type (show_cause/assessment/penalty/scrutiny/circular).

Integration with Hugging Face `transformers` library (pipeline API — simplest integration path for inference).

### spaCy NER for Entity Extraction

Custom NER model trained on Indian compliance text. Named entities: `NOTICE_NO`, `GSTIN`, `PAN`, `DEADLINE_DATE`, `PENALTY_AMOUNT`, `LEGAL_SECTION`, `AUTHORITY_NAME`.

Uses spaCy 3.x `en_core_web_sm` as base + custom compliance NER component. Model file: `backend/compliance_models/compliance_ner/`.

### XGBoost Risk Scorer

Tabular ML model. Input features:
- penalty_amount (log-scaled)
- days_until_deadline
- authority_risk_weight (RBI=0.9, SEBI=0.85, IT=0.75, GST=0.65, MCA=0.60, Legal=0.80)
- notice_type_weight
- historical_response_rate (per entity)
- recurrence_count

Output: `risk_score` (float 0.0–1.0), mapped to `risk_level` (critical/high/medium/low).

---

## Notification Service

### Architecture: Celery Tasks + WebSocket Manager

```
NotificationService.trigger_alert(notice, channel)
    │
    ├─ email → send_email_task.delay(notice_id, recipient)
    │              └─ Celery task → SendGrid API
    │
    ├─ sms → send_sms_task.delay(notice_id, recipient)
    │              └─ Celery task → Twilio API
    │
    └─ in_app → ws_manager.broadcast(user_id, payload)
                     └─ WebSocket → frontend NotificationContext
```

### WebSocket Manager

```python
# app/compliance/websocket.py
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    async def broadcast_to_user(self, user_id: int, message: dict):
        for ws in self.active_connections.get(user_id, []):
            await ws.send_json(message)

ws_manager = ConnectionManager()  # singleton, process-scoped

# FastAPI endpoint
@ws_router.websocket("/ws/notifications")
async def ws_endpoint(ws: WebSocket, token: str, db: Session = Depends(get_db)):
    user = verify_ws_token(token)  # JWT auth for WebSocket
    await ws_manager.connect(ws, user.id)
    try:
        while True:
            await ws.receive_text()  # keepalive ping/pong
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, user.id)
```

Celery tasks delivering in-app notifications cannot directly call the async WebSocket manager (different processes). Solution: Celery task publishes to a Redis pub/sub channel; a background asyncio task in the FastAPI process subscribes and forwards to WebSocket connections.

### Deduplication

Alert deduplication prevents spam for the same notice:

```
Redis key: "alert_dedup:{notice_id}:{channel}:{alert_type}"
TTL: 24 hours for deadline reminders, 1 hour for new notice alerts
```

### Smart Reminder Schedule

T-7, T-3, T-1 days before deadline + day-of overdue alert. Implemented as APScheduler jobs running on a fixed schedule, not as queued Celery tasks (eliminates risk of duplicate queuing across restarts).

---

## APScheduler Integration

### Co-existence with Celery

APScheduler handles **periodic triggers** (cron-like). Celery handles **execution** of the actual work. This separation is intentional:

- APScheduler runs inside the FastAPI process (via lifespan), not as a separate process
- On schedule fire, APScheduler calls `celery_task.delay()` — hands off to Celery immediately
- This avoids: dual worker processes, missed jobs on worker restart, schedule state in broker queue

```python
# app/compliance/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

def setup_compliance_scheduler():
    # Portal polling: every 6 hours
    scheduler.add_job(
        trigger_portal_sync_task,
        IntervalTrigger(hours=6),
        id="portal_sync",
        replace_existing=True,
    )
    # Deadline scan: daily at 8 AM IST
    scheduler.add_job(
        trigger_deadline_scan_task,
        CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        id="deadline_scan",
        replace_existing=True,
    )
    # ES sync: every 30 seconds
    scheduler.add_job(
        sync_to_elasticsearch,
        IntervalTrigger(seconds=30),
        id="es_sync",
        replace_existing=True,
    )
    return scheduler
```

APScheduler is started/stopped via FastAPI `lifespan` context manager:

```python
# app/main.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.compliance.scheduler import setup_compliance_scheduler
    scheduler = setup_compliance_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(lifespan=lifespan, ...)
```

### Multiple Backend Instances

On Render, if the backend scales to multiple instances, APScheduler will run in each instance, causing duplicate job fires. Mitigation: use `APScheduler` with `SQLAlchemyJobStore` backed by PostgreSQL. Only one instance acquires the distributed lock per scheduled job. Alternatively: set Render instance count to 1 for backend (appropriate for v2.0 single-tenant scope).

---

## Notice Data Flow (End-to-End)

```
[A] INGESTION (Multiple Sources)
     ├─ Portal API/Scraper (APScheduler fires every 6h)
     │    └─ PortalClientService.fetch_notices() → raw notice data
     ├─ Email parser (IMAP poll every 15min)
     │    └─ EmailParserClient.fetch_notices() → raw notice data
     └─ Manual upload (user action)
          └─ POST /api/compliance/notices/upload → file → OCR reuse

[B] NOTICE RECORD CREATION
     └─ NoticeIngestionService.ingest(raw_notice)
          ├─ Deduplicate by (notice_number, authority, user_id)
          ├─ Create notices row (status=received)
          ├─ Create audit_log entry (action=notice.received)
          └─ Queue: classify_and_extract_task.delay(notice_id)

[C] CLASSIFICATION & EXTRACTION (Celery task)
     └─ classify_and_extract_task(notice_id)
          ├─ BertClassifier.classify(text) → authority, notice_type, confidence
          ├─ NERExtractor.extract(text) → notice_number, deadline, penalty, sections
          ├─ Update notices row (classification fields, extracted_fields)
          ├─ Queue: score_risk_task.delay(notice_id)
          └─ Create audit_log entry (action=notice.classified)

[D] RISK SCORING (Celery task)
     └─ score_risk_task(notice_id)
          ├─ RiskScorer.score(notice) → risk_score, risk_level
          ├─ Update notices row (risk_score, risk_level)
          ├─ If risk_level in [critical, high]: trigger_escalation_alerts()
          ├─ Create compliance_statuses row (status=under_review)
          └─ Create audit_log entry (action=notice.scored)

[E] ALERT DISPATCH
     └─ NotificationService.evaluate_and_dispatch(notice)
          ├─ Load matching alert_rules for user + notice type
          ├─ For each matching rule:
          │    ├─ Check dedup Redis key
          │    ├─ Create alerts row
          │    └─ Dispatch: send_email_task / send_sms_task / ws_broadcast
          └─ Create audit_log entry (action=alert.dispatched)

[F] DASHBOARD DISPLAY
     └─ GET /api/compliance/notices?filters...
          ├─ PostgreSQL query with RBAC filter (user_id / role)
          ├─ Returns paginated notices with status, risk, deadline
          └─ Frontend WebSocket receives real-time updates for new notices

[G] RESPONSE DRAFTING
     └─ POST /api/compliance/responses
          ├─ ResponseDraftService.generate_draft(notice_id)
          │    ├─ Load notice context + linked documents
          │    ├─ Call existing LLMService (reuse provider chain)
          │    ├─ Apply notice-type-specific prompt template
          │    └─ Create response_drafts row (version=1, status=draft)
          ├─ Multi-stage approval workflow:
          │    └─ PATCH /api/compliance/responses/{id}/approve
          │         └─ compliance_head / legal_team roles only
          └─ Create audit_log entries at each workflow stage

[H] AUDIT & REPORTING
     └─ GET /api/compliance/reports
          ├─ PostgreSQL aggregations (GROUP BY authority, status, month)
          ├─ Returns compliance health score, penalty analysis, SLA metrics
          └─ audit_logs queried directly for immutable trail (never via ES)

[I] ELASTICSEARCH SYNC (async, eventual consistency)
     └─ APScheduler fires sync_to_elasticsearch every 30s
          ├─ Query notices + documents updated since last checkpoint
          ├─ Bulk upsert to ES
          └─ Used only for: unified search, full-text notice search
```

---

## Frontend Architecture

### New Routes (Next.js App Router)

```
frontend/src/app/
  compliance/                          # New compliance section
    layout.tsx                         # Compliance shell layout (sidebar nav)
    page.tsx                           # Redirect → /compliance/notices
    notices/
      page.tsx                         # Notice list with filters + risk indicators
      [id]/
        page.tsx                       # Notice detail: timeline, linked docs, responses
        response/
          page.tsx                     # Response drafting interface
    alerts/
      page.tsx                         # Alert rules + notification history
    regulations/
      page.tsx                         # Regulation library + calendar
    reports/
      page.tsx                         # Compliance health dashboard + export
    portals/
      page.tsx                         # Portal credential management + sync status
```

### State Management Upgrade

Current frontend uses only React Context (`AuthContext`). Compliance features require more sophisticated state:

```typescript
// New: Zustand store for compliance UI state
// frontend/src/store/complianceStore.ts
interface ComplianceStore {
  selectedFilters: NoticeFilters;
  setFilters: (filters: Partial<NoticeFilters>) => void;
  pendingNotifications: Notification[];
  addNotification: (n: Notification) => void;
  wsConnected: boolean;
  setWsConnected: (v: boolean) => void;
}

// React Query for server state (notices, alerts, regulations)
// frontend/src/hooks/useNotices.ts
export function useNotices(filters: NoticeFilters) {
  return useQuery({
    queryKey: ["notices", filters],
    queryFn: () => complianceApi.getNotices(filters),
    staleTime: 30_000,
  });
}
```

`AuthContext` is **not replaced** — it remains the auth source of truth. Zustand supplements it for compliance-specific UI state. React Query manages all server-state caching for compliance endpoints.

### Shared Components (new)

```typescript
// Extend existing components/index.ts
RiskBadge.tsx           // CRITICAL/HIGH/MEDIUM/LOW with color coding
DeadlineCountdown.tsx   // "3 days remaining" with urgency styling
AuthorityBadge.tsx      // RBI/SEBI/GST/IT/MCA badges
NoticeStatusBadge.tsx   // Received/Under Review/Drafted/Submitted/Resolved
ComplianceHealthScore.tsx  // Circular score indicator for dashboard
```

Existing shared components (`CategoryBadge`, `StatusBadge`, `ConfidenceBadge`, `LoadingSpinner`) are **reused without modification**.

### WebSocket Client

```typescript
// frontend/src/lib/websocket.ts
class NotificationWebSocket {
  private ws: WebSocket | null = null;

  connect(token: string) {
    this.ws = new WebSocket(
      `${process.env.NEXT_PUBLIC_WS_URL}/ws/notifications?token=${token}`
    );
    this.ws.onmessage = (event) => {
      const notification = JSON.parse(event.data);
      complianceStore.getState().addNotification(notification);
    };
    // Reconnect with exponential backoff on disconnect
  }
}
```

`NEXT_PUBLIC_WS_URL` is the backend URL with `ws://` or `wss://` scheme. On Render, this requires upgrading the plan to support WebSocket connections (Render starter plan supports WebSockets on HTTP services).

---

## Deployment Architecture

### Docker Compose Changes (local dev)

```yaml
# Add to docker-compose.yml

  # Elasticsearch (local dev only — use managed cloud in prod)
  elasticsearch:
    image: elasticsearch:8.13.0
    container_name: smartdocs-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9200/_cluster/health"]
      interval: 15s
      timeout: 10s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 1G

  # Compliance Celery Worker (separate from document worker)
  compliance_worker:
    build: ./backend
    container_name: smartdocs-compliance-worker
    command: celery -A app.tasks.celery_app worker -Q compliance -l info --concurrency=2 --max-memory-per-child=2048000
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      ELASTICSEARCH_URL: http://elasticsearch:9200
      SENDGRID_API_KEY: ${SENDGRID_API_KEY}
      TWILIO_ACCOUNT_SID: ${TWILIO_ACCOUNT_SID}
      TWILIO_AUTH_TOKEN: ${TWILIO_AUTH_TOKEN}
    depends_on:
      redis:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 2G  # BERT model requires ~600MB
```

The existing `celery_worker` service processes document tasks on the `default` queue. The new `compliance_worker` processes compliance tasks on the `compliance` queue. This separation prevents BERT model memory from bloating the existing document worker.

Celery task routing:
```python
# app/tasks/__init__.py — add task routing
celery_app.conf.task_routes = {
    "app.tasks.document_tasks.*": {"queue": "default"},
    "app.compliance.tasks.*": {"queue": "compliance"},
}
```

### Render Production Changes

| Service | Current | v2.0 Change |
|---------|---------|-------------|
| Backend (FastAPI) | 1x Render Web Service | Add: ELASTICSEARCH_URL, SENDGRID, TWILIO env vars; APScheduler runs in-process |
| Celery Worker | 1x Render Background Worker (document tasks) | Keep existing; add new compliance_worker Background Worker |
| PostgreSQL | Render Managed PostgreSQL | No change — new tables via Alembic migration |
| Redis | Render Managed Redis | No change |
| Elasticsearch | Not present | Add: Elastic Cloud (Basic tier, ~$16/month) OR Bonsai Elasticsearch on Heroku ($10/month) |

**Elasticsearch hosting recommendation:** Elastic Cloud Serverless (pay-per-use) or Bonsai.io (Heroku marketplace, $10/month for 125MB). For v2.0 scope (single tenant, <10K notices), Bonsai hobby tier is sufficient. Elastic Cloud preferred for production due to managed TLS, backups, and Kibana access.

### Vercel Frontend Changes

| Item | Change |
|------|--------|
| New env var | `NEXT_PUBLIC_WS_URL=wss://your-backend.onrender.com` |
| New routes | `/compliance/*` — standard Next.js App Router, no Vercel config needed |
| Dependencies | Add: `zustand`, `@tanstack/react-query`, `date-fns` (deadline display) |
| Build impact | Negligible — new pages are standard React Server/Client Components |
| WebSocket | Vercel frontend connects to Render backend WebSocket endpoint directly |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Compliance Database

**What goes wrong:** Creating a second PostgreSQL database (or separate schema) for compliance tables to "keep concerns separate."
**Why bad:** Breaks cross-entity queries (join notices to documents), duplicates auth logic, complicates migrations, requires connection pooling to two databases.
**Instead:** All tables in the same PostgreSQL database. Use `app.compliance.models.*` Python package boundary for code separation, not database-level isolation.

### Anti-Pattern 2: Elasticsearch as System of Record

**What goes wrong:** Writing notices directly to Elasticsearch first, treating PostgreSQL as a downstream sync.
**Why bad:** ES is not ACID-compliant. Audit trails require authoritative PostgreSQL timestamps. Compliance data requires the guarantees of a relational transaction.
**Instead:** Write to PostgreSQL always. ES is a search index only. Accept eventual consistency for search (max 30s lag).

### Anti-Pattern 3: Loading BERT in the FastAPI Request Thread

**What goes wrong:** Calling `bert_classifier.classify(text)` synchronously in a FastAPI route handler.
**Why bad:** BERT inference takes 200-500ms on CPU. Blocks the async event loop. Kills API response times across all endpoints.
**Instead:** Classification always happens in Celery tasks. API responds immediately with `notice_id` and `status=processing`. Frontend polls or receives WebSocket update when classification completes.

### Anti-Pattern 4: Storing Portal Credentials in Plaintext

**What goes wrong:** Saving GST portal username/password directly in `portal_credentials.credentials` VARCHAR column.
**Why bad:** Database breach exposes credentials to all government portals for all users.
**Instead:** Fernet encryption with key in environment variable. Decrypt in-memory only during portal calls. Never log decrypted credentials.

### Anti-Pattern 5: APScheduler as a Background Worker Process

**What goes wrong:** Running APScheduler as a separate `apscheduler_worker` Docker service for portal polling.
**Why bad:** Redundant process; APScheduler's async version integrates cleanly into FastAPI's lifespan; adds operational complexity.
**Instead:** APScheduler runs in the FastAPI process via `AsyncIOScheduler` + lifespan hook. It only fires Celery tasks — heavy work runs in workers. This is the established pattern for FastAPI + APScheduler + Celery.

### Anti-Pattern 6: Blocking WebSocket from Celery

**What goes wrong:** Celery task directly calling `await ws_manager.broadcast_to_user()`.
**Why bad:** Celery tasks run in sync worker processes (prefork pool). Cannot call async functions. Different process from the FastAPI WebSocket manager.
**Instead:** Celery task publishes to Redis pub/sub channel. A background asyncio coroutine in the FastAPI process subscribes and forwards to WebSocket connections.

---

## Scalability Considerations

| Concern | At v2.0 (1 tenant, <10K notices) | Future (multi-tenant, 100K+ notices) |
|---------|----------------------------------|---------------------------------------|
| Notice storage | Single PostgreSQL, fine | Partition `notices` by `user_id` + `created_at` |
| BERT inference | CPU inference in Celery worker | GPU instance or batch inference service |
| ES index | Single Bonsai instance | Dedicated Elastic Cloud cluster, separate notice/doc indices per tenant |
| Portal scraping | Single IP | Rotating proxies, distributed scraping workers |
| WebSocket | Single backend instance | Redis pub/sub already supports multi-instance fan-out |
| Notification volume | Celery with 2 workers | Dedicated notification microservice + SES/SNS |

---

## Build Order (Phase Dependencies)

```
Phase 1: Database Foundation
  ├─ Alembic migrations for 8 new compliance tables
  ├─ New UserRole values (compliance_head, legal_team, finance_team, auditor)
  └─ notice_document_links bridge table

Phase 2: Notice Ingestion (Manual) + Classification
  ├─ NoticeIngestionService (manual upload path)
  ├─ BERT classifier + spaCy NER (compliance/ml/)
  ├─ classify_and_extract_task (Celery)
  └─ /api/compliance/notices CRUD endpoints
  (Depends on: Phase 1)

Phase 3: Risk Scoring + Dashboard
  ├─ XGBoost risk scorer
  ├─ score_risk_task (Celery)
  ├─ compliance_statuses workflow
  └─ Frontend: /compliance/notices list + detail pages
  (Depends on: Phase 2)

Phase 4: Alert System + WebSocket
  ├─ NotificationService (SendGrid + Twilio + WebSocket)
  ├─ APScheduler setup in lifespan
  ├─ alert_rules + alerts tables
  └─ Frontend: WebSocket client + notification UI
  (Depends on: Phase 3)

Phase 5: Elasticsearch Integration
  ├─ ES index mapping creation
  ├─ ElasticsearchSyncService
  ├─ APScheduler sync job (30s)
  └─ Unified search endpoint
  (Depends on: Phase 3 — notices must exist to sync)

Phase 6: Government Portal Integration
  ├─ PortalClientService + per-portal clients
  ├─ portal_credentials table + encryption
  ├─ APScheduler portal polling job
  └─ /api/compliance/portals endpoints
  (Depends on: Phase 2 — needs ingestion pipeline ready)

Phase 7: Response Drafting + Approval Workflow
  ├─ ResponseDraftService (reuses existing LLMService)
  ├─ response_drafts table
  ├─ Approval workflow endpoints
  └─ Frontend: response drafting interface
  (Depends on: Phase 2, Phase 4 for notifications)

Phase 8: Regulations Library + Audit Reports
  ├─ regulations table + seed data
  ├─ Compliance reports endpoints
  ├─ Audit export (PDF/Excel)
  └─ Frontend: reports + regulations pages
  (Depends on: All prior phases)
```

---

## Sources

**Confidence assessment:**
- Database schema design: HIGH — based on direct analysis of existing models + established SQLAlchemy patterns
- Elasticsearch integration pattern: HIGH — sidecar index + polling sync is established pattern; ES client API stable
- APScheduler + FastAPI lifespan: HIGH — standard documented integration pattern; `AsyncIOScheduler` well-established
- Celery queue routing: HIGH — direct extension of existing `celery_app` config pattern observed in codebase
- WebSocket + Celery pub/sub bridge: HIGH — Redis pub/sub pattern for this exact problem is well-documented
- BERT/spaCy/XGBoost inference: MEDIUM — training data quality and model accuracy depend on labeled notice dataset (not yet acquired)
- Government portal APIs: MEDIUM — GST/IT/MCA APIs exist but have undocumented access restrictions; scraping fallbacks reduce risk
- Portal credential encryption: HIGH — Fernet from Python `cryptography` library is standard for this use case

*Architecture research completed: 2026-03-30*
