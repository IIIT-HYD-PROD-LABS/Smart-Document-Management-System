TaxSync

**AI-powered document management + compliance tracking system** built for IIIT Hyderabad Production Labs. Upload any document — PDFs, scanned images, DOCX — and the system automatically extracts text via OCR, classifies it using machine learning, and makes it searchable. v2.0 layers a multi-tenant **compliance notice tracking** workflow on top: ingest GST/IT/MCA/RBI/SEBI notices, route through a 4-stage approval pipeline, fire deadline alerts, and export per-client compliance reports.

**Current status (2026-05-22):** v1.0 SHIPPED · v2.0 Phases 9-13 CODE-COMPLETE · v2.1 shipped · v2.1.1 IA reset · v2.1.2 production-readiness sweep · v2.1.3 compliance flow rewire (2026-05-21 PM) · **v2.1.4 admin shell + auth hardening shipped 2026-05-22**: unified `/dashboard/admin/` shell with secondary sidebar (Overview, Users, User detail, Early access, Audit log, AI provider, Organization, Security, Model eval). Auth hardening closed two CRITICAL findings: (1) `POST /api/auth/register` now requires a single-use early-access invitation JWT after the bootstrap admin (closing the public-register bypass that made the early-access gate decorative), (2) first-user admin promotion is wrapped in a Postgres advisory lock so concurrent register or OAuth callbacks cannot both insert as admin (closing the count-then-insert race at three call sites). Plus four HIGH/MED follow-ups: `accept-invite` now uses a typed `AcceptInviteRequest` schema, JWT invitation tokens removed from API responses, `/api/auth/oauth/diag` admin-gated outside DEBUG, and `is_active` filter added to the admin-promotion count. Compliance defense-in-depth: `GET /notices/{id}` and `GET /review/{id}` now apply an explicit `client_id` filter on top of RLS. Frontend perf: dashboard stats wrapped in React Query (60s stale), analytics dual-fetch wrapped (5min stale), recharts lazy-loaded via dynamic import, soft logout via `auth:session-expired` custom event removes the full-page reload on token refresh failure. 414 backend tests pass. **v2.1.3 compliance flow rewire shipped 2026-05-21 (PM)**: admin-only client creation, email-based team invite flow (pre-creates a pending User and emails a 7-day signed JWT, invitee sets password on `/accept-invite` and is signed-in), dedicated `POST /notices/{id}/assign` endpoint with a real-time WebSocket notification to the assignee (via the `notifications:{client_id}` Redis pubsub channel), the review queue is no longer empty by design: `rule_based_heuristic_v1` synthesises authority + type confidences from the ner extractor output today (BERT in v2.1 takes over automatically when it lands), and a new `POST /api/compliance/review/manual-enqueue/{notice_id}` endpoint lets any active member flag a notice they think the classifier got wrong. Compliance review page redesigned as a triage workbench: sticky filter strip with reason buckets, card grid with segmented confidence dots and a 75 percent threshold marker, Confirm / Re-classify / Open actions per card, manual-flag form embedded in the empty state. CI + Deploy GREEN on `main`. See [STATUS_REPORT.md](./docs/status/STATUS_REPORT.md) for the full session log and [SECURITY.md](./docs/security/SECURITY.md) for the per-finding table.

---

## Features

### v1.0 — Document Management
- **ML Document Classification** — Automatically categorizes documents into bills, invoices, tax forms, bank statements, UPI receipts, and tickets using a trained Linear SVC model (85.06% accuracy — exceeds 85% target)
- **OCR Text Extraction** — Extracts text from scanned PDFs and images using Tesseract with adaptive preprocessing (grayscale, blur, thresholding, deskew, morphological ops, multi-PSM retry)
- **LLM Smart Extraction** — Multi-provider LLM service (Ollama, Gemini, Anthropic, OpenAI, local regex fallback) with category-specific extraction prompts and AI summaries; degraded-mode tracking when only the regex fallback is available
- **Multi-User & RBAC** — Three-tier role system (admin/editor/viewer), admin panel with role/status changes and **soft-delete + PII anonymization** (audit-trail-preserving — see Phase 9 audit immutability trigger), document-level sharing with permissions
- **OAuth SSO** — Google & Microsoft OAuth single sign-on with exchange code flow. Both buttons render unconditionally on `/login` and `/register`; backend gracefully reports "not configured" when OAuth env vars are absent
- **Async Processing** — Upload returns immediately (HTTP 202). Celery workers handle OCR + classification in the background with real-time status polling
- **Full-Text Search** — PostgreSQL `tsvector` + GIN indexes; search across all extracted content with category filtering
- **Secure Auth** — JWT access tokens + opaque refresh tokens with rotation and reuse detection. bcrypt password hashing. Rate limiting on all endpoints
- **Multi-Format Support** — PDF (text + scanned), PNG, JPG, TIFF, DOCX

