# Taxsync_Backend — campus deployment (Jenkins / Product Labs)

**Source of truth for API deploy:** [IIITH-Product-Labs/Taxsync_Backend](https://github.com/IIITH-Product-Labs/Taxsync_Backend) branch **`staging`**.

Push to **`staging`** autotriggers Jenkins. The job must **build and run** the container (not build-only).

## Autotrigger checklist (Product Labs)

1. **Checkout** includes tracked **`.env`** (`SECRET_KEY`, `DATABASE_URL`, OAuth URLs).
2. **Build:** `docker build -t tt0docker/stage_taxsync_be:$BUILD_NUMBER .`  
   Build fails if `.env` is missing from the repo.
3. **Deploy (required):** after build, run **`./deploy.sh`** on **10.2.8.73**  
   - Starts `smartdocs-backend` with `--env-file .env` and **`-p 8025:8000`**
   - Or use root **`Jenkinsfile`** (build + deploy stages).

If deploy step is skipped, campus API stays **502** and logs show **`SECRET_KEY is not set`**.

```bash
chmod +x deploy.sh scripts/run-backend-campus.sh
./deploy.sh
```

Environment variables for `deploy.sh`:

| Variable | Default | Meaning |
|----------|---------|---------|
| `DOCKER_IMAGE` | `tt0docker/stage_taxsync_be` | Image name without tag |
| `BUILD_NUMBER` | `latest` | Image tag |
| `SKIP_DOCKER_BUILD` | `0` | Set `1` if image already built |

## Manual run (same as autotrigger deploy stage)

```bash
git checkout staging && git pull
./scripts/run-backend-campus.sh tt0docker/stage_taxsync_be:TAG
```

## Verify

```bash
curl -fsS http://127.0.0.1:8025/api/health/live
curl -fsS https://canvas.iiit.ac.in/taxsyncbestage/api/health/live
```

Logs should show `TaxSync backend boot:` and `GOOGLE_OAUTH=configured`.  
If you see `ERROR: SECRET_KEY is not set`, the container was started **without** `--env-file ./.env` or an image built without `.env` in context.

## Google OAuth (Google Cloud Console)

Authorized redirect URI:

`https://canvas.iiit.ac.in/taxsyncbestage/api/auth/callback/google`

Must match `BACKEND_URL` in `.env`.

## Ports

| Host | Container | Service |
|------|-----------|---------|
| 8025 | 8000 | FastAPI (nginx → `/taxsyncbestage`) |

Redis/Celery workers are separate campus services; login and health only need this API container.
