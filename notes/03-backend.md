# 03 · BACKEND

> FastAPI 0.120 · Pydantic v2 · SQLAlchemy 2.0 · Celery 5.3 · Uvicorn · Python 3.11

## ★ Remember
- Routers thin, services thick
- DI everywhere — `Depends(get_db)`, `Depends(get_current_user)`
- Async work goes through Celery, never blocks request thread
- `structlog` everywhere — correlation-id via `asgi-correlation-id`
- RBAC at the route layer, RLS at the DB layer

---

## 1. Entry point (`backend/app/main.py`)

```python
app = FastAPI(
    title=APP_NAME, version=APP_VERSION,
    docs_url="/docs" if DEBUG else None,
    lifespan=lifespan,
)

app.state.limiter = limiter   # slowapi

# middleware — LAST added = FIRST executed
add_middleware(CORSMiddleware)
add_middleware(GZipMiddleware, minimum_size=1000)
add_middleware(SecurityHeadersMiddleware)
add_middleware(RequestLoggingMiddleware)
add_middleware(CorrelationIdMiddleware)
add_middleware(TenantContextMiddleware)

# routers
include_router(auth, documents, ml, admin, early_access)
include_router(... prefix="/api/compliance")  # × 14
include_router(... prefix="/api/email")        # × 6
```

---

## 2. 3-layer structure

```
ROUTER  (app/routers/*.py · app/compliance/routers/*)
   │  thin: validate, authorize, call service
   ▼
SERVICE (app/services/*.py · app/compliance/services/*)
   │  business logic, state machines, transactions
   ▼
MODEL   (app/models/*.py · app/compliance/models/*)
   │  SQLAlchemy ORM tables + relationships
   ▼
DATABASE (Postgres / Supabase)
       RLS policies · audit triggers · FTS triggers

SCHEMA  (app/schemas/*.py) — Pydantic v2 IN/OUT DTOs
```

Routers never query the DB directly past simple reads — they call services that own the transaction boundary.

---

## 3. Routers — v1.0

| File              | Prefix                  |
|-------------------|-------------------------|
| `auth.py`         | `/api/auth`             |
| `documents.py`    | `/api/documents`        |
| `ml.py`           | `/api/ml`               |
| `admin.py`        | `/api/admin`            |
| `early_access.py` | `/api/early-access`     |

Plus root `GET /` and `GET /api/health` defined in `main.py`.

---

## 4. Routers — compliance (14)

All mount under `/api/compliance` and gate on the 7×12 permission matrix.

- `clients` — per-tenant CRUD + branding (logo, website, address)
- `memberships` — 7-role assignments
- `notices` — core notice CRUD + upload (reuses v1.0 OCR pipeline)
- `responses` — 4-stage approval drafts
- `reports` — CSV export of summary + analytics
- `audit` — immutable audit log read
- `review_queue` — low-confidence ML triage
- `alerts` — deadline alert schedules
- `calendar` — per-client deadlines
- `regulatory_calendar` — FY 25-26 seed deadlines (37 entries)
- `notifications` — WebSocket `/ws/notifications`
- `search` — cross-entity FTS (notices + documents)
- `notice_types` — taxonomy management
- `ai` — BYOK Phase 16 (summaries, recommended actions, payment timing)

---

## 5. Routers — email (Phase 15, Gmail MCP)

All under `/api/email`, gated on `EMAIL_INTEGRATION_USE`.

- `oauth` — Gmail OAuth dance
- `credentials` — Fernet-encrypted token storage
- `filter_rules` — "ingest if from .gov.in" etc.
- `activity` — ingestion log
- `bills` — vendor-invoice surface
- `view_email` — render raw email

MCP server registered via `import app.email.mcp.server` in the `lifespan()` handler.

---

## 6. Service layer