### v2.0 — Compliance Notice Management
- **Multi-tenant compliance** (Phase 9) — 7-role × 12-permission matrix with row-level security (RLS), audit immutability via DB triggers + `REVOKE` on the `app_runtime` runtime role, and a `cross_client_view` PERMISSIVE policy for senior auditors
- **ML risk scoring + auto-escalation** (Phase 10) — rule-based scorer with SHAP-style factor explanations; review queue for low-confidence classifications; escalation activity + audit log on critical-tier notices
- **Alerts + statutory calendar** (Phase 11) — APScheduler-backed multi-channel alert pipeline (email + WebSocket; SMS scaffolded). 45 statutory deadlines pre-seeded for calendar year 2026 spanning GST returns, IT advance tax, MCA, RBI, SEBI filings plus Indian public holidays. Indian holiday-aware deadline adjustment. Real-time `NotificationBell` with auto-reconnecting WebSocket
- **Response drafting + 4-stage approval** (Phase 12) — Drafter → Reviewer → Legal → CFO workflow with versioned drafts and evidence linking
- **Cross-entity unified search + analytics** (Phase 13) — single FTS query across `compliance_notices` + `documents` (`tsvector` + GIN trigger). Three analytics endpoints: penalty by authority, notice volume by status, response-time percentiles
- **CSV report export** (v2.0.1) — Download Generate-summary + the 3 Phase 13 aggregations as CSV from `/dashboard/compliance/reports`. Stdlib `csv` + `StreamingResponse`, charset=utf-8 declared; no new dependencies
- **Notice file upload pipeline** (Phase 9 + v2.0.1) — `POST /notices/{id}/upload` reuses v1.0 storage AND dispatches the Celery OCR/classification task (parity with the regular doc upload), so notice-attached documents transition `PENDING → COMPLETED` automatically

### v2.1 — Client Branding + BYOK AI (2026-05-08)
- **Per-tenant client branding** — `compliance_clients` gets `logo_url` (base64 data URL ≤340KB), `website` (https-validated), `address`. New endpoints: `POST /compliance/clients/{id}/logo` (multipart, PNG/JPEG/WEBP only with magic-byte validation, SVG rejected for XSS), `PATCH /compliance/clients/{id}/branding`, `DELETE /compliance/clients/{id}/logo`. Logo + name auto-render in a co-brand cluster bottom-left of the sidebar (above the user cluster) so each tenant sees its own brand alongside TaxSync. Edit at **Compliance → Clients → \<client\> → Branding**.
- **BYOK AI assistant** (Phase 16) — bring your own Anthropic Claude or Google Gemini key. One row per tenant in `ai_credentials` (Fernet-encrypted via INFRA-06 cipher). Five task surfaces: notice summary + recommended actions, vendor-invoice summary + suggested actions + payment timing. System prompt hard-restricts the AI to Indian regulatory notices, compliance deadlines, vendor invoices, the approval chain, and TaxSync workflow — anything else returns `OUT_OF_SCOPE` (HTTP 422 with friendly toast). Provider adapters use the official `anthropic` SDK and httpx for Gemini's REST API. Settings page at **/dashboard/settings/ai** with Test + Save flow; entry-points on the dashboard quick-action tile, sidebar nav, and per-page AI panels on every notice and invoice. Costs go to the tenant's provider account; TaxSync never bills for AI.
- **Vendor invoices rebrand** — the email-driven Bills feature relabeled as "Vendor invoices" everywhere user-visible (sidebar nav, dashboard metrics, dashboard quick action, notice page copy). Data model, APIs, and `/api/email/bills/*` paths unchanged — pure UI/copy. Sidebar icon swapped `FiCreditCard` → `FiClipboard`. Reflects the descope of personal/household-bill positioning per 2026-05-08 client guidance.
- **Dashboard SSG fix** — `dynamic = 'force-dynamic'` on `app/dashboard/layout.tsx` plus `QueryClientProvider` hoisted from `compliance/layout` to `dashboard/layout`. Fixes a pre-existing `next build` break on auth-gated pages and gives the new sidebar `useQuery` a provider above it on every dashboard route.

### v2.0 Phase 15: Gmail MCP Integration (2026-05-07)
- **Gmail OAuth + 6 MCP tools.** Connect a tenant's Gmail once, refresh tokens stored Fernet-encrypted, six MCP tools (`gmail_search`, `gmail_read_message`, `gmail_list_attachments`, `gmail_get_attachment`, `gmail_list_labels`, `gmail_modify_labels`) exposed to internal compliance agents via the in-memory FastMCP transport, every invocation writes a PII-redacted audit row. Scheduled scanner (5min to 24hr cadence) ingests attachments into the DMS, auto-creates `ComplianceNotice` rows for regulatory senders, and routes personal or household bills (now branded "Vendor invoices") to the bill dashboard with T-3, T-1, and overdue reminders. See `scripts/smoke_phase15_v20.py` for the automated smoke and `.planning/phases/15-gmail-mcp-integration/15-SMOKE-CHECKLIST.md` for the 12-step manual OAuth checklist.

### v2.0 Phase 18: AI Notice Response Drafting, BYOK (2026-05-25)
- **One endpoint draft generation** at `POST /api/compliance/ai/notice-response-draft/{notice_id}`. Anyone with `NOTICE_DRAFT_RESPONSE` (legal_team, ca_consultant, staff) can call it. The service reads the notice + the Phase 17 extracted_fields envelope, embeds them as JSON context, and asks the tenant's BYOK provider to draft a formal markdown reply that quotes figures verbatim and cites statute sections without invention.
- **User guidance** capped at 800 chars: the caller can include free-text instructions like "be more terse" or "emphasise procedural objections" in the request body. Guidance is truncated before hashing so the audit trail records exactly what the prompt saw.
- **PII-redacted audit chain.** One `notice_ai_draft` row per call with provider, model, tokens in or out, latency, body SHA-256, guidance SHA-256, and the list of extracted-field KEYS used as context. NO raw draft text and NO guidance text in the audit log. Phase 9 immutability trigger applies.
- **Preview-only.** Drafts do not bypass the existing Phase 12 four-stage approval workflow. The caller persists the chosen draft via the existing POST `/api/compliance/notices/{id}/responses` flow, which moves it through Drafter, Reviewer, Legal, CFO as usual.
- **Smoke.** `docker cp scripts/smoke_phase18_v20.py smartdocs-backend:/tmp/ && docker exec -e ANTHROPIC_API_KEY_SMOKE=$KEY smartdocs-backend python /tmp/smoke_phase18_v20.py` runs 10 checks end to end. CI-safe SKIP when no key set. Verified 10/10 PASS on 2026-05-25 against `gemini-2.5-flash-lite`: 1913-char draft, 5.9s latency, 11 extracted fields used.

