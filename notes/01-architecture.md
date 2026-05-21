# 01 · TAXSYNC ARCHITECTURE

> AI-powered document management + Indian-regulator compliance tracker.
> v2.1.1 · 502+ backend tests green.

## ★ Remember
- 3-tier service: web → API → DB
- Async work uses HTTP 202 + Celery
- Multi-tenant via PostgreSQL RLS
- JWT access + opaque refresh tokens
- Docker compose for the whole stack

---

## 1. What is TaxSync?

Multi-tenant SaaS that ingests documents (PDF, image, DOCX), runs **OCR + ML classification**, then layers a **4-stage compliance approval workflow** for Indian regulatory notices (GST · IT · MCA · RBI · SEBI).

```
USER ─► UPLOAD ─► OCR ─► CLASSIFY ─► STORE
                                  ▼
                          SEARCH / WORKFLOW
                                  ▼
                  ALERTS · APPROVALS · REPORTS
```

Built for IIIT Hyderabad Production Labs. v1.0 shipped doc management; v2.0 added compliance; v2.1 added BYOK AI + per-tenant branding.

---

## 2. System diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Browser  (Next.js 15 · App Router · TanStack Query · Zustand)│
└──────────────┬──────────────────────────────────▲────────────┘
   REST + JWT  │                                  │ WebSocket
               ▼                                  │
┌─────────────────────────────────────────────────────────────┐
│            FastAPI Backend  (Uvicorn · Python 3.11)          │
│  Auth · Documents · ML · Admin · Compliance(14 routers)      │
│  Middleware: CORS → GZip → Sec-Headers → Logging → Tenant    │
└──────┬──────────────┬────────────────────────┬───────────────┘
       │              │                        │
       ▼              ▼                        ▼
  ┌─────────┐   ┌──────────┐         ┌───────────────────┐
  │ Postgres│   │  Redis   │ ◄─jobs─ │ Celery Workers ×2 │
  │ Supabase│   │  Broker  │         │ • default (OCR)   │
  │  + RLS  │   │  + cache │         │ • compliance (ML) │
  └─────────┘   └──────────┘         └───────────────────┘
```

---

## 3. Tech stack map

| Layer    | Tech                                                  |
|----------|--------------------------------------------------------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind             |
| State    | TanStack Query · Zustand                               |
| API      | FastAPI 0.120 · Pydantic v2                            |
| ORM      | SQLAlchemy 2.0 + Alembic                               |
| DB       | Postgres 16 (Supabase Cloud / local dev)               |
| Broker   | Redis 7                                                |
| Async    | Celery 5.3 · APScheduler                               |
| OCR      | Tesseract · pdfplumber · python-docx                   |
| ML       | LinearSVC + TF-IDF · BERT · XGBoost · SHAP             |
| LLM      | Anthropic · Gemini · OpenAI · Ollama · regex fallback  |
| Auth     | JWT(HS256) · bcrypt · OAuth (Google/Microsoft)         |

---

## 4. Request flow — synchronous

1. Browser → `POST /api/auth/login`
2. CORS → GZip → SecurityHeaders → Logging
3. TenantContext middleware parses `X-Client-Id` into ContextVars
4. FastAPI route resolves `Depends(get_db)`
5. SQLAlchemy `before_cursor_execute` listener executes
   `SET app.current_client_id = ?` + `SET ROLE app_runtime` per statement
6. PostgreSQL RLS policies filter rows for the tenant
7. Pydantic v2 schema serializes the response
8. Security headers attached on the way out

---

## 5. Request flow — asynchronous (upload)

```
Upload  ─►  HTTP 202  +  Celery enqueue
                        │
                        ▼
                  Redis broker queue
                        │
                        ▼
                Celery worker pulls
                        │
   ┌──────── stage 1 ───┴──── stage 2 ────────┐
   ▼                                          ▼
 OCR + extract                       Classify + LLM
   │                                          │
   └──────► UPDATE documents SET status='completed'
                        │
                        ▼
              Frontend polls task status
                or WebSocket push
