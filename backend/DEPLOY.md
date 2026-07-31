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
# MUST be 8025:8000 (host:container). 8025:8025 causes public 502.
docker run -d --name smartdocs-backend --restart unless-stopped \
  -p 8025:8000 \
  --add-host=host.docker.internal:host-gateway \
  tt0docker/stage_taxsync_be:${BUILD_NUMBER}
```

## Verify

```bash
docker logs smartdocs-backend --tail 30
# Expect: GOOGLE_OAUTH=configured  (not missing)
curl -fsS http://127.0.0.1:8025/api/health/live
curl -fsS https://canvas.iiit.ac.in/taxsyncbestage/api/health/live
```

Google OAuth redirect URI: `https://canvas.iiit.ac.in/taxsyncbestage/api/auth/callback/google`

## `.env` must have (tracked on staging)

| Key | Campus value |
|-----|----------------|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Non-empty (login) |
| `REDIS_URL` | `redis://10.2.8.73:6379/2` — **not** `redis://redis:...` |
| `DATABASE_URL` | Real `taxsync_app` password — **not** `CHANGE_ME` |
| `DB_ENFORCE_RLS` | `false` until `app_runtime` password is correct |
