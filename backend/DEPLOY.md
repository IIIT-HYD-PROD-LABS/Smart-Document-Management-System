# Taxsync_Backend — campus deployment (Jenkins / Product Labs)

**Source of truth for API deploy:** [IIITH-Product-Labs/Taxsync_Backend](https://github.com/IIITH-Product-Labs/Taxsync_Backend) branch **`staging`**.

The Smart-Document-Management-System monorepo is for local development only — **do not** deploy from it on campus.

## Jenkins (`Stage_Taxsync_BE`)

| Step | What happens |
|------|----------------|
| Build | `docker build` from **Taxsync_Backend** root (`Dockerfile`, `COPY . .` includes tracked `.env`) |
| Run | **Must** start a container on **10.2.8.73** — build success alone does nothing |

## Run backend on 10.2.8.73

After Jenkins build, on the host:

```bash
git clone https://github.com/IIITH-Product-Labs/Taxsync_Backend.git
cd Taxsync_Backend && git checkout staging && git pull

chmod +x scripts/run-backend-campus.sh
./scripts/run-backend-campus.sh tt0docker/stage_taxsync_be:TAG
```

`TAG` = image tag from Jenkins. Script uses repo `.env` via `--env-file` and publishes **`8025:8000`**.

Manual equivalent:

```bash
docker rm -f smartdocs-backend 2>/dev/null || true
docker run -d --name smartdocs-backend --restart unless-stopped \
  --env-file ./.env \
  -p 8025:8000 \
  tt0docker/stage_taxsync_be:TAG
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