### v2.0 Phase 17: AI Notice Field Extraction, BYOK (2026-05-25)
- **Upload-first notice creation** at `/dashboard/compliance/notices/new`. Drop a PDF, JPG, or PNG and the page extracts canonical notice fields (notice_number, authority, issued_date, response_deadline, tax_demand, interest, penalty, total_liability, GSTIN, PAN, CIN, taxpayer_name, legal_sections, notice_type) using the tenant's Phase 16 BYOK key. The 14-field schema lines up with the create-notice form so each row carries an accept, edit, or discard affordance plus a per-field confidence badge (emerald `Confident` at >= 0.75, amber `Review` at >= 0.55, rose `Needs review` below).
- **Conjunctive routing gate.** Auto-apply requires ALL of: average confidence >= 0.85, `notice_number` >= 0.85, and `authority` >= 0.85 (D-06). Any miss routes the artefact to the Phase 10 review queue with reason `low_confidence_extraction`. Structural validation (GSTIN, PAN, CIN, ISO dates, liability arithmetic) halves the per-field confidence before the gate runs, so a model that reports 0.95 on a malformed GSTIN drops to 0.475 and falls into the review path.
- **PII-redacted audit chain.** One `notice_ai_extract` row per call with provider, model, latency, tokens, average confidence, body SHA-256, and the list of returned field KEYS only (no raw text, no extracted values). Accepting fields writes one `notice_ai_extract_accepted` row per field carrying `original_value_sha256`, `accepted_value_sha256`, and `was_edited`. Both row types inherit the Phase 9 immutability trigger.
- **Provenance disclosure** on the notice detail page surfaces provider, model, average confidence, extracted-at timestamp, and per-field confidences with hover tooltips explaining any structural validation failures. Manually-created notices remain uncluttered (no disclosure when `extraction_status` is null).
- **Wiring parity across ingestion paths.** The same `extract_notice_fields` service runs from the synchronous `extract-preview` endpoint (D-19), from `process_document_task` when a Celery-OCR'd document is attached to a notice (D-23), and from `process_classified_email` before a Gmail-routed notice row is created (D-24). One routing helper, one audit shape, one set of guarantees. First-upload-wins is enforced; re-uploading does NOT clobber already-accepted fields.
- **Smoke command.** `docker cp scripts/smoke_phase17_v20.py smartdocs-backend:/tmp/ && docker exec -e ANTHROPIC_API_KEY_SMOKE=$KEY smartdocs-backend python /tmp/smoke_phase17_v20.py` runs 12 checks end to end against the live provider (Anthropic preferred per D-32; Gemini accepted via `GEMINI_API_KEY_SMOKE`). Skips cleanly with exit 0 when no key is set, so it is CI-safe. Verified 12/12 PASS on 2026-05-25 against `gemini-2.5-flash-lite` at avg confidence 0.99.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              Next.js Frontend                │
│     Landing · Auth · Dashboard · Search      │
└──────────────────┬───────────────────────────┘
                   │ REST API
┌──────────────────┴───────────────────────────┐
│              FastAPI Backend                  │
│  Auth · OAuth (Google/MS) · Documents · ML   │
├────────────────┬────────────┬────────────────┤
│ PostgreSQL     │   Redis    │ Celery Workers │
│ (Supabase      │  (Broker)  │ (OCR+Classify) │
│  Cloud)        │            │                │
└────────────────┴────────────┴────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router, standalone build), React 19, TypeScript, Tailwind CSS, TanStack Query, Zustand, react-day-picker v9, framer-motion |
| Backend | FastAPI, SQLAlchemy, Pydantic v2, Uvicorn, structlog |
| Database | PostgreSQL (Supabase Cloud, session-mode pooler for Phase 9 RLS), Alembic migrations (head: `0034_phase17_notice_extraction`) |
| AI/LLM | Multi-provider (Ollama, Gemini, Anthropic, OpenAI, local regex fallback) with degraded-mode tracking |
| Phase 10 ML | InLegalBERT (deferred), rule-based risk scorer + SHAP-style factors, scikit-learn (LinearSVC + CalibratedClassifierCV + TF-IDF), Tesseract OCR, pdfplumber, python-docx, spaCy NER |
| Phase 11 alerts | APScheduler (durable), holidays (Indian FY 2025-26), Twilio SMS adapter, WebSocket via FastAPI; SendGrid migration deferred to v2.1 |
| Phase 13 search | PostgreSQL `tsvector` + GIN indexes + trigger-maintained search vectors on `documents` + `compliance_notices` (Elastic Cloud deferred to v2.1) |
| Async | Celery + Redis (default queue + dedicated `compliance` queue with 2GB ceiling) |
| Auth | JWT (HS256) + opaque refresh tokens with rotation + reuse detection, bcrypt, OAuth (Google/Microsoft), slowapi rate limiting |
| Security | RLS on every client-scoped table + immutable audit triggers + `REVOKE` on `app_runtime` role |
| Infra | Docker Compose (db + redis + backend + 2 Celery workers + frontend), Vercel (frontend prod) |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose

### 1. Clone and configure

```bash
git clone https://github.com/IIIT-HYD-PROD-LABS/Smart-Document-Management-System.git
cd Smart-Document-Management-System
cp backend/.env.example .env  # repo root .env, NOT backend/.env (docker compose reads root)
```

Required `.env` keys:

| Key | Why | Notes |
|---|---|---|
| `SECRET_KEY` | JWT signing | ≥ 32 chars, ≥ 10 unique chars (config.py validates) |
| `DATABASE_URL` | Postgres | Supabase pooler in **session mode** (port 5432) — Phase 9 RLS context vars don't survive transaction-mode pooling |
| `REDIS_PASSWORD` | Celery broker | Any random secret |
| `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` | Google OAuth (optional) | Get from console.cloud.google.com → APIs & Services → Credentials. Authorized redirect URI: `http://localhost:8000/api/auth/callback/google` (dev) |
| `MICROSOFT_CLIENT_ID` + `MICROSOFT_CLIENT_SECRET` | Microsoft OAuth (optional) | Same pattern |
| `KAGGLE_USERNAME` + `KAGGLE_KEY` | Dataset retraining (optional) | Only needed if running `python -m app.ml.datasets.download` |

OAuth buttons render unconditionally. If creds are absent, clicking shows a helpful toast (`"Google sign-in not yet configured. Set GOOGLE_CLIENT_ID in backend .env to enable."`); the OAuth dance is fully gated server-side, so no error escape paths.

### 2. Start all services

```bash
docker compose up --build
```

This launches the following containers:

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Next.js UI |
| Backend | http://localhost:8000 | FastAPI REST API |
| Swagger | http://localhost:8000/docs | Interactive API docs (debug mode) |
| Redis | localhost:6379 | Celery message broker |

The PostgreSQL database is hosted on Supabase Cloud and configured via `DATABASE_URL` in `.env`.

For production deployment, see [DEPLOYMENT.md](./docs/deployment/DEPLOYMENT.md). All other docs are organized under [./docs/](./docs/README.md).

### 3. Get the trained model (automatic)

The trained model (`document_classifier.pkl` + `tfidf_vectorizer.pkl`) is committed to git — you get it automatically on `git clone` / `git pull`. No training step needed.

### 4. Download datasets (optional — only if you want to retrain)

Datasets are 28 GB and not in git. To download them into `backend/datasets/`:

```bash
# Add to .env:  KAGGLE_USERNAME=xxx  KAGGLE_KEY=xxx
docker compose run backend python -m app.ml.datasets.download
docker compose run backend python -m app.ml.datasets.prepare
```

Once downloaded they are bind-mounted into the container at `/app/datasets` automatically.

To retrain from scratch after downloading:
```bash
# Synthetic data only (no external deps):
docker compose exec backend python -m app.ml.train --synthetic-only

# Real Kaggle datasets:
docker compose exec backend python -m app.ml.train --full-pipeline

# Combined (real + synthetic augmentation — what achieved 85%):
docker compose exec backend python -m app.ml.train --combined
```

### 5. Local development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head
python -m app.ml.train --synthetic-only
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get access + refresh token pair |
| POST | `/api/auth/refresh` | Rotate refresh token |
| POST | `/api/auth/logout` | Revoke refresh token |
| GET | `/api/auth/providers` | List configured auth providers |
| GET | `/api/auth/oauth/google` | Google OAuth URL |
| GET | `/api/auth/oauth/microsoft` | Microsoft OAuth URL |
| POST | `/api/auth/oauth/exchange` | Exchange OAuth code for tokens |

### Documents (all require `Authorization: Bearer <token>`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/upload` | Upload file (returns 202, async processing) |
| GET | `/api/documents/{id}/status` | Poll processing status |
| GET | `/api/documents/all` | List all documents (paginated) |
| GET | `/api/documents/{id}` | Get document detail |
| GET | `/api/documents/search?q=…` | Full-text search with optional `category` filter |
| GET | `/api/documents/category/{cat}` | Filter by category |
| GET | `/api/documents/stats` | Dashboard statistics |
| DELETE | `/api/documents/{id}` | Delete document + file |

### Sharing (all require `Authorization: Bearer <token>`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/{id}/share` | Share document with a user |
| GET | `/api/documents/{id}/permissions` | List sharing permissions for a document |
| DELETE | `/api/documents/{id}/share/{pid}` | Remove a sharing permission |
| GET | `/api/documents/shared-with-me` | List documents shared with current user |

### Admin (requires admin role)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/users` | List all users |
| GET | `/api/admin/stats` | Admin dashboard statistics |
| PATCH | `/api/admin/users/{id}/role` | Update user role |
| PATCH | `/api/admin/users/{id}/status` | Update user status |

### Audit (requires admin role)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/audit` | Query audit logs (filterable by user, action, resource, date range) |

### ML (requires `Authorization: Bearer <token>`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ml/evaluation` | Model metrics — accuracy, per-category P/R/F1, confusion matrix |

