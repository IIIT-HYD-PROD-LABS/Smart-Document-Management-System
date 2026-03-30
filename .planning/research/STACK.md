# Technology Stack — v2.0 Compliance Management Additions

**Project:** Smart Document Management & Compliance System
**Researched:** 2026-03-30
**Scope:** NEW additions only for compliance management milestone. Do NOT re-research the existing stack.
**Existing Stack (do not modify):** FastAPI 0.104.1, SQLAlchemy 2.0.23, PostgreSQL, Celery 5.3.6, Redis, Next.js 15 (package.json shows 15.5.14), React 19, TypeScript, Tailwind CSS, scikit-learn, Tesseract OCR, pdfplumber, OpenCV, Docker, Render (backend), Vercel (frontend)

> **Version Note:** All versions are from training data through August 2025. Where marked `[verify]`, confirm the latest stable on PyPI/npm before pinning. Architecture choices are stable regardless of minor version drift.

---

## What Already Exists (Do Not Re-Install)

The following are in `backend/requirements.txt` and satisfy partial needs for compliance features:

| Already installed | Relevant to compliance |
|---|---|
| `spacy` (was researched for v1 but NOT in requirements.txt — needs adding) | NER extraction |
| `openai==1.86.0`, `anthropic==0.52.0` | AI response drafting |
| `celery==5.3.6` + `redis==5.0.1` | Async compliance checks |
| `httpx==0.25.2` | Government portal HTTP calls |
| `structlog==25.5.0` | Audit logging |
| `sqlalchemy==2.0.23` + `alembic==1.18.4` | Schema migrations |
| `pdfplumber==0.10.3` + `pytesseract` + `opencv` | Scanned notice OCR |

The frontend (`package.json`) has `next==15.5.14`, `react==19.0.0` — neither Zustand nor React Query are installed yet.

---

## Recommended New Stack — Backend

### ML: Notice Classification

#### transformers (HuggingFace)

- **Package:** `transformers==4.41.2` `[verify latest 4.x]`
- **Companion:** `torch==2.3.0` (CPU-only build: `torch==2.3.0+cpu` from PyTorch index) `[verify]`
- **Why:** BERT fine-tuning requires the `transformers` library. `bert-base-uncased` (110M params, ~420MB) is the recommended base because it handles mixed-case regulatory text well. For Indian legal vocabulary, consider `ai4bharat/indic-bert` or `nlpaueb/legal-bert-base-uncased` as the base — both are fine-tunable on Indian regulatory notice text.
- **Why not GPT-2/LLM APIs for classification:** Classification is a discriminative task — fine-tuned BERT consistently outperforms generative LLMs for 6-class categorical outputs at 1/10th the inference cost. The existing LLM fallback chain (OpenAI/Anthropic) is the right place for generative response drafting, not classification.
- **Render deployment constraint:** Render's standard instance has 512MB RAM. A fine-tuned BERT model in CPU inference mode needs ~900MB peak. Use Render's **Standard** tier (2GB RAM, $25/month) for the backend service. Docker Compose `memory: 1G` limit on the Celery worker must be raised to `2G` for the ML worker.
- **Confidence:** HIGH (transformers library is the de-facto standard; version needs verification)

```
# In a separate ml_compliance_worker or raise Celery worker memory to 2G
transformers==4.41.2
torch==2.3.0+cpu  # CPU-only; saves ~1.5GB vs CUDA build on Render
```

#### datasets (HuggingFace)

- **Package:** `datasets==2.19.0` `[verify]`
- **Why:** Required for fine-tuning pipeline. Handles tokenization, batching, and train/eval splits for your labeled Indian notice dataset (5,000+ examples across 6 categories). Far easier than writing custom PyTorch Dataset classes.
- **Confidence:** HIGH

#### scikit-learn (already installed)

- No version change needed. Use existing `scikit-learn==1.6.1` for the XGBoost pipeline preprocessing (label encoding, StandardScaler) and for evaluation metrics on the BERT classifier.
- **Confidence:** HIGH

---

### ML: NER Extraction

#### spaCy + custom NER model

