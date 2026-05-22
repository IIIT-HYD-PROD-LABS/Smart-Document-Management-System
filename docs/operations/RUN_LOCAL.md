# Local Docker runbook

How to start, restart, and debug Smart-Docs locally without help from Claude.
All commands assume your cwd is the repo root (where `docker-compose.yml` lives).

Backend code and frontend code are **baked into images at build time**, not
volume-mounted. That means *every* code change you pull requires a rebuild of
the changed image. There is no hot-reload.

## Quick cheat sheet

```bash
# After git pull, rebuild whichever side changed (or both):
docker compose build backend frontend                 # rebuild images
docker compose up -d                                  # start everything

# Just restart a running container without rebuilding (no code change):
docker compose restart backend
docker compose restart frontend

# Tail logs:
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f celery_worker compliance_worker

# Health checks:
curl http://localhost:8000/api/health/live            # liveness (fast)
curl http://localhost:8000/api/health                 # deep check (DB, Redis)
curl http://localhost:3000/login -o /dev/null -w "%{http_code}\n"

# Stop everything but keep volumes (DB data preserved):
docker compose down

# Nuclear option, wipes DB volume too:
docker compose down -v
```

## Decision tree: what to rebuild after `git pull`

| Files changed                                              | What to run                                                  |
|------------------------------------------------------------|--------------------------------------------------------------|
| `backend/requirements.txt`                                 | `docker compose build backend celery_worker compliance_worker` |
| `backend/**/*.py` (any Python)                             | `docker compose build backend celery_worker compliance_worker` |
| `backend/alembic/versions/*.py` (new migration)            | rebuild backend, then run migration (see below)              |
| `frontend/package.json` or `frontend/package-lock.json`    | `docker compose build frontend`                              |
| `frontend/src/**/*.{ts,tsx,css}`                           | `docker compose build frontend`                              |
| `frontend/next.config.mjs` (CSP, env, etc.)                | `docker compose build frontend`                              |
| `docker-compose.yml` or `docker-compose.override.yml`      | `docker compose up -d --force-recreate`                      |
| `.env` (any env var)                                       | `docker compose up -d --force-recreate`                      |
| Anything in `.github/`, `docs/`, `README.md`               | nothing, docs only                                           |

If you don't know what changed, the safe blunt hammer is:

```bash
docker compose build
docker compose up -d
```

That rebuilds every service image. Takes about 3-5 minutes the first time and
~30 seconds on subsequent runs (Docker caches the `pip install` and `npm ci`
layers as long as `requirements.txt` and `package-lock.json` are unchanged).

## Full post-pull cycle (the common case)

```bash
git pull
docker compose build backend frontend celery_worker compliance_worker
docker compose up -d
# Wait ~15s for healthchecks, then verify:
curl -s http://localhost:8000/api/health/live
curl -s -o /dev/null -w "frontend=%{http_code}\n" http://localhost:3000/login
```

If the backend logs show `relation "X" does not exist` or you see migration
files in the diff, run the migration step below.

## Database migrations (Alembic)

The backend container has `alembic` installed. Migration files live in
`backend/alembic/versions/`. To apply pending migrations:

```bash
docker exec smartdocs-backend alembic upgrade head
```

To see what is pending without applying:

```bash
docker exec smartdocs-backend alembic current
docker exec smartdocs-backend alembic history --verbose
```

After a migration, restart the workers so any model-cache-dependent code
picks up the new schema:

```bash
docker compose restart celery_worker compliance_worker
```

## Tests inside the container

```bash
# All non-integration tests (fast, no Supabase RLS dependency):
docker exec smartdocs-backend pytest tests/ -m "not integration" -q

# A specific test file:
docker exec smartdocs-backend pytest tests/test_auth.py -v

# A single test:
docker exec smartdocs-backend pytest tests/test_auth.py::TestRegister::test_valid_registration_returns_201_with_tokens
```

## Shell access for debugging

```bash
# Python REPL with the app loaded:
docker exec -it smartdocs-backend python

# Plain shell:
docker exec -it smartdocs-backend bash
docker exec -it smartdocs-frontend sh        # alpine, no bash

# Postgres CLI (connects to the Supabase pooler from inside the container):
docker exec -it smartdocs-backend psql "$DATABASE_URL"
```

## Common failures and fixes

**`Container smartdocs-frontend is unhealthy`**: the frontend image hasn't
been rebuilt after a code change, or the build itself failed. Run
`docker compose logs --tail 80 frontend` to see the npm/Next.js error.

**`POST /api/auth/register` returns 403 "Registration requires an invitation"**:
expected behaviour after 94aa3c9. Only the bootstrap admin can self-register;
all subsequent registers need a token from an approved early-access entry.
Test/dev registers should go through the approved early-access flow or be
created directly in the DB.

**`GET /api/health` returns 503 but `/live` is 200**: deep health check timed
out against Supabase pooler (slow network or rate limit). The app is fine,
just retry. The 503 is a deliberate signal so load balancers can drain
deeply-unhealthy instances.

**`permission denied to set role "app_runtime"` in tests**: integration tests
require the Postgres test DB user to have `SET ROLE` permission. Skip them
locally with `-m "not integration"`. CI runs them via the dedicated runtime
role.

**`Gmail credential ... revoked or unauthorized`**: the OAuth token at Google
side was disconnected or expired. Reconnect via `/dashboard/email/settings`
(the new admin/integrations surface) and the 15-minute polling schedule will
register a fresh APScheduler job automatically.

**`Incompatible React versions`**: someone bumped `react` without also
bumping `react-dom`. Run `npm install react@<version> react-dom@<version>`
together to regenerate the lockfile, then rebuild.

## Container map

| Container                    | Image                 | Port | Restart when                                       |
|------------------------------|-----------------------|------|----------------------------------------------------|
| `smartdocs-backend`          | FastAPI + uvicorn     | 8000 | backend Python code or requirements.txt changes    |
| `smartdocs-celery`           | same as backend       | none | backend code changes (uses same image)             |
| `smartdocs-compliance-worker`| same as backend       | none | backend code or compliance task changes            |
| `smartdocs-frontend`         | Next.js standalone    | 3000 | frontend code or package.json changes              |
| `smartdocs-db`               | postgres:16-alpine    | 5432 | almost never (stateful)                            |
| `smartdocs-redis`            | redis:7-alpine        | 6379 | almost never (stateful)                            |

## One-liner aliases (optional)

Drop these in your `~/.bashrc` or `~/.zshrc` for muscle memory:

```bash
alias sd-up='docker compose up -d'
alias sd-down='docker compose down'
alias sd-build='docker compose build backend frontend celery_worker compliance_worker'
alias sd-rebuild='sd-build && sd-up'
alias sd-logs='docker compose logs -f backend frontend'
alias sd-be='docker exec -it smartdocs-backend bash'
alias sd-fe='docker exec -it smartdocs-frontend sh'
alias sd-migrate='docker exec smartdocs-backend alembic upgrade head'
alias sd-test='docker exec smartdocs-backend pytest tests/ -m "not integration" -q'
alias sd-health='curl -s http://localhost:8000/api/health | python3 -m json.tool'
```