### Compliance — Notices (Phase 9, all require `X-Client-Id` tenant header + role-gated)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/compliance/notices` | List/filter notices for active tenant (paginated) |
| POST | `/api/compliance/notices` | Create notice with manual metadata |
| GET | `/api/compliance/notices/{id}` | Get notice detail |
| PATCH | `/api/compliance/notices/{id}` | Edit metadata (omits status field) |
| PATCH | `/api/compliance/notices/{id}/status` | State machine transition (target-dependent permission gate; `under_review` accepts `NOTICE_REVIEW` OR `NOTICE_DRAFT_RESPONSE`) |
| POST | `/api/compliance/notices/bulk` | Bulk status update with partial-failure semantics |
| GET | `/api/compliance/notices/{id}/chain` | Recursive CTE: ancestors + descendants |
| POST | `/api/compliance/notices/{id}/upload` | Attach PDF/JPG/PNG; first upload becomes `notice.document_id`; **dispatches Celery OCR + classification** (v2.0.1) |
| GET | `/api/compliance/notices/{id}/activity` | User-facing timeline |
| POST | `/api/compliance/notices/{id}/activity/note` | Add free-text note |

### Compliance — Reports + Search (Phase 13 + v2.0.1 CSV exports)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/compliance/reports/health-summary` | Monthly summary JSON; payload: `{client_id, month: "YYYY-MM"}` |
| POST | `/api/compliance/reports/health-summary/export` | Same as above, returns **CSV** |
| GET | `/api/compliance/reports/penalty-by-authority` | Aggregation JSON |
| GET | `/api/compliance/reports/penalty-by-authority/export` | Aggregation **CSV** |
| GET | `/api/compliance/reports/notice-volume-by-status` | Aggregation JSON |
| GET | `/api/compliance/reports/notice-volume-by-status/export` | Aggregation **CSV** |
| GET | `/api/compliance/reports/response-time` | Percentile stats JSON |
| GET | `/api/compliance/reports/response-time/export` | Percentile stats **CSV** (3-column `metric,value,unit`) |
| GET | `/api/compliance/search/unified?q=…` | FTS across notices + documents (`min_length=2`) |

### Compliance — Other Phase 9-12 (gated by role + tenant)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/compliance/clients/me` | List the tenants the current user has membership on |
| GET | `/api/compliance/audit` | Read-only immutable audit log (DB trigger + `REVOKE` on `app_runtime` enforce append-only) |
| GET | `/api/compliance/calendar/entries` | 45 statutory deadlines for calendar year 2026 (year/month/authority/category filterable) |
| GET | `/api/compliance/calendar/compliance-score` | Rolling 90-day compliance health score |
| GET | `/api/compliance/review/pending` | Phase 10 ML review queue |
| PATCH | `/api/compliance/review/{review_id}/assign` | Assign authority + notice type for low-confidence ML output |
| POST | `/api/compliance/responses` | Create draft response |
| GET | `/api/compliance/responses/{id}` | Read response state + version |
| PATCH | `/api/compliance/responses/{id}/transition` | 4-stage approval transition (Drafter → Reviewer → Legal → CFO) |

### Compliance — Client Branding (v2.1, gated by `CLIENT_MANAGE_TEAM`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| PATCH  | `/api/compliance/clients/{id}/branding` | Update website + address (JSON body, https-prefix validated) |
| POST   | `/api/compliance/clients/{id}/logo` | Upload logo (multipart, ≤256KB, PNG/JPEG/WEBP only, magic-byte validated, stored as base64 data URL) |
| DELETE | `/api/compliance/clients/{id}/logo` | Clear the stored logo |

### Compliance — BYOK AI Assistant (v2.1 / Phase 16, all under `/api/compliance/ai`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/credentials` | Read provider + model + has_key (NEVER returns the key); gated `notice:view` |
| POST   | `/credentials` | Set / replace provider + model + api_key; gated `client:manage_team` |
| DELETE | `/credentials` | Disconnect AI; gated `client:manage_team` |
| POST   | `/credentials/test` | One-token round-trip ping; returns `{ok, latency_ms, detail?}` |
| POST   | `/notice-summary/{notice_id}` | Markdown summary + key points + deadline_iso |
| POST   | `/notice-actions/{notice_id}` | `[{label, rationale, urgency}]` action list |
| POST   | `/invoice-summary/{bill_id}` | Summary + anomalies (vs same-vendor history) |
| POST   | `/invoice-actions/{bill_id}` | Action list (mark paid / flag duplicate / escalate) |
| POST   | `/invoice-timing/{bill_id}` | Payment-timing recommendation + rationale + suggested_payment_date |

The AI is **scope-locked** via the system prompt — anything outside Indian regulatory work, vendor invoices, or TaxSync workflow returns the literal `OUT_OF_SCOPE`, mapped to HTTP 422 with a friendly client-side message.

Permission matrix (84-cell): see `backend/app/compliance/services/permission_registry.py` and `backend/tests/test_compliance_endpoints.py`. Roles: `compliance_head`, `legal_team`, `finance_team`, `auditor`, `ca_consultant`, `staff`, `cfo`.

---

## Document Categories

| Category | Examples | Training Data |
|----------|----------|---------------|
| Bills | Utility bills, phone bills | Financial images (India) |
| UPI | UPI transaction receipts | UPI Transactions 2024 (250K records) |
| Tickets | Event/travel tickets | Synthetic |
| Tax | ITR forms, tax documents | ITR Form 16 images |
| Bank | Bank statements, passbooks | Bank statements CSV + images |
| Invoices | Purchase invoices, receipts | Invoice OCR (8K images), RVL-CDIP |