- **Package:** `spacy==3.7.4` `[verify latest 3.x]`
- **English model:** `en_core_web_trf` (transformer-based, 500MB, best accuracy) OR `en_core_web_lg` (CNN-based, 560MB, faster, no GPU needed — preferred for Render CPU)
- **Why:** spaCy's NER pipeline is the right tool for extracting notice numbers, dates, authorities, deadlines, penalty amounts, and legal section citations from structured Indian regulatory text. The entities needed (DATE, MONEY, ORG, LAW, CARDINAL) map directly to spaCy entity types. Custom NER components can be trained on top of the base model to handle Indian regulatory vocabulary (e.g., GSTIN, PAN, DIN, CIN).
- **Why not re-use the LLM for NER:** LLM extraction (already in `llm_service.py`) is too slow (2-8s per call) and too expensive at scale. spaCy NER runs in <50ms locally, producing structured outputs without API costs. Reserve LLMs for response drafting.
- **Integration point:** Extend existing `app/ml/metadata_extractor.py` with a `compliance_ner.py` module in `app/ml/`. Reuse the same Celery task architecture from `document_tasks.py`.
- **Confidence:** HIGH

```
spacy==3.7.4
# Download model in Dockerfile:
# python -m spacy download en_core_web_lg
```

---

### ML: Risk Scoring

#### xgboost

- **Package:** `xgboost==2.0.3` `[verify latest 2.x]`
- **Why:** XGBoost is the right tool for tabular risk scoring where features are structured (penalty_amount, days_to_deadline, authority_type, prior_violations, notice_severity). It handles mixed feature types (numeric + categorical), produces calibrated probability scores, is fast in inference (microseconds), and is small (no GPU needed, ~50MB installed). The model is interpretable — SHAP values explain why a notice is high-risk, which is required for compliance audit trails.
- **Why not a neural network:** Risk scoring uses tabular features, not text. Neural networks don't outperform gradient boosted trees on tabular data (See: "Why do tree-based models still outperform deep learning on tabular data?" — Grinsztajn et al., 2022). XGBoost is production-proven for exactly this use case.
- **Companion:** `shap==0.45.0` `[verify]` — for risk score explanation (required for auditor reports)
- **Confidence:** HIGH

```
xgboost==2.0.3
shap==0.45.0
```

---

### Search: Elasticsearch Integration

#### elasticsearch-py (official client)

- **Package:** `elasticsearch==8.13.0` `[verify latest 8.x]`
- **Why:** The compliance milestone adds a second searchable corpus (notices) alongside existing documents. PostgreSQL FTS (already in production) handles document search well. Elasticsearch adds: (1) cross-index queries across documents AND notices in a single call, (2) field-level boosting (penalty_amount, deadline get higher relevance weight), (3) aggregations for compliance dashboard facets (by authority, status, risk level). Use Elasticsearch 8.x with the official Python client.
- **Why not expand PostgreSQL FTS for compliance:** PostgreSQL FTS works but lacks aggregation pipelines needed for compliance dashboards. More critically, running Elasticsearch alongside PostgreSQL avoids rewriting the working v1.0 document search.
- **Deployment:** Add Elasticsearch as a new service. Options:
  - **Elastic Cloud** (recommended for Render deployment): Managed, 14-day free trial, then ~$16/month for 1GB. No Docker Compose changes needed.
  - **Self-hosted in Docker Compose:** `docker.elastic.co/elasticsearch/elasticsearch:8.13.0` with `ES_JAVA_OPTS=-Xms512m -Xmx512m` (512MB heap). Adds ~700MB memory to local dev.
- **Sync strategy:** Use a Celery Beat task to sync PostgreSQL notice records to Elasticsearch on upsert. Do NOT use dual-write in the HTTP request path (latency). Eventual consistency (sync delay <30s) is acceptable for compliance search.
- **Confidence:** MEDIUM (Elasticsearch 8 client is stable; deployment complexity on Render needs validation)

```
elasticsearch==8.13.0
```

---

### Scheduling: Periodic Compliance Checks

#### APScheduler

