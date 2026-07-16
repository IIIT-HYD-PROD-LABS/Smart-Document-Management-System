# Deploy topology for TaxSync / Smart Document Management
#
# Three git remotes, two runtime worlds. CI always uses ephemeral Postgres on
# GitHub runners. Campus staging/prod uses IIIT Postgres + fixed ports.

## Remotes

| Remote | URL | Role |
|---|---|---|
| `origin` | `IIIT-HYD-PROD-LABS/Smart-Document-Management-System` | Monorepo + CI/CD source of truth |
| `gh-backend` | `IIITH-Product-Labs/Taxsync_Backend` | Flat backend export for campus/Jenkins-style jobs |
| `gh-frontend` | `IIITH-Product-Labs/Taxsync_Frontend` | Frontend ship branch (`staging`) |
| `gitlab-backend` / `gitlab-frontend` | `http://10.2.8.15/...` | Campus GitLab mirrors (optional) |

## Runtime environments

### A) GitHub Actions CI (this monorepo)

- Postgres 15 service container on `localhost:5432` (user/db `test`)
- Redis 7 on `localhost:6379`
- Env vars set in `.github/workflows/ci.yml` only (no Supabase, no 10.2.8.x)
- Jobs: `secret-scan`, `test`, `lint`, `docker-build`, `frontend-checks`
- Deploy workflow only builds/pushes images when Docker Hub secrets exist;
  it cannot SSH into campus

### B) Local docker-compose (developer laptop)

- `docker-compose.yml` + `docker-compose.override.yml`
- Local `db` service Postgres (host port **5434** → container 5432)
- Historical notes about Supabase are comments only; override points at `db:`
- Not the campus topology

### C) IIIT campus staging (production-like)

- Host: **10.2.8.73**
- Compose: `docker-compose.prod.yml` + server-local **`.env.prod`** (never git)
- Ports:
  - Backend **8025** → container `:8000`
  - Frontend **8026**
  - Redis loopback **127.0.0.1:6379**
- Public URLs (campus nginx):
  - API: `https://canvas.iiit.ac.in/taxsyncbestage`
  - UI: `https://canvas.iiit.ac.in/taxsyncfestage`
- Database: **IIIT Postgres** via `DATABASE_URL*` in `.env.prod`
  (example host `10.2.8.73:5432`, not Supabase pooler)

Deploy command on campus host:

```bash
cd Smart-Document-Management-System
test -f .env.prod || { echo "copy .env.prod.example first"; exit 1; }
./deploy-prod.sh
```

## What is NOT connected anymore

- Supabase pooler URLs are legacy comments in `docker-compose.override.yml`.
  Do not paste them into `.env.prod` for campus.
- GitHub runners cannot reach `10.2.8.x`. Do not put campus DATABASE_URL into
  GitHub secrets for CI tests.

## Split Taxsync repos

- Backend CI: `Taxsync_Backend` workflow tests the flat tree (`app/`, `tests/`)
- Frontend CI: `Taxsync_Frontend` workflow runs `npm ci` + `tsc` + `build`
- Prefer merging monorepo `main` first, then subtree-export backend / copy frontend

## Health checks after campus deploy

```bash
curl -fsS http://127.0.0.1:8025/api/health/live
curl -fsS https://canvas.iiit.ac.in/taxsyncbestage/api/health/live
curl -I https://canvas.iiit.ac.in/taxsyncfestage/
```
