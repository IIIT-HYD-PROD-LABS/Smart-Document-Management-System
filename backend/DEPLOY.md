# Taxsync_Backend — config lives in `.env` (staging branch).

Product Labs owns the Dockerfile / Jenkins `docker build` + `docker run`.
This repo must keep a complete tracked **`.env`** on **`staging`** so the image
(or `--env-file .env`) has secrets.

Required keys (non-empty):

- `SECRET_KEY`, `DATABASE_URL`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (Google sign-in)
- `REDIS_URL` / `CELERY_*` → use host Redis e.g. `redis://10.2.8.73:6379/2`
  (not `redis://redis:...` unless Compose DNS exists)
- `FRONTEND_URL`, `BACKEND_URL` (OAuth redirects)
- `DB_ENFORCE_RLS=false` until `app_runtime` password is correct on campus

Google redirect URI:

`https://canvas.iiit.ac.in/taxsyncbestage/api/auth/callback/google`