- **Package:** `apscheduler==3.10.4` `[verify latest 3.x]`
- **Why:** APScheduler integrates cleanly into the existing FastAPI + Celery architecture. Use it for: periodic government portal polling (every 6 hours), deadline reminder triggers (daily at 8am IST), compliance health score recalculation (daily), Elasticsearch sync jobs. APScheduler 3.x supports `AsyncIOScheduler` for FastAPI's async context and can dispatch to Celery tasks (best of both: schedule in APScheduler, execute in Celery).
- **Why not Celery Beat alone:** Celery Beat works for periodic tasks but requires a separate Beat process. APScheduler runs inside the FastAPI process for lightweight cron-like scheduling, dispatching to Celery only for heavy work. This avoids an extra Docker service.
- **Integration point:** Initialize scheduler in `app/main.py` on startup event. Add scheduler module at `app/scheduler.py`.
- **Confidence:** HIGH

```
apscheduler==3.10.4
```

---

### Real-Time: WebSocket Notifications

#### FastAPI native WebSocket (no new package)

- **Why:** FastAPI has built-in WebSocket support via Starlette's `WebSocket` class. No extra package needed. Use Redis pub/sub (already installed) as the message broker between Celery tasks and WebSocket connections: when a new notice arrives or a deadline approaches, the Celery task publishes to a Redis channel; a WebSocket connection manager subscribes and pushes to connected clients.
- **Pattern:**
  ```
  Celery task → redis.publish("notifications:{user_id}", payload)
  FastAPI WS endpoint → redis.subscribe("notifications:{user_id}") → ws.send_json()
  ```
- **Integration point:** Add `app/routers/notifications.py` with WebSocket endpoint. Add `app/services/notification_service.py` with connection manager. Use existing `redis==5.0.1` with async Redis client.
- **Async Redis client:** `redis==5.0.1` already installed supports async via `aioredis`-style interface. No new package needed.
- **Confidence:** HIGH (FastAPI WebSocket + Redis pub/sub is the standard pattern; no new dependencies)

---

### Email: SendGrid

- **Package:** `sendgrid==6.11.0` `[verify latest 6.x]`
- **Why:** SendGrid is the industry standard for transactional email. Provides: template management for notice alerts, delivery tracking, bounce handling, and 100 free emails/day (sufficient for early usage). The Python SDK wraps the v3 Mail Send API with retry logic built-in.
- **Alternative considered:** `python-mailjet-restapi` — rejected because SendGrid has better deliverability for Indian email servers and is the client's stated preference (PROJECT.md).
- **Integration point:** Add `app/services/email_service.py`. Trigger via Celery tasks for deadline reminders (async delivery, non-blocking).
- **Confidence:** HIGH

```
sendgrid==6.11.0
```

---

### SMS: Twilio

- **Package:** `twilio==9.0.4` `[verify latest 9.x]`
- **Why:** Twilio is the specified SMS provider. The Python helper library wraps the REST API with auth, retry, and error handling. SMS is used only for critical/high-risk notice alerts — low volume, so Twilio's pay-per-SMS model (₹0.75/SMS in India) fits the use case.
- **Alternative considered:** MSG91 (Indian provider, cheaper for India) — valid alternative if Twilio costs become prohibitive at scale.
- **Integration point:** Add to `app/services/notification_service.py`. Trigger via Celery tasks only (never in-request-path due to Twilio API latency of 1-3s).
- **Confidence:** HIGH

```
twilio==9.0.4
```

---

### Web Scraping: RBI/SEBI Notices

#### httpx + BeautifulSoup4

- **httpx:** Already installed (`httpx==0.25.2`). Use for async HTTP requests to RBI/SEBI websites.
- **BeautifulSoup4:** `beautifulsoup4==4.12.3` `[verify]` + `lxml==5.2.0` `[verify]` (faster HTML parser)
- **Why:** RBI and SEBI don't provide official notice APIs. Web scraping is the only option. BeautifulSoup4 + lxml is the standard Python scraping stack — lightweight, no JavaScript rendering needed (RBI/SEBI notice pages are server-rendered HTML).
- **Why not Scrapy:** Overkill for 2 target sites. Scrapy's async spider framework adds unnecessary complexity. httpx + BeautifulSoup in a Celery task is sufficient.
- **Why not Playwright/Selenium:** RBI/SEBI notice listing pages don't require JavaScript. If this assumption is wrong during implementation, add `playwright==1.44.0` then.
- **Scraping schedule:** Celery Beat task every 6 hours. Add retry with exponential backoff (httpx already supports this). Cache last-seen notice ID to avoid re-processing.
- **Confidence:** MEDIUM (scraping works; RBI/SEBI could change their HTML structure — build with resilient selectors and add monitoring)