---

## Processing Pipeline

```
Upload (HTTP 202)
  │
  ▼
Celery Worker picks up task
  │
  ├─ PDF? ──► pdfplumber text extraction
  │            └─ fallback to OCR if < 50 chars
  ├─ DOCX? ─► python-docx (paragraphs + tables)
  ├─ Image? ► Tesseract OCR
  │            ├─ Grayscale → Gaussian blur → Adaptive threshold
  │            ├─ Deskew correction
  │            ├─ Morphological open/close
  │            └─ Multi-PSM retry (PSM 6 → PSM 3)
  │
  ▼
Text Preprocessing (clean, normalize, preserve financial patterns)
  │
  ▼
TF-IDF + Linear SVC Classification
  │
  ▼
LLM Smart Extraction (category-specific prompts → structured JSON)
  │
  ▼
Metadata Extraction (dates, amounts, vendor — regex + dateutil)
  │
  ▼
Status: COMPLETED (category + confidence score + metadata + AI summary)
```

---

## Project Structure

```
backend/
  app/
    main.py                  # FastAPI app, middleware, routes
    config.py                # Pydantic settings from .env
    database.py              # SQLAlchemy engine + session
    models/                  # User, Document, RefreshToken
    schemas/                 # Request/response Pydantic models
    routers/                 # auth.py, documents.py, admin.py
    services/                # storage_service.py, oauth_service.py
    middleware/               # Security headers, request logging
    ml/
      ocr.py                 # Image preprocessing + Tesseract
      pdf_extractor.py       # pdfplumber + OCR fallback
      docx_extractor.py      # python-docx extraction
      text_preprocessor.py   # Text cleaning for ML
      classifier.py          # Classification orchestrator
      metadata_extractor.py  # Date/amount/vendor regex extraction
      train.py               # Model training pipeline
      datasets/              # Kaggle download + data preparation
    tasks/                   # Celery task definitions
    utils/                   # JWT, rate limiter, logging
  alembic/                   # Database migrations
  Dockerfile
  requirements.txt

frontend/
  src/
    app/
      page.tsx               # Landing page
      login/                 # Sign in
      register/              # Sign up
      oauth/callback/        # OAuth callback handler
      dashboard/
        page.tsx             # Overview (stats, categories, recent)
        upload/              # Drag-drop upload with progress
        documents/           # Document list with category filters
        search/              # Full-text search
        analytics/           # Category distribution, processing status
        admin/               # Admin panel (user management, stats)
        shared/              # Shared documents view
    context/                 # Auth context (token management)
    lib/                     # Axios API client with refresh interceptor
  Dockerfile

docker-compose.yml           # Redis, Backend, Celery, Frontend
```

---

## Development Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation & Security Hardening | ✅ Done |
| 2 | Document Processing Pipeline | ✅ Done |
| 3 | ML Classification Upgrade | ✅ Done (85.06% accuracy) |
| 4 | Search & Retrieval Engine | ✅ Done (FTS + fuzzy + filters) |
| 5 | LLM Smart Extraction | ✅ Done |
| 6 | Multi-User & RBAC | ✅ Done |
| Security Audit | 21 fixes across 17 files | ✅ Done |
| Auth & Login Fixes | 11 bugs fixed (March 2026) | ✅ Done |
| Security Hardening | 25 fixes across 14 files + all tests green | ✅ Done |
| 7 | UI & Analytics | ✅ Done |
| 8 | Production Readiness | ✅ Done |
| 9 | Compliance Foundation (v2.0) | ✅ Shipped 2026-04-28 |
| 10 | ML Classification + Risk Scoring (v2.0) | ✅ Code-complete + smoke PASSED 2026-05-05 (v2.1 BERT bake-off deferred) |
| 11 | Alerts + Compliance Calendar (v2.0) | ✅ Code-complete + hardening pass 2026-05-05 (v2.1 SendGrid + DLT SMS + ICS export deferred) |
| 12 | Response Drafting + Evidence (v2.0) | ✅ Code-complete + smoke PASSED 2026-05-05 (v2.1 templates + LLM drafts + PDF merge + ITC recon deferred) |
| 13 | Elasticsearch + Cross-Entity Search (v2.0) | ✅ Code-complete + smoke PASSED 2026-05-05 via PG-FTS (v2.1 Elastic Cloud + outbox deferred) |
| 14 | Government Portal Integration (v2.0) | CONTEXT seeded 2026-05-05 — BLOCKED on GSP empanelment + IT API access |
| 15 | Gmail MCP Integration (v2.0) | ✅ Shipped 2026-05-07 (7/7 plans) |
| 16 | BYOK AI Assistant (v2.1) | ✅ Shipped 2026-05-08 |
| 17 | AI Notice Field Extraction, BYOK (v2.0) | ✅ Shipped 2026-05-25 (7/7 plans, smoke 12/12 PASS) |
| 18 | AI Notice Response Drafting, BYOK (v2.0) | ✅ Shipped 2026-05-25 (1 plan, smoke 10/10 PASS against live Gemini) |

### Completed

**Phase 1** — JWT refresh token rotation with reuse detection, bcrypt auth, rate limiting (slowapi), security headers (HSTS, CSP, X-Frame-Options), structured JSON logging with correlation IDs, Alembic migration framework.

**Phase 2** — Multi-format text extraction (PDF, DOCX, images), OCR with adaptive preprocessing, async Celery processing (202 Accepted + status polling), frontend bulk upload with per-file progress, metadata extraction (dates, amounts, vendor).