```
v1.0 services/
  audit_service        immutable append + dead-letter JSONL
  llm_service          multi-provider Ollama/Gemini/etc
  oauth_service        Google + Microsoft adapters
  storage_service      path-traversal-safe FS + S3

compliance/services/
  notice_service           create, transition, chain CTE
  notice_state_machine     6 states · explicit allowed-transitions
  response_state_machine   4-stage approval gate
  permission_registry      7×12 matrix · frozenset lookups
  evidence_service         attach Document → response_drafts
  alert_service            APScheduler add_job
  scheduler                durable jobstore on apscheduler_jobs
  unified_search_service   FTS across notices + documents
  ai_service               scope-locked SYSTEM prompt · 5 tasks
  ai_providers             Anthropic SDK · Gemini httpx REST
```

---

## 7. Schemas (Pydantic v2)

- Pydantic v2.13 (~5–50× faster than v1)
- Grouped by feature: `schemas/document.py`, `sharing.py`, `admin.py`, `audit.py`, `early_access.py`
- Compliance schemas under `compliance/schemas/`
- `model_validate(orm_object)` converts ORM → DTO

---

## 8. Dependency injection

```python
def route(
    request: Request,
    user = Depends(get_current_user),
    db   = Depends(get_db),
    perm = Depends(
        require_compliance_permission(Permission.NOTICE_VIEW)
    ),
): ...
```

DI composes: `get_db` opens a session, `get_current_user` decodes the JWT, `require_compliance_permission` checks the 7×12 matrix.

---

## 9. Celery — async workers

```python
celery_app = Celery(broker=REDIS, backend=REDIS)

# v1.0 default queue
process_document_task(document_id):
    read file → OCR → classify → update row
    stages: reading_file 10% → extracting_text 30%
            → classify 70% → completed 100%

# compliance queue (2 GB cap, hostname=compliance@%h)
classify_notice_task(notice_id):
    BERT classify → spaCy NER → risk_scorer
    → CalibratedClassifier confidence
    → if low confidence → review_queue
    → if critical tier  → auto-escalation + audit

alert_tasks/check_due:
    pulls APScheduler jobs near deadline,
    fires email + WebSocket push
```

---

## 10. Config & env

| Key | Purpose |
|-----|---------|
| `SECRET_KEY` | JWT signing (≥32 chars, ≥10 unique) |
| `DATABASE_URL` | Postgres / Supabase session-mode |
| `REDIS_URL` + `REDIS_PASSWORD` | Celery broker + cache |
| `LLM_PROVIDER` | local / ollama / gemini / anthropic / openai |
| `OLLAMA_BASE_URL` | `host.docker.internal:11434` |
| `GOOGLE_CLIENT_ID / SECRET` | Optional OAuth |
| `MICROSOFT_CLIENT_ID / SECRET` | Optional OAuth |
| `RATE_LIMIT_AUTH` | slowapi limit string |
| `AUDIT_FAILURES_PATH` | Dead-letter JSONL path |
| `MAX_FILE_SIZE_MB` | Upload cap |
| `DEBUG` | Toggles `/docs` + HSTS |

---

## 11. Error handling

- Global `Exception` handler → logs `unhandled_exception` + returns 500 generic body
- `RequestValidationError` → structured 422 with `loc/msg/type`
- `StarletteHTTPException` → echoes status + detail
- Service layer raises `HTTPException` with explicit codes (401/403/409/422/503)
- `structlog` emits correlation-id with every log line via `asgi-correlation-id`

---

## 12. Lifespan hooks

```python
@asynccontextmanager
async def lifespan(app):
    # On boot
    import app.email.mcp.server   # register FastMCP
    try:
        get_scheduler()           # APScheduler warm-up
    except InsufficientPrivilege:
        warn("scheduler_init_skipped")
    yield
    # On shutdown — APScheduler atexit closes it
```

Best-effort scheduler init: in dev the `app_runtime` role can't `CREATE TABLE`, so the scheduler lazy-binds on the first compliance request.

---

> "Routers are an HTTP boundary. Don't put business logic there.
> If a service has no test, it doesn't exist yet."

**When adding a feature:**
1. Model — SQLAlchemy class + Alembic revision
2. Schema — Pydantic IN/OUT DTOs
3. Service — business logic + tests first
4. Router — thin wrapper composing DI + service
5. Register — `include_router` in `main.py`