```
beautifulsoup4==4.12.3
lxml==5.2.0
```

---

### Government Portal APIs

#### No new package — use existing httpx

- **GST Portal API:** The GSTN (Goods and Services Tax Network) provides APIs for taxpayer verification and notice retrieval. Authentication uses OTP-based or API key flows. Use `httpx==0.25.2` (already installed) for all HTTP calls. Add a `app/services/portal_integrations/gst_portal.py` service.
- **Income Tax e-filing API:** Available via the IT department's B2B integration. Uses OAuth 2.0. The `authlib` library (already researched, add if not present) handles OAuth flows. Add `app/services/portal_integrations/it_portal.py`.
- **MCA API:** Ministry of Corporate Affairs provides REST APIs for company data. Similar OAuth pattern.
- **Critical caveat:** Government portal APIs in India have inconsistent uptime and undocumented rate limits. Build every portal integration with: circuit breaker pattern, exponential backoff, graceful degradation (manual upload always works), and comprehensive error logging. Do NOT make portal availability a hard requirement for compliance tracking to function.
- **Confidence:** LOW for API availability/stability (Indian government APIs are notoriously unreliable — this is a known risk flagged in PROJECT.md). Architecture is sound; specific API behavior needs validation during implementation.

---

### Additional Backend Utilities

#### dateparser

- **Package:** `dateparser==1.2.0` `[verify]`
- **Why:** Indian regulatory notices use varied date formats: "15th March 2024", "15/03/2024", "March 15, 2024", "within 30 days of issue". `dateparser` handles all of these. Better than `python-dateutil` for natural language dates. Critical for deadline extraction.
- **Confidence:** HIGH

```
dateparser==1.2.0
```

#### python-jose (JWT — already have PyJWT)

- No new package. Extended RBAC (Compliance Head, Legal Team, Finance Team, Auditor) uses existing JWT infrastructure. Add new role values to the existing `UserRole` enum. No new auth library needed.

---

## Recommended New Stack — Frontend

### State Management: Zustand

- **Package:** `zustand@^4.5.2` `[verify latest 4.x]`
- **Why:** Zustand is the correct choice for compliance management UI state (active filters, selected notices, notification panel state, multi-GSTIN selection). It's 1KB gzipped, has zero boilerplate compared to Redux, and integrates cleanly with React 19. The existing frontend uses no global state management — all state is component-local or via context. Zustand fills this gap without overengineering.
- **Why not Redux Toolkit:** Redux Toolkit is appropriate for enterprise apps with complex state graphs. The compliance dashboard has moderate state complexity — Zustand is sufficient and far less configuration overhead.
- **Confidence:** HIGH

```json
"zustand": "^4.5.2"
```

### Server State: TanStack Query (React Query)

- **Package:** `@tanstack/react-query@^5.40.0` `[verify latest 5.x]`
- **Why:** The compliance dashboard makes many concurrent API calls (notices list, risk scores, deadline calendar, notification feed). React Query handles caching, background refetching, optimistic updates, and stale-while-revalidate automatically. Currently the frontend uses raw `axios` calls with manual loading/error state — this works for the document management use case but breaks down for the compliance dashboard's real-time data requirements (multiple polls, WebSocket updates invalidating cached queries).
- **Integration note:** Keep existing `axios` instance (`frontend/src/lib/api.ts`) as the underlying HTTP client. Wrap it in React Query's `queryFn`. Do not replace axios — it handles JWT interceptors that need to stay.
- **Confidence:** HIGH

```json
"@tanstack/react-query": "^5.40.0"
```

### WebSocket Client

- **No new package.** Use the browser's native `WebSocket` API. Create a `useNotifications` hook in `frontend/src/hooks/useNotifications.ts` that wraps the WebSocket connection with reconnection logic. React Query's `queryClient.invalidateQueries()` can be triggered from the WebSocket message handler to refresh affected data.
- **Confidence:** HIGH

### Calendar: react-big-calendar

- **Package:** `react-big-calendar@^1.13.1` `[verify latest 1.x]`
- **Why:** Compliance calendar view (statutory deadlines, notice deadlines, custom reminders) requires a full calendar component. `react-big-calendar` is the most capable React calendar library, supports month/week/day views, event click handling, and custom event rendering. Needed for the compliance calendar feature (pre-loaded statutory deadlines + notice-specific deadlines).
- **Companion:** `moment@^2.30.1` or `date-fns` (already installed) as the localizer.
- **Confidence:** HIGH