**Phase 3** — Upgraded classifier from Logistic Regression (76.4%) to Linear SVC (85.06%, exceeds >85% target). 7 Kaggle datasets (28 GB), TF-IDF 15K vocab + trigrams, class-balanced training with synthetic augmentation (factor=10). ML evaluation API + model evaluation dashboard page with confusion matrix and per-category P/R/F1 badges. Trained model committed to git; datasets bind-mounted in Docker for team access.

**Phase 4** — PostgreSQL full-text search replacing ILIKE: stored tsvector column with GIN index, ts_rank relevance ordering, `pg_trgm` trigram fuzzy matching (OR-combine: FTS for stems + trigram for typos). Category, date range, and amount filters with JSONB NULL guards. Frontend filter UI. Rate-limited search endpoint (30/min). Opus code review applied 6 fixes (pattern injection, date validation, amount cast safety, trigger optimization).

**Phase 5** — LLM Smart Extraction: Multi-provider LLM service (Ollama, Gemini, Anthropic, OpenAI, local regex fallback), category-specific extraction prompts with structured JSON output, AI summaries per document.

**Phase 6** — Multi-User & RBAC: Three-tier role system (admin/editor/viewer), admin panel, document-level sharing with permissions, Google & Microsoft OAuth SSO, OAuth exchange code flow.

**Security Audit** — 21 fixes across 17 files: OAuth CSRF protection, token rotation security, rate limiter IP spoofing fix, security headers hardening, input validation.

**Auth & Login Fixes (March 23, 2026)** — Fixed 11 bugs blocking login/registration: database connection (Supabase pooler host/password), Redis rate limiter graceful fallback, cookie expiry on silent refresh and OAuth paths, double navigation in login/register, logout race condition, dashboard auth guard, OAuth JSON response safety, token rotation ordering, ValueError handling in OAuth exchange.

**Security Hardening (March 25, 2026)** — Comprehensive security audit with 20 parallel agents. 25 fixes across 14 files: password complexity enforcement (8+ chars, upper/lower/digit/special), magic bytes file validation, streaming upload to prevent memory DoS, CSP hardening (removed unsafe-eval), server-side route protection via Next.js middleware, global exception handler, JWT jti claims, OAuth timing-safe comparison, CORS wildcard validation, DB SSL + connection pool hardening, Celery rate limiting. All 12 tests fixed and passing (was 2/12).

**Phase 7 — UI & Analytics (March 25, 2026)** — Full recharts analytics dashboard (area chart for upload trends, donut chart for category distribution, stat cards, processing status bar). In-browser document preview (react-pdf for PDFs with page nav + zoom, image viewer with zoom/pan, DOCX extracted text). Document version control (auto-versioning on re-upload, version history, rollback). Shared component library (ConfidenceBadge, StatusBadge, CategoryBadge, LoadingSpinner). Responsive sidebar with hamburger menu on mobile/tablet.

**UI Redesign** — Minimalist dark theme (Linear/Notion-inspired), Inter font, zinc/neutral palette, no glassmorphism. Clean dashboard with stats, category filters, full-text search, analytics.

**Phase 8 — Production Readiness (March 25, 2026)** — Audit logging system (AuditLog model, audit service with fire-and-forget BackgroundTasks, admin query endpoint with filters). GitHub Actions CI/CD (automated tests + lint on push/PR, Docker image build on merge, Dependabot for dependency updates). Production documentation (DEPLOYMENT.md step-by-step guide, TROUBLESHOOTING.md with 12+ entries, SECURITY.md production checklist).

---

## v2.0 — Compliance Management System

Smart Document Management System v2.0 extends v1.0 with multi-tenant compliance notice tracking for Indian regulators (GST, IT, MCA, RBI, SEBI). Manual notice metadata entry, full status workflow, immutable audit trail, multi-client RBAC — Phase 9 ships the foundation; Phases 10-14 add ML auto-classification, alert system, response drafting, cross-entity search, and government-portal integration.

### Phase 9 — Compliance Foundation

**Goal:** Manually track compliance notices end-to-end with full audit trail, multi-client support, and role-based access control.

**ROADMAP success criteria — all GREEN:**

1. Upload a compliance notice (PDF/JPG/PNG) with manual metadata; appears scoped to the correct client.
2. Move a notice through the full workflow (Received → Under Review → Response Drafted → Submitted → Resolved/Dismissed) and link related notices via parent_notice_id chain.
3. Filter and search by authority/type/status/risk/deadline/GSTIN; bulk-update status for multiple notices.
4. Every notice action recorded in an immutable, timestamped audit log — no application user (including admins) can alter or delete an audit record (PostgreSQL trigger + REVOKE on app_runtime role).
5. CA/Tax Consultant manages multiple client entities (each with distinct GSTIN/PAN) with PostgreSQL RLS guaranteeing zero cross-client leakage.
6. All 7 compliance roles enforce correct permission boundaries: Compliance Head, Legal Team, Finance Team, Auditor (time-bound), CA/Consultant, Staff, CFO — verified by 84-case parametrized RBAC matrix.

**Requirements covered (26):** LIFE-01..08, AUDIT-01/02, RBAC-01..06, CLIENT-01..07, INFRA-05/06/07.

### Stack additions for v2.0

