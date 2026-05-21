# 06 · DEPLOYMENT

> Docker Compose locally · Vercel for frontend · VPS/EC2 + Supabase for backend
> Alembic migrations on every release

## ★ Remember
- 5 services per stack: frontend · backend · celery · compliance_worker · redis (+ local db)
- Supabase = **session-mode pooler** (port 5432), not transaction mode
- `SECRET_KEY` ≥ 32 chars, ≥ 10 unique characters
- `DEBUG=false` in prod hides `/docs` and enables HSTS
- Docker healthchecks gate startup order

---

## 1. Docker Compose topology

```
┌─────────────────────────────────────────────────────┐
│ smartdocs-frontend  :3000   Next.js 15 standalone   │
└──────────────┬──────────────────────────────────────┘
               │ NEXT_PUBLIC_API_URL
               ▼
┌─────────────────────────────────────────────────────┐
│ smartdocs-backend   :8000   FastAPI + Uvicorn       │
│ healthcheck: GET /api/health                        │
│ vols: uploads · models · datasets · audit_failures  │
└──────┬──────────────┬──────────────────┬────────────┘
       │              │                  │
       ▼              ▼                  ▼
 smartdocs-db    smartdocs-redis    smartdocs-celery
   :5432           :6379              (default queue)
   pg16-alpine     redis7 +pwd        2 worker proc
   512M cap        256M cap           1G cap

                                  smartdocs-compliance-worker
                                  compliance queue
                                  2.5G cap · HF cache mount
```

---

## 2. Zero-to-run

```bash
git clone https://github.com/IIIT-HYD-PROD-LABS/Smart-Document-Management-System.git
cd Smart-Document-Management-System
cp backend/.env.example .env         # repo root (NOT backend/.env)
vim .env                              # set SECRET_KEY + DATABASE_URL
docker compose up --build

# follow
docker compose logs -f backend
docker compose exec backend alembic upgrade head
```

- Docker Compose reads `.env` from the **repo root**, not `backend/.env`
- First user to register becomes admin automatically

---

## 3. Required env vars

| Var | Required | Notes |
|-----|----------|-------|
| `SECRET_KEY` | ✓ | ≥ 32 chars, ≥ 10 unique |
| `DATABASE_URL` | ✓ | Supabase pooler port 5432 (session mode) for RLS |
| `REDIS_PASSWORD` | ✓ | Random secret |
| `ALLOWED_ORIGINS` | ✓ prod | JSON array; **never `*`** |
| `FRONTEND_URL` | ✓ | Used in OAuth redirect target |
| `DEBUG` | — | `false` in prod (hides /docs, sets HSTS) |
| `LLM_PROVIDER` | — | `local` default; OK without keys |
| `GOOGLE_*` / `MICROSOFT_*` | — | OAuth optional |
| `USE_S3` + AWS keys | — | Else local FS |
| `AUDIT_FAILURES_PATH` | — | Default `/var/log/smartdocs/audit_failures.jsonl` |

---

## 4. Supabase gotchas

- **Use port 5432 (session mode)** not 6543 (transaction mode)
- Phase 9 RLS uses `set_config(..., is_local=true)` + `SET ROLE` — both are tx-local. Transaction pooling discards them between requests, so RLS context evaporates.
- Password expiry: rotate every 90 days; update `DATABASE_URL` and redeploy backend + workers
- Some DDL (CREATE ROLE, FORCE RLS) needs `postgres` super — run locally first
- Supabase Advisor flagged some policies → migration `0024_supabase_security_advisor_fixes` resolves

---

## 5. Production topology

```
[ Vercel ] ◄─── Next.js (standalone build · CDN)
   │
   │  fetch
   ▼
[ VPS / EC2 ] ──► FastAPI + uvicorn + 2 celery workers
                  │ Docker Compose minus the db service
                  │ TLS terminated by nginx / Caddy / ALB
                  ▼
[ Supabase ] ◄─── Postgres (managed) · session-mode pooler
                  RLS · audit-trigger preserved across hosts
[ Upstash ] ◄─── Redis (managed) — optional
```

Local compose still works; remove `db` from the compose file and point `DATABASE_URL` at Supabase.

---

## 6. Frontend on Vercel

- `vercel.json` at repo root
- Standalone output via Next.js 15
- `NEXT_PUBLIC_API_URL` set per environment
- Preview deploys per PR
- `export const dynamic = "force-dynamic"` on `dashboard/layout.tsx` — prevents SSG break on auth-gated pages
- Edge middleware redirects unauth users to `/login`

---

## 7. Build pipeline

```
1. push to main
2. .github/workflows               CI:
     ├ backend tests (pytest)      · 502+ green
     ├ frontend build              · next build
     └ lint + ruff                 · pip check
3. on green:
     ├ frontend → Vercel (auto)
     └ backend  → manual:
         ssh prod-host
         git pull
         docker compose up -d --build backend celery_worker compliance_worker
         docker compose exec backend alembic upgrade head
```

---

## 8. Healthchecks

| Service | Probe |
|---------|-------|
| db | `pg_isready` every 10 s |
| redis | `redis-cli ping` every 10 s |
| backend | `GET /api/health` every 15 s, 30 s start period |
| celery | `celery inspect ping` every 30 s |
| compliance_worker | same, 60 s start (waits on HF cache) |

`/api/health` reports `{database, redis}` connection state; returns 503 if either is down.

---

## 9. Logging

- structlog JSON output
- correlation-id injected via `asgi-correlation-id`
- Docker log driver: json-file, 10 MB × 3 rotate
- Audit dead-letter at `/var/log/smartdocs/` (named volume)
- Celery workers log to stdout (`--loglevel=info`)

---

## 10. Backup & DR

- Postgres → Supabase point-in-time restore
- Uploads → Docker named volume `backend_uploads` (or migrate to S3)
- Audit JSONL volume `audit_failures` — DO NOT prune
- BERT models in `/app/models/hf_cache` survive worker restart
- Refresh tokens re-issue on next login if DB lost

---

## 11. Observability

- Sentry plug-in points (TODO)
- Celery flower behind admin (not exposed publicly)
- Vercel analytics for FE
- Supabase Query Performance + Logs
- Tenant listener emits `tenant_listener_set` debug logs

---

## 12. Pre-deploy checklist

1. `SECRET_KEY` — ≥ 32 chars, ≥ 10 unique, rotated since last incident
2. `DATABASE_URL` — session mode (5432), password fresh
3. `ALLOWED_ORIGINS` — exact frontend URL, no wildcard
4. `DEBUG=false` — hides `/docs`, enables HSTS
5. `alembic upgrade head` — currently `0032_add_ai_credentials`
6. OAuth redirect URIs — match `FRONTEND_URL` in `console.cloud.google.com` + `entra.microsoft.com`
7. `USE_S3` if running multi-host workers — local FS doesn't survive
8. Audit dead-letter volume mounted and writable
9. `GET /api/health` returns 200
10. Smoke: register → upload → search on prod URL

---

> "Schema before code. Code before clients.
> Rolling back? Reverse the order."

**Upgrade order:**
1. `alembic upgrade head` first — schema must lead code
2. Roll out new backend + workers
3. Roll out new frontend last (it consumes the API)
4. Verify `/api/health` 200 before tearing down old containers
5. NEVER skip workers — they share the same codebase