```json
"react-big-calendar": "^1.13.1"
```

### Data Tables: @tanstack/react-table

- **Package:** `@tanstack/react-table@^8.17.0` `[verify latest 8.x]`
- **Why:** The compliance notices table needs: sorting by risk score/deadline/authority, column filtering, row selection (bulk status update), pagination, and expandable rows (show notice details inline). `@tanstack/react-table` is a headless table library that handles all of this with full TypeScript support and Tailwind CSS styling.
- **Confidence:** HIGH

```json
"@tanstack/react-table": "^8.17.0"
```

### Charts: recharts (already installed)

- No new package. `recharts@^2.12.7` is already installed and sufficient for compliance analytics dashboards (bar charts for authority distribution, line charts for response time trends, pie charts for compliance status breakdown).

### PDF/Document Preview

- **Already installed:** `react-pdf@^10.4.1` in `package.json`. No new package needed.

---

## Infrastructure Changes

### Memory Limits

The current Docker Compose memory limits must increase for ML workloads:

| Service | Current Limit | Required v2.0 | Reason |
|---|---|---|---|
| `backend` | 1G | 1G | No change (API only) |
| `celery_worker` | 1G | 2G | BERT model (~900MB) + XGBoost + spaCy model (~560MB) cannot share one 1G worker. Split into two workers (see below). |

**Recommended: Split Celery workers**

```yaml
# docker-compose.yml
celery_worker_default:
  # Handles document tasks (existing), notification dispatch, portal polling
  command: celery -A app.tasks.celery_app worker -Q default --concurrency=2 --max-memory-per-child=512000
  deploy:
    resources:
      limits:
        memory: 1G

celery_worker_ml:
  # Handles BERT inference, spaCy NER, XGBoost scoring
  command: celery -A app.tasks.celery_app worker -Q ml_tasks --concurrency=1 --max-memory-per-child=1800000
  deploy:
    resources:
      limits:
        memory: 2G
```

This prevents BERT model loading from consuming the memory needed for document processing tasks.

### Elasticsearch Service

Add to `docker-compose.yml` for local development:

```yaml
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
  environment:
    - discovery.type=single-node
    - ES_JAVA_OPTS=-Xms512m -Xmx512m
    - xpack.security.enabled=false  # dev only; enable in production
  ports:
    - "9200:9200"
  deploy:
    resources:
      limits:
        memory: 1G
```

For Render production: Use **Elastic Cloud** (managed) rather than self-hosted. Single-node on a free/starter Elastic Cloud cluster avoids Render instance size increases.

### Render Deployment

The existing Render backend service needs a memory upgrade. Currently running on what appears to be a standard instance. To support BERT inference in the ML worker:

- **Celery ML worker:** Render **Standard** instance (2GB RAM, $25/month) or separate **Background Worker** service
- **Celery default worker + FastAPI backend:** Can stay on existing instance
- **Elasticsearch:** Elastic Cloud Starter tier (~$16/month) or Elastic's free tier (14-day trial then paid)

---

## Complete New Dependency List

### Backend additions to `requirements.txt`

```
# ── ML: Notice Classification (BERT) ───────────────────────────
transformers==4.41.2
torch==2.3.0+cpu           # CPU-only build; saves 1.5GB over CUDA
datasets==2.19.0

# ── ML: NER Extraction ─────────────────────────────────────────
spacy==3.7.4
# Run in Dockerfile: python -m spacy download en_core_web_lg

# ── ML: Risk Scoring ───────────────────────────────────────────
xgboost==2.0.3
shap==0.45.0               # Risk score explainability for auditor reports

# ── Search: Elasticsearch ──────────────────────────────────────
elasticsearch==8.13.0

# ── Scheduling ─────────────────────────────────────────────────
apscheduler==3.10.4

# ── Notifications: Email ───────────────────────────────────────
sendgrid==6.11.0

# ── Notifications: SMS ─────────────────────────────────────────
twilio==9.0.4

# ── Web Scraping (RBI/SEBI) ────────────────────────────────────
beautifulsoup4==4.12.3
lxml==5.2.0

# ── Date Parsing (notice deadlines) ───────────────────────────
dateparser==1.2.0
```