| Layer | Additions |
|-------|-----------|
| Backend | PostgreSQL RLS (FORCE ROW LEVEL SECURITY on 6 client-scoped tables), `app_runtime` DB role with REVOKE on audit_logs, Fernet PII encryption, pytest-freezer + freezegun, structlog redact_pii |
| Frontend | zustand@5 (multi-tenant state + persist), @tanstack/react-query@5 (server cache), @tanstack/react-table@8 (notice table + row selection), react-hook-form@7 + zod@3 (wizard validation), react-day-picker@9 (date pickers — v9 for React 19 compat), papaparse@5 (CSV), date-fns@3 |
| Migrations | 0013–0019 (clients, registrations, memberships, notices, activity, calendar, RLS policies, recursion fix, fail-closed cast) |

### Run commands

```bash
# Start all services (Postgres, Redis, backend, frontend)
docker compose up -d

# Apply Phase 9 migrations
docker compose exec backend alembic upgrade head

# Run full backend test suite (Phase 9 merge gates: RLS isolation, audit immutability, RBAC matrix)
docker compose exec backend pytest --tb=short tests/

# Run frontend lint (skipped at build-time per next.config.mjs.eslint.ignoreDuringBuilds)
docker compose exec frontend npm run lint
```

### Phase 9 plan status

| Plan | Wave | Description | Status |
|------|------|-------------|--------|
| 09-01 | 0 | Test infrastructure: 17 stub test files, conftest fixtures, validation contract | ✅ done |
| 09-02 | 1 | DB foundations: 5 migrations (schema, audit-immutability trigger, RLS policies, calendar seed, DB roles) + Indian validators + permission registry + state machine | ✅ done |
| 09-03 | 2 | ORM models + services: Client/Membership/Notice/NoticeType/Calendar + activity_service + notice_service + client_service + report_service (+ migration 0018 RLS recursion fix) | ✅ done |
| 09-04 | 3 | Tenant context middleware + auditor expiry + require_compliance_permission factory + 3 merge gates GREEN | ✅ done |
| 09-05 | 4 | 7 FastAPI compliance routers (clients, memberships, notices, reports, audit, lookups) under /api/compliance | ✅ done |
| 09-06 | 5 | Frontend foundation: 2 Zustand stores, complianceApi axios extension (X-Client-Id auto-attach), ClientSwitcher, 4-step onboarding wizard, team management (user APPROVED 2026-04-27) | ✅ done |
| 09-07 | 6 | Frontend notice surfaces: 12 components, 5 pages, README v2.0 — compliance dashboard, notice detail (40/60 layout), bulk action bar with partial-failure UX, audit log viewer, monthly health summary report (XSS-safe structural render) | ✅ code-complete (manual smoke test pending) |

---

## Environment Variables

```env
DATABASE_URL=postgresql://postgres:postgres@db.xxxx.supabase.co:5432/postgres
SECRET_KEY=your-secret-key-minimum-32-characters
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=50
USE_S3=false
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
ML_CONFIDENCE_THRESHOLD=0.3
DEBUG=true

# OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# Email (SMTP) is required to deliver early-access invitations, password
# resets, tenant invites, and compliance alerts. Without these, admin
# approval still succeeds but the invitee never gets the link (the admin
# UI flags this with "approved, but email NOT delivered").
#
# Recommended: Gmail App Password (free, ~500 emails/day, delivers to any
# recipient, no domain verification). Requires 2-Step Verification on the
# account; generate a 16-char value (no spaces) at
# https://myaccount.google.com/apppasswords (App = Mail). Gmail rewrites or
# rejects any From that is not the authenticated account, so SMTP_FROM_EMAIL
# must equal SMTP_USERNAME.
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=xxxxxxxxxxxxxxxx
SMTP_FROM_EMAIL=you@gmail.com
SMTP_USE_TLS=true

# Alternative: Resend (3k emails/month free, sandbox sender
# onboarding@resend.dev needs no domain). Caveat: the free tier rejects
# every recipient that is not the account owner with a 550 ("verify a
# domain at resend.com/domains"), so it cannot reach arbitrary users until
# you verify a domain. This limitation is why Gmail is recommended above.
# SMTP_HOST=smtp.resend.com
# SMTP_USERNAME=resend
# SMTP_PASSWORD=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# SMTP_FROM_EMAIL=onboarding@resend.dev

# LLM
LLM_PROVIDER=ollama
LLM_MODEL=llama3
```

See `backend/.env.example` for the full list.

## Auth & Early-Access Flow

1. Visitor lands on `/`, clicks **Start Beta Trial** → fills the modal → record persisted in `early_access_requests` (status: `pending`).
2. Admin approves at `/dashboard/admin` → backend mints a 7-day JWT and sends `Your TaxSync Early Access is Approved!` email containing `${FRONTEND_URL}/register?token=<jwt>`.
3. Invitee clicks the email link → `/register?token=<jwt>` → frontend validates the token via `GET /api/early-access/validate-invite?token=<jwt>` → form pre-fills email + full name (email is read-only).
4. Invitee chooses username + password → `POST /api/auth/register` → token pair issued → redirected to `/dashboard`.
5. Existing users sign in via the **Sign in** link in the navbar → `/login`.

If `SMTP_HOST` is not set, admin approval still succeeds but the toast on `/dashboard/admin` reads "approved, but email NOT delivered (SMTP not configured)". In `DEBUG=true`, the registration URL is logged to the backend so you can copy/paste it into the browser without running an SMTP server.

---

## Team

**Sravan** (10srav) — Development Lead
**Jyothika** — CORE MEMBER

Built for **Product Labs, IIIT Hyderabad**.
