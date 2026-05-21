# Troubleshooting Guide

Quick-reference solutions for common Smart Document Management System issues. All commands assume you are in the project root (`Smart-Document-Management-System/`).

---

## Container Issues

### Backend won't start: "SECRET_KEY must not be empty"

**Problem:** The `.env` file is missing `SECRET_KEY` or it is set to an empty string. The backend validates this on startup and refuses to run without it.

**Solution:**
```bash
# Generate a secure key and add it to .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Paste the output as SECRET_KEY=<value> in your .env file, then restart
docker compose down && docker compose up -d
```

---

### Backend won't start: "SECRET_KEY has too few unique characters"

**Problem:** The `SECRET_KEY` value has fewer than 10 unique characters (e.g., all the same character, all digits, or a simple placeholder like `12345678901234567890123456789012`). The backend rejects low-entropy keys.

**Solution:**
```bash
# Replace your SECRET_KEY with a properly random value
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Update SECRET_KEY in .env with the generated value, then restart
docker compose restart backend celery_worker
```

Also rejected: default insecure values like `changeme`, `secret`, `test`, `password`. Use a truly random key.

---

### Database connection refused

**Problem:** The backend logs `OperationalError: could not connect to server: Connection refused` on startup. The PostgreSQL database is unreachable.

**Solution:**
1. Verify `DATABASE_URL` in `.env` is correct (host, port, username, password, database name).
2. If using Supabase, confirm the project is not paused -- visit the Supabase dashboard and restore it if needed.
3. If using the Supabase pooler (port `6543`), ensure you are using the **Transaction mode** connection string, not the Direct connection.
4. Test connectivity from inside the container:
   ```bash
   docker compose exec backend python -c "from app.database import engine; engine.connect(); print('OK')"
   ```
5. If the database is remote, check that your IP is not blocked by firewall rules.

---

### Supabase password expired / rotated

**Problem:** Login or database operations fail after Supabase rotates the database password. Symptoms include:
- `FATAL: password authentication failed for user "postgres"` in Supabase's Postgres logs (Dashboard > Logs > Postgres)
- Supabase MCP returns `"Database authentication failed. Try refreshing the page or reinput your current password in Settings > Database > Reset database password"`
- Backend container starts but stays `(unhealthy)`, with uvicorn logs stuck at `Waiting for application startup.`

**Why this fails subtly:** The healthcheck error inside the container is `ConnectionRefusedError: [Errno 111] Connection refused` -- but that's the *healthcheck itself* failing to reach `localhost:8000` because uvicorn never bound the port. The root cause is the FastAPI lifespan startup blocking on the bad DB credential.

**Solution:**
1. Go to Supabase Dashboard > Project Settings > Database > **Reset database password**. Save the new password in your password manager *before* navigating away (Supabase only shows it once).
2. Update **all three** `DATABASE_URL` lines in `docker-compose.override.yml` (services: `backend`, `celery_worker`, `compliance_worker`) with the new password. The override file is the source of truth for the docker stack; `.env` is secondary.
3. Leave `DATABASE_URL_RUNTIME` (`app_runtime`) and `DATABASE_URL_MIGRATOR` (`app_migrator`) alone unless their logins also fail -- those are app-managed roles created by migration `0017_db_roles` with stable dev passwords, not the Supabase project password.
4. Verify with MCP from outside your network:
   ```
   # Supabase MCP > execute_sql > SELECT 1
   # If this returns 1, the new password is live server-side.
   ```
5. Force-recreate the backend so the new env vars take effect:
   ```bash
   docker compose up -d --force-recreate backend celery_worker compliance_worker
   ```

---

### Backend (unhealthy) / "dependency failed to start" — TimeoutError on port 5432

**Problem:** `docker compose start` or `docker compose up` fails with `dependency failed to start: container smartdocs-backend is unhealthy`. The backend container is `Up (unhealthy)`, uvicorn logs are stuck at `Waiting for application startup.`, and probing the Supabase pooler from inside the container gives `TimeoutError` (not `Connection refused`).