### Frontend additions to `package.json`

```json
{
  "dependencies": {
    "zustand": "^4.5.2",
    "@tanstack/react-query": "^5.40.0",
    "@tanstack/react-table": "^8.17.0",
    "react-big-calendar": "^1.13.1"
  }
}
```

---

## Alternatives Considered

| Category | Recommended | Alternative Rejected | Why Rejected |
|---|---|---|---|
| Notice classification | BERT fine-tune (transformers) | scikit-learn TF-IDF + SVC (existing) | Existing classifier hits 85% accuracy ceiling on legal text; 92%+ target requires contextual embeddings, not bag-of-words |
| Notice classification | BERT fine-tune | GPT-4 via API for classification | Generative LLMs are slower (2-5s vs 50ms) and 50x more expensive per classification; discriminative BERT is correct for this task |
| NER | spaCy | Regex patterns | Regex breaks on format variation. Indian regulatory notices have no fixed template — NER is required |
| NER | spaCy | LLM NER via prompt | Too slow (2-8s) and expensive at scale. spaCy NER runs in <50ms locally |
| Risk scoring | XGBoost | Neural network | Tabular feature input; tree-based models outperform NNs on tabular data; XGBoost wins on interpretability (required for audit) |
| Cross-system search | Elasticsearch | Extend PostgreSQL FTS | PostgreSQL FTS lacks aggregation pipelines needed for compliance dashboard facets; cross-index queries simpler in Elasticsearch |
| Cross-system search | Elasticsearch | Meilisearch / Typesense | These are optimized for instant search UX, not compliance analytics aggregations; Elasticsearch aggregation API is better fit |
| Scheduling | APScheduler | Celery Beat alone | Beat requires a separate process; APScheduler runs inside FastAPI and dispatches heavy work to Celery — fewer Docker services |
| WebSocket | No new package (native + Redis pub/sub) | django-channels / socket.io | Overkill; FastAPI has native WebSocket support; Redis pub/sub is already in the stack |
| Email | SendGrid | AWS SES | SendGrid has better deliverability to Indian email servers and simpler template management; SES requires Route 53 domain verification complexity |
| SMS | Twilio | MSG91 (Indian provider) | Twilio is the stated client preference; MSG91 is a valid future alternative if cost is an issue |
| Web scraping | httpx + BeautifulSoup4 | Scrapy | Scrapy adds a full spider framework for 2 target sites; httpx + BeautifulSoup in Celery tasks is proportional to the problem |
| Web scraping | httpx + BeautifulSoup4 | Playwright | RBI/SEBI notice pages are server-rendered HTML; Playwright is needed only if JavaScript rendering is required (evaluate during Phase 1) |
| Frontend state | Zustand | Redux Toolkit | Redux Toolkit is appropriate for large state graphs; compliance dashboard has moderate complexity; Zustand is proportional |
| Frontend state | Zustand | React Context + useReducer | Context causes unnecessary re-renders across the compliance dashboard; Zustand's granular subscriptions are better for large tables |

---

## Explicit Exclusions

| Technology | Reason Not Used |
|---|---|
| `sentence-transformers` / pgvector for notice search | Elasticsearch handles cross-system search better for compliance analytics; semantic vector search is a v3 feature |
| `celery-beat` as a separate service | APScheduler runs inside FastAPI; heavy tasks dispatched to Celery. Avoid extra Docker services. |
| `langchain` for notice classification | LangChain adds abstraction overhead for classification; transformers direct API is sufficient and faster |
| `playwright` / `selenium` for web scraping | Government notice pages are server-rendered HTML; add only if JavaScript rendering is needed |
| `fastapi-websocket-pubsub` | Third-party WebSocket pub/sub library; unnecessary — Redis pub/sub + native FastAPI WebSocket is the simpler equivalent |
| `firebase` / Pusher for real-time | External real-time services; Redis pub/sub + native WS avoids vendor lock-in and additional cost |
| `pandas-ta` / financial calculation libraries | XGBoost handles feature engineering from structured fields; no time-series analysis needed at this stage |
| GraphQL | REST is sufficient; adding GraphQL for compliance queries adds implementation overhead with no clear benefit |
| Kubernetes / Helm | Docker Compose is sufficient for v2.0 scope; K8s deferred per PROJECT.md |

