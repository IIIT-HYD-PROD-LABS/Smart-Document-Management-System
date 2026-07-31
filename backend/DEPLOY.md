# Taxsync_Backend — deploy with Dockerfile only

Push **`staging`** → Jenkins builds **`Dockerfile`** → runs container. No monorepo, no `deploy.sh`, no `--env-file`.

## Dockerfile contract

- **`COPY .env`** — tracked on `staging` (private repo); holds `SECRET_KEY`, `DATABASE_URL`, OAuth URLs.
- **`start.sh`** — reads `/app/.env` at container start.
- Build **fails** if `.env` is missing or incomplete.

## Jenkins / manual (same commands)

```bash
docker build -t tt0docker/stage_taxsync_be:${BUILD_NUMBER} .
docker rm -f smartdocs-backend 2>/dev/null || true
docker run -d --name smartdocs-backend --restart unless-stopped \
  -p 8025:8000 tt0docker/stage_taxsync_be:${BUILD_NUMBER}
```

## Verify

```bash
curl -fsS http://127.0.0.1:8025/api/health/live
curl -fsS https://canvas.iiit.ac.in/taxsyncbestage/api/health/live
```

Google OAuth redirect URI: `https://canvas.iiit.ac.in/taxsyncbestage/api/auth/callback/google`