**Cause:** Some networks silently drop outbound TCP on Postgres ports (5432/6543). Common offenders: ERNET (Indian education/research networks, `14.139.0.0/16`), corporate VPNs with egress filtering, several Indian residential ISPs. Distinguishing signal: connections to the *same* Supabase pooler IP on port `443` succeed in <200ms, but `5432` times out at 4-8s with no RST.

**Diagnostic probe:**
```bash
# Run on the host AND inside the container -- both should show the same result.
python3 -c "
import socket, time
for ip in ['3.111.225.200','3.109.171.244','13.200.110.68']:
    s=socket.socket(); s.settimeout(5); t=time.time()
    try: s.connect((ip,5432)); print('OK  ', ip, round(time.time()-t,2),'s')
    except Exception as e: print('FAIL', ip, type(e).__name__, str(e)[:50])
    finally: s.close()
"
# TimeoutError -> port-level block (this section)
# Connection refused -> server unreachable (different problem)
```

**Solution:** Tunnel the DB traffic over UDP/443 or TCP/443 so the egress filter can't see port 5432.
1. **Cloudflare WARP** (free, fastest, no account):
   ```bash
   curl https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
   echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
   sudo apt update && sudo apt install -y cloudflare-warp
   warp-cli registration new && warp-cli connect
   ```
2. **Any commercial VPN** (ProtonVPN/Mullvad/NordVPN) — pick a non-India exit.
3. **SSH tunnel via a cloud VM you control:**
   ```bash
   ssh -L 15432:aws-1-ap-south-1.pooler.supabase.com:5432 user@your-vm -N -f
   # Then point docker-compose.override.yml DATABASE_URL at host.docker.internal:15432
   ```