---

## Integration Points with Existing Stack

| New Component | Integrates With | Integration Method |
|---|---|---|
| BERT classifier | Celery `ml_tasks` queue | New task `classify_notice_task()` in `app/tasks/compliance_tasks.py`; same pattern as `process_document_task` |
| spaCy NER | `app/ml/` module | New `app/ml/compliance_ner.py`; called from `classify_notice_task` |
| XGBoost risk scoring | PostgreSQL compliance notices table | `app/services/risk_scoring_service.py`; called after NER extraction populates features |
| Elasticsearch | PostgreSQL (source of truth) | Celery Beat sync task; writes to ES index, PostgreSQL remains authoritative |
| APScheduler | FastAPI `app/main.py` | Initialize in `lifespan` context manager (startup/shutdown); dispatches to Celery |
| WebSocket | Redis pub/sub + FastAPI | `app/routers/notifications.py`; connection manager in `app/services/notification_service.py` |
| SendGrid / Twilio | Celery tasks | Called from `app/tasks/alert_tasks.py`; never in HTTP request path |
| Zustand | React components | Global store at `frontend/src/store/`; compliance UI state only (filters, selections) |
| React Query | Existing axios client | Wrap `api.ts` axios instance in `queryFn`; keep JWT interceptors on axios |
| React Big Calendar | PostgreSQL compliance calendar table | React Query fetches events; rendered in calendar component |

---

## Deployment Compatibility

### Render (Backend)

| Component | Render Impact | Mitigation |
|---|---|---|
| BERT model (~420MB) + PyTorch (~800MB installed) | Requires 2GB+ RAM instance | Use separate Render Background Worker for ML Celery queue; Standard tier ($25/mo) |
| spaCy `en_core_web_lg` (~560MB) | Included in ML worker RAM budget above | Download in Dockerfile; cache in model volume |
| Elasticsearch | Not self-hosted on Render | Use Elastic Cloud Starter (~$16/mo); add `ELASTICSEARCH_URL` env var |
| APScheduler | Runs inside FastAPI process | No extra service; fits within existing backend instance |
| WebSocket | Render supports persistent connections | No change needed; Render's HTTP/2 infrastructure handles WS |

### Vercel (Frontend)

| Component | Vercel Impact | Notes |
|---|---|---|
| Zustand | None | Client-side bundle; no SSR concerns |
| React Query | None | Standard server state pattern; works with Next.js App Router |
| React Big Calendar | Bundle size ~150KB gzipped | Acceptable; lazy-load the calendar component |
| WebSocket client | None | Native browser API; no Vercel configuration needed |

---

## Sources

- HuggingFace `transformers` library: https://huggingface.co/docs/transformers
- spaCy NER documentation: https://spacy.io/usage/training (training custom NER)
- XGBoost documentation: https://xgboost.readthedocs.io/en/stable/
- Elasticsearch Python client: https://www.elastic.co/guide/en/elasticsearch/client/python-api/current/index.html
- APScheduler documentation: https://apscheduler.readthedocs.io/en/stable/
- FastAPI WebSocket: https://fastapi.tiangolo.com/advanced/websockets/
- SendGrid Python library: https://github.com/sendgrid/sendgrid-python
- Twilio Python library: https://www.twilio.com/docs/libraries/python
- Zustand documentation: https://docs.pmnd.rs/zustand/getting-started/introduction
- TanStack Query v5: https://tanstack.com/query/v5/docs/framework/react/overview
- Grinsztajn et al. (2022) "Why tree-based models still outperform deep learning on tabular data" — NeurIPS 2022 (XGBoost over NNs for tabular risk scoring)

**Confidence levels:**
- BERT/transformers, spaCy, XGBoost, APScheduler, Zustand, React Query: **HIGH** — stable, widely-used libraries with clear integration paths
- Elasticsearch deployment on Render: **MEDIUM** — Elastic Cloud approach is sound; Render self-hosting is not recommended
- Government portal APIs (GST, IT, MCA): **LOW** — APIs exist but Indian government APIs have undocumented rate limits, inconsistent uptime, and may require separate registration/approval

---

*Stack research completed: 2026-03-30*
*Scope: v2.0 compliance management additions only*