```

Upload returns HTTP `202 Accepted` with a `celery_task_id`. The frontend polls or subscribes via WebSocket for status transitions: `PENDING → PROCESSING → COMPLETED / FAILED`.

---

## 6. Multi-tenancy model

- Shared schema, one DB
- Every tenant-scoped table has a `client_id` column
- Row isolation = PostgreSQL Row Level Security (RLS)
- Tenant resolved per-request via header `X-Client-Id`
- A `before_cursor_execute` listener pins SQL session vars BEFORE the route runs
- Cross-client mode `X-Client-Id: *` only allowed for senior roles (compliance_head, ca_consultant, cfo)
- No tenant header → fail-closed (zero rows returned)

---

## 7. Containers (docker-compose)

```
┌──────────────────────────────────┐
│ frontend       :3000  Next.js 15 │
│ backend        :8000  FastAPI    │
│ celery_worker   -     OCR queue  │
│ compliance_wkr  -     ML queue   │
│ redis          :6379  broker     │
│ db             :5432  pg local   │
└──────────────────────────────────┘
```

Production: `db` is swapped for **Supabase** (session-mode pooler), `frontend` ships to **Vercel**, `backend` runs on VPS/EC2.

---

## 8. Middleware stack

`backend/app/main.py` — order matters: LAST added = FIRST executed on requests.

1. `CORSMiddleware` (outermost — handles preflight)
2. `GZipMiddleware` (>= 1 KB)
3. `SecurityHeadersMiddleware`
4. `RequestLoggingMiddleware` (structlog)
5. `CorrelationIdMiddleware`
6. `TenantContextMiddleware` (innermost — resolves X-Client-Id into ContextVars)

---

## 9. Data stores

| Store      | What it holds                                   |
|------------|--------------------------------------------------|
| Postgres   | Users · Documents · Notices · Audit · FTS index  |
| Redis      | Celery broker + result backend · OAuth replay    |
| Local FS   | `/app/uploads` (docker named volume)             |
| S3 (opt)   | `documents.s3_url` via boto3                     |
| JSONL      | Audit dead-letter `/var/log/smartdocs/`          |
| HF Cache   | BERT weights `/app/models/hf_cache`              |

---

## 10. Version timeline

```
v1.0    Doc Mgmt          OCR · Classify · Search · 3-tier RBAC
v2.0    Compliance        7×12 RBAC matrix · RLS · 4-stage approval
        ├ Phase 9         Foundation + RLS + audit-trigger
        ├ Phase 10        ML risk scoring + auto-escalation
        ├ Phase 11        APScheduler alerts · 37 deadlines · WebSocket
        ├ Phase 12        Drafter → Reviewer → Legal → CFO
        └ Phase 13        Cross-entity FTS + analytics
v2.0.1  Patch             CSV export · notice upload pipeline
v2.1    BYOK AI           Per-tenant Anthropic/Gemini keys
        Phase 15          Gmail MCP integration
        Branding          logo · website · address
v2.1.1  IA reset          19→14 sidebar · Profile section · perf fix
```

---

## 11. Key architectural decisions

| Decision | Why |
|----------|-----|
| Shared DB + RLS (not DB-per-tenant) | Cheaper at scale; one migration set; less ops |
| Session-mode Supabase pooler | RLS context vars don't survive transaction pooling |
| `before_cursor_execute` listener | `set_config` + `SET ROLE` are tx-local; rebind per statement |
| Two Celery queues | Heavy ML never starves v1.0 OCR; 2 GB cap on ML worker |
| BYOK LLM | Costs hit tenant's provider account; TaxSync never bills |
| Audit immutability via DB trigger | Defense in depth — even compromised app role can't tamper |
| Soft-delete users only | Audit-log trigger forbids hard removal |

---

> "Multi-tenant SaaS is fundamentally a `WHERE client_id = ?` problem.
> RLS just moves that WHERE from your app code to the database."