4. **Phone hotspot** (quick test if your carrier doesn't also block 5432).

After the tunnel is up, the existing containers' next healthcheck (every 15s) auto-flips the backend to `healthy` -- no restart needed. Confirm with `docker compose ps`.

**This issue often stacks with "Supabase password expired" above.** If both apply, fix the password first (verifiable via Supabase MCP without touching your network), then enable the tunnel.

---

### Redis connection errors on startup

**Problem:** Backend or Celery worker logs show `ConnectionError: Error connecting to Redis` or the health check fails with Redis-related errors.

**Solution:**
1. Ensure the `redis` service is running: `docker compose ps redis`
2. Verify `REDIS_PASSWORD` in `.env` matches the password used in `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`.
3. Inside Docker, Redis is at hostname `redis`, not `localhost`. The URLs should look like:
   ```
   REDIS_URL=redis://:smartdocs_redis_secret@redis:6379/0
   ```
4. Restart Redis: `docker compose restart redis`

---

## Processing Issues

### Celery worker not processing documents

**Problem:** Documents stay in "pending" status. The Celery worker container is running but not picking up tasks.

**Solution:**
1. Check the worker logs: `docker compose logs celery_worker --tail=50`
2. Verify the worker is connected to Redis:
   ```bash
   docker compose exec celery_worker celery -A app.tasks.celery_app inspect ping
   ```
3. If it reports no workers, restart: `docker compose restart celery_worker`
4. Ensure `CELERY_BROKER_URL` in `.env` uses `redis` (not `localhost`) as the hostname when running in Docker.
5. Check if the worker is OOM-killed (exits silently): `docker compose ps` -- if the celery_worker status shows "exited", increase Docker memory limits or reduce `--concurrency` in `docker-compose.yml`.

---

### OCR returns empty text

**Problem:** Uploaded images are processed successfully but `extracted_text` is empty. The document gets classified as "unknown" with 0.0 confidence.

**Solution:**
1. Verify Tesseract is installed in the container (it should be -- the Dockerfile installs `tesseract-ocr`):
   ```bash
   docker compose exec backend tesseract --version
   ```
2. If the image is very small (< 800px height), OCR may struggle. Upload higher-resolution scans.
3. Check that the image is not corrupted -- open it locally to verify.
4. For non-English documents, install additional Tesseract language packs by adding to `backend/Dockerfile`:
   ```dockerfile
   RUN apt-get update && apt-get install -y tesseract-ocr-<lang>
   ```
5. Check processing logs: `docker compose logs celery_worker --tail=100 | grep ocr`

---

### Documents stuck in "processing" status

**Problem:** Documents remain in "processing" indefinitely and never complete or fail.

**Solution:**
1. Check if the Celery worker is still running: `docker compose ps celery_worker`
2. If the worker crashed mid-task, the document status stays stuck. Reset it manually:
   ```bash
   docker compose exec backend python -c "
   from app.database import SessionLocal
   from app.models.document import Document, DocumentStatus
   db = SessionLocal()
   stuck = db.query(Document).filter(Document.status == DocumentStatus.PROCESSING).all()
   for doc in stuck:
       doc.status = DocumentStatus.PENDING
   db.commit()
   print(f'Reset {len(stuck)} documents')
   "
   ```
3. Restart the worker to reprocess: `docker compose restart celery_worker`
4. The task has a hard time limit of 600 seconds (10 minutes). Very large files may exceed this -- check `docker compose logs celery_worker` for `SoftTimeLimitExceeded`.

---

## Authentication Issues

### OAuth callback fails with "Invalid OAuth state"

**Problem:** After authenticating with Google or Microsoft, the callback returns HTTP 400 with `"Invalid OAuth state -- possible CSRF"`.

**Solution:**
1. The OAuth state is stored in an `oauth_state` cookie. If the browser blocks or loses the cookie, validation fails.
2. Ensure `BACKEND_URL` in `.env` matches the actual URL the browser uses (e.g., `http://localhost:8000`). A mismatch causes the redirect URI to differ from what the provider expects.
3. Ensure `FRONTEND_URL` in `.env` is correct (e.g., `http://localhost:3000`).
4. If testing from a different machine or using a tunnel (ngrok), update both `BACKEND_URL` and `FRONTEND_URL` accordingly.
5. Check that cookies are not blocked by browser privacy settings or extensions.
6. The state cookie has a 10-minute lifetime -- if the user takes too long to authenticate, it expires. Try again promptly.

---

### Rate limit errors (429 Too Many Requests)

**Problem:** API calls fail with HTTP 429. This is most common on auth endpoints (limited to 5 requests/minute by default).

**Solution:**
1. Wait for the rate limit window to reset (check the `Retry-After` response header).
2. To adjust limits, edit these values in `.env`:
   ```
   RATE_LIMIT_AUTH=5/minute
   RATE_LIMIT_UPLOAD=10/minute
   RATE_LIMIT_DEFAULT=60/minute
   ```
3. Restart after changes: `docker compose restart backend`
4. If Redis is down, rate limits fall back to in-memory storage and are per-worker only. This can cause inconsistent enforcement -- fix Redis first (see "Redis connection errors" above).

---

## Upload Issues

### File upload fails with "File type not allowed"

**Problem:** The upload endpoint returns HTTP 400 with `"File type '.xyz' not allowed"`.

**Solution:**
The backend only accepts these file types: `pdf`, `png`, `jpg`, `jpeg`, `tiff`, `bmp`, `docx`.

1. Rename the file to use a supported extension if the content format is actually supported (e.g., `.jpe` to `.jpg`).
2. To add new file types, update `ALLOWED_EXTENSIONS` in `backend/app/config.py` and add the corresponding magic byte signature in `backend/app/services/storage_service.py` (`_MAGIC_SIGNATURES` dict). Rebuild the container:
   ```bash
   docker compose build backend && docker compose up -d
   ```

---

### File upload fails with "File content does not match declared type"

**Problem:** The upload endpoint returns HTTP 400 with `"File content does not match declared type '.pdf'"` even though the file appears valid.

**Solution:**
The backend validates file content against magic byte signatures. This error means the file's actual bytes do not match its extension.

1. The file may be renamed incorrectly (e.g., a `.png` renamed to `.pdf`). Check the actual file format.
2. Some export tools produce non-standard headers. Try re-exporting or re-saving the file.
3. For DOCX files, the magic bytes check expects a ZIP header (`PK\x03\x04`) since DOCX is a ZIP archive. A corrupted or password-protected DOCX may fail this check.
4. Files with 0 bytes will always fail -- ensure the file is not empty.

---

## Build Issues

### Docker build fails on Apple M1/ARM

**Problem:** `docker compose build` fails with architecture-related errors on Apple Silicon (M1/M2/M3) Macs, often from Python packages with native extensions (e.g., `numpy`, `opencv-python-headless`).

**Solution:**
```bash
docker compose build --build-arg BUILDPLATFORM=linux/amd64
# Or set the platform in docker-compose.yml for each service:
#   platform: linux/amd64
```
Alternatively, use Docker Desktop with Rosetta emulation enabled (Settings > General > Use Rosetta).

---

### Frontend build fails with TypeScript errors

**Problem:** `docker compose build frontend` fails during `npm run build` with TypeScript compilation errors.

**Solution:**
1. Check the error output for the specific file and line. Common causes:
   - Missing type definitions: run `npm install` locally in `frontend/` to ensure `node_modules` is complete.
   - Strict mode violations: the project uses `"strict": true` in `tsconfig.json`. Fix type errors rather than disabling strict mode.
2. If the error references `.next/types`, clear the build cache:
   ```bash
   rm -rf frontend/.next
   docker compose build --no-cache frontend
   ```
3. Ensure `node_modules` is not being copied into the Docker build context by checking that `frontend/.dockerignore` includes `node_modules`. The Dockerfile runs `npm ci` to install dependencies cleanly.

---

### Alembic "Can't locate revision"

**Problem:** Running `alembic upgrade head` fails with `Can't locate revision identified by 'xxxx'` because the database's migration history references a revision that no longer exists in the `alembic/versions/` directory.

**Solution:**
```bash
# Stamp the database to the current head (marks all migrations as applied)
docker compose exec backend alembic stamp head
# Then run any pending migrations
docker compose exec backend alembic upgrade head
```
If the schema is out of sync after stamping, you may need to manually verify tables match the models, or recreate the database from scratch for development environments.

---

### Alembic "Target database is not up to date"

**Problem:** Running `alembic revision --autogenerate` fails with `Target database is not up to date` because there are unapplied migrations.

**Solution:**
```bash
# Apply all pending migrations first
docker compose exec backend alembic upgrade head
# Then generate the new migration
docker compose exec backend alembic revision --autogenerate -m "description"
```

---

## LLM / AI Extraction Issues

### AI extraction returns "skipped" for all documents

**Problem:** Documents process successfully but `ai_extraction_status` is always "skipped" and no AI summary is generated.

**Solution:**
1. AI extraction requires at least 20 characters of extracted text. If OCR or text extraction yields very little text, AI extraction is skipped by design.
2. Check `LLM_PROVIDER` in `.env`. Valid values: `ollama`, `gemini`, `anthropic`, `openai`, or `local` (regex fallback only).
3. If using `ollama`, ensure Ollama is running on your host machine and accessible at `OLLAMA_BASE_URL` (default: `http://host.docker.internal:11434` inside Docker).
4. If using `gemini`, `anthropic`, or `openai`, verify the corresponding API key is set in `.env` (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY`).
5. Check Celery worker logs for `ai_extraction_failed` entries:
   ```bash
   docker compose logs celery_worker | grep ai_extraction
   ```

---

## General Tips

- **View all container statuses:** `docker compose ps`
- **View logs for a service:** `docker compose logs <service> --tail=100 -f`
- **Rebuild after code changes:** `docker compose build && docker compose up -d`
- **Full reset (destroys data):** `docker compose down -v && docker compose up -d --build`
- **Check backend health:** `curl http://localhost:8000/api/health`
- **Check API docs (requires DEBUG=true):** Open `http://localhost:8000/docs` in a browser
