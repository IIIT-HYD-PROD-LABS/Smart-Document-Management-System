# Deployment Guide

Production deployment instructions for the Smart Document Management System.

---

## Prerequisites

| Requirement | Minimum Version |
|---|---|
| Docker | 24.x+ |
| Docker Compose | v2+ (`docker compose`, not `docker-compose`) |
| Git | 2.x+ |
| PostgreSQL | 14+ (Supabase Cloud recommended) |
| Domain name | Required for production HTTPS |

Hardware (minimum for a small team):
- 2 vCPU, 4 GB RAM, 40 GB disk
- Celery worker + OCR processing are memory-intensive; add RAM if processing large PDFs

---

## Environment Setup

### 1. Copy the example env file to the project root

```bash
cp backend/.env.example .env
```

> Docker Compose reads `.env` from the project root (next to `docker-compose.yml`).

### 2. Configure all required variables

Open `.env` and set every value. The table below describes each variable.

#### Required (app will not start without these)

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | JWT signing key. Must be 32+ chars with 10+ unique characters. | Generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DATABASE_URL` | PostgreSQL connection string. Use Supabase pooler (port 6543). | `postgresql://postgres.xxxx:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres` |

#### Application

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Display name | `Smart Document Management System` |
| `DEBUG` | Set `false` in production (disables `/docs` and `/redoc`). | `false` |

#### Security & Auth

| Variable | Description | Default |
|---|---|---|
| `ALLOWED_ORIGINS` | JSON array of allowed CORS origins. **Never use `*`**. | `["http://localhost:3000"]` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token lifetime. | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime. | `7` |
| `RATE_LIMIT_AUTH` | Rate limit on login/register. | `5/minute` |
| `RATE_LIMIT_UPLOAD` | Rate limit on file uploads. | `10/minute` |
| `RATE_LIMIT_DEFAULT` | Default API rate limit. | `60/minute` |

#### Redis & Celery

| Variable | Description | Default |
|---|---|---|
| `REDIS_PASSWORD` | Password for the Redis container. Used by docker-compose. | `smartdocs_redis_secret` |
| `REDIS_URL` | Redis connection string. Docker Compose overrides this automatically. | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker. Docker Compose overrides this automatically. | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result store. Docker Compose overrides this automatically. | `redis://localhost:6379/0` |

> When using Docker Compose, you only need to set `REDIS_PASSWORD`. The compose file wires `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` automatically using that password.

#### LLM / AI Extraction

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | One of: `gemini`, `ollama`, `anthropic`, `openai`, `local` (regex fallback). | `local` |
| `GEMINI_API_KEY` | Required if `LLM_PROVIDER=gemini`. Get from Google AI Studio. | (empty) |
| `ANTHROPIC_API_KEY` | Required if `LLM_PROVIDER=anthropic`. | (empty) |
| `OPENAI_API_KEY` | Required if `LLM_PROVIDER=openai`. | (empty) |
| `OLLAMA_BASE_URL` | Ollama server URL. Docker uses `http://host.docker.internal:11434`. | `http://localhost:11434` |
| `LLM_MODEL` | Model name for the chosen provider. | Provider default (e.g. `gemini-2.0-flash`) |
| `LLM_TIMEOUT_SECONDS` | Timeout for LLM API calls. | `60` |

#### File Storage

| Variable | Description | Default |
|---|---|---|
| `UPLOAD_DIR` | Local upload directory (inside container). | `./uploads` |
| `MAX_FILE_SIZE_MB` | Max upload file size. | `50` |
| `USE_S3` | Set `true` to use AWS S3 instead of local storage. | `false` |
| `AWS_ACCESS_KEY_ID` | AWS credentials (if `USE_S3=true`). | (empty) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials (if `USE_S3=true`). | (empty) |
| `AWS_REGION` | AWS region. | `ap-south-1` |
| `S3_BUCKET_NAME` | S3 bucket name. | `smart-docs-bucket` |

#### OAuth SSO (optional)

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID. | (empty) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret. | (empty) |
| `MICROSOFT_CLIENT_ID` | Microsoft OAuth client ID. | (empty) |
| `MICROSOFT_CLIENT_SECRET` | Microsoft OAuth client secret. | (empty) |
| `MICROSOFT_TENANT_ID` | Azure AD tenant. | `common` |
| `FRONTEND_URL` | Frontend URL for OAuth redirects. | `http://localhost:3000` |
| `BACKEND_URL` | Backend URL for OAuth callbacks. | `http://localhost:8000` |

#### Logging

| Variable | Description | Default |
|---|---|---|
| `LOG_LEVEL` | Python log level. | `INFO` |
| `LOG_JSON_FORMAT` | Emit structured JSON logs (recommended for production). | `true` |

---

## Option A: Docker Self-Hosted (VPS / Server)

This is the recommended deployment method. All services (backend, Celery worker, Redis, frontend) run in Docker containers orchestrated by Docker Compose.

### Step 1 -- Clone the repository

```bash
git clone https://github.com/your-org/Smart-Document-Management-System.git
cd Smart-Document-Management-System
```

### Step 2 -- Configure environment

```bash
cp backend/.env.example .env

# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
# Paste the output as SECRET_KEY in .env

# Edit .env with your database URL, domain, Redis password, etc.
nano .env
```

Minimum values to change in `.env`:
```
SECRET_KEY=<generated-key>
DATABASE_URL=postgresql://postgres.xxxx:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
DEBUG=false
ALLOWED_ORIGINS=["https://your-domain.com"]
REDIS_PASSWORD=<strong-random-password>
LLM_PROVIDER=gemini
GEMINI_API_KEY=<your-key>
FRONTEND_URL=https://your-domain.com
BACKEND_URL=https://api.your-domain.com
```

### Step 3 -- Build and start all services

```bash
docker compose up -d --build
```

This starts four containers:
| Container | Port | Purpose |
|---|---|---|
| `smartdocs-redis` | internal only | Message broker + cache |
| `smartdocs-backend` | 8000 | FastAPI API server |
| `smartdocs-celery` | none | Background task worker (OCR, ML, LLM) |
| `smartdocs-frontend` | 3000 | Next.js web UI |

### Step 4 -- Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### Step 5 -- Verify health

```bash
curl http://localhost:8000/api/health
# Expected: {"status":"healthy","version":"1.0.0"}
```

Check all containers are healthy:
```bash
docker compose ps
```

### Step 6 -- Create the first admin user

Register via the API or the frontend at `http://localhost:3000`. The first registered user can be promoted to admin.

### Step 7 -- Set up a reverse proxy for HTTPS

You need a reverse proxy in front of Docker to terminate TLS. Choose one:

#### Option: Caddy (simplest -- automatic HTTPS)

Install Caddy on the host, then create `/etc/caddy/Caddyfile`:

```
your-domain.com {
    reverse_proxy localhost:3000
}

api.your-domain.com {
    reverse_proxy localhost:8000
}
```

```bash
sudo systemctl restart caddy
```

Caddy automatically obtains and renews Let's Encrypt certificates.

#### Option: Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Use certbot to obtain certificates:
```bash
sudo certbot --nginx -d your-domain.com -d api.your-domain.com
```

### Step 8 -- Update frontend API URL

In `.env` or in `docker-compose.yml`, set the frontend's `NEXT_PUBLIC_API_URL` to your production backend URL:

```yaml
# docker-compose.yml override
frontend:
  environment:
    NEXT_PUBLIC_API_URL: https://api.your-domain.com
```

Then rebuild the frontend:
```bash
docker compose up -d --build frontend
```

---

## Option B: Render.com

Render can host each component as a separate service.

### 1. Backend -- Web Service

- **Runtime:** Docker
- **Root directory:** `backend`
- **Dockerfile path:** `./Dockerfile`
- **Environment variables:** Set all required vars from the table above.
- **Health check path:** `/api/health`
- Set `DATABASE_URL` to your Supabase pooler connection string.
- Set `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` to your Render Redis instance URL.

### 2. Celery Worker -- Background Worker

- **Runtime:** Docker
- **Root directory:** `backend`
- **Dockerfile path:** `./Dockerfile`
- **Start command override:**
  ```
  celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2 --pool=prefork --max-memory-per-child=512000
  ```
- **Environment variables:** Same as backend (copy all).

### 3. Redis -- Render Redis addon

- Create a Redis instance in Render.
- Copy the internal connection URL.
- Set `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` on both the backend and worker to this URL.

### 4. Frontend -- Static Site or Web Service

- **Runtime:** Node (or Docker)
- **Root directory:** `frontend`
- **Build command:** `npm ci && npm run build`
- **Start command:** `npm start`
- **Environment variable:** `NEXT_PUBLIC_API_URL=https://your-backend.onrender.com`

### 5. Run migrations

Use Render's shell or a one-off job:
```bash
cd backend && alembic upgrade head
```

---

## Database Setup (Supabase)

### 1. Create a Supabase project

Go to [supabase.com](https://supabase.com), create a new project, and note the database password.

### 2. Get the connection string

In your Supabase dashboard, go to **Settings > Database > Connection string > URI**.

**Use the pooler host (port 6543), not the direct connection (port 5432):**

```
postgresql://postgres.your-project-ref:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

Why the pooler?
- Handles connection limits for you (Supabase free tier limits direct connections).
- Required when multiple services (backend + Celery worker) connect simultaneously.

### 3. Enable required extensions

Connect to your Supabase database via the SQL Editor and run:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

This enables trigram-based fuzzy search used by the document search feature.

### 4. Run migrations

```bash
docker compose exec backend alembic upgrade head
```

### 5. Password expiry

Supabase database passwords can expire. If you see authentication errors after a period of inactivity, reset the password in the Supabase dashboard (**Settings > Database > Database password**) and update `DATABASE_URL` in your `.env`.

---

## Post-Deployment Checklist

Run through this list after every deployment:

- [ ] **Health endpoint returns 200:**
  ```bash
  curl -s https://api.your-domain.com/api/health | grep healthy
  ```

- [ ] **All containers are running and healthy:**
  ```bash
  docker compose ps
  ```

- [ ] **Register the first admin user** via the frontend or API.

- [ ] **Test document upload and processing:**
  1. Upload a PDF or image through the frontend.
  2. Confirm the document appears in the dashboard.
  3. Check that ML classification and OCR completed (document should have extracted text and a predicted category).

- [ ] **Verify Celery worker is processing tasks:**
  ```bash
  docker compose logs celery_worker --tail 20
  ```
  Look for `Task accepted` and `Task succeeded` messages.

- [ ] **Check security headers:**
  ```bash
  curl -sI https://api.your-domain.com/api/health | grep -iE "strict-transport|x-frame|x-content-type|content-security"
  ```
  Expected headers: `Strict-Transport-Security`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`.

- [ ] **Confirm Swagger docs are disabled:** `https://api.your-domain.com/docs` should return 404 when `DEBUG=false`.

- [ ] **Set up monitoring and alerts:**
  - Monitor `/api/health` endpoint with an uptime checker (e.g., UptimeRobot, Render health checks).
  - Set up log aggregation (Docker logs, or ship JSON logs to Datadog/Grafana/etc.).
  - Monitor disk usage for the `backend_uploads` volume.

---

## Updating

### Pull latest code and rebuild

```bash
cd Smart-Document-Management-System
git pull origin main
docker compose up -d --build
```

### Run new migrations (if any)

```bash
docker compose exec backend alembic upgrade head
```

### Verify after update

```bash
curl -s http://localhost:8000/api/health
docker compose ps
docker compose logs --tail 20
```

### Rollback

If something goes wrong:
```bash
# Revert to previous commit
git checkout <previous-commit-hash>
docker compose up -d --build
docker compose exec backend alembic downgrade -1
```

---

## Troubleshooting

### Container won't start

```bash
docker compose logs backend --tail 50
```

Common causes:
- **`SECRET_KEY must not be empty`** -- Set a strong `SECRET_KEY` in `.env`.
- **`ALLOWED_ORIGINS must not contain '*'`** -- Use explicit origins, e.g. `["https://your-domain.com"]`.
- **Database connection refused** -- Check `DATABASE_URL`. Use the Supabase pooler host (port 6543).

### Celery worker not processing

```bash
docker compose logs celery_worker --tail 50
```

- Verify Redis is healthy: `docker compose exec redis redis-cli -a $REDIS_PASSWORD ping`
- Check that `CELERY_BROKER_URL` is correct.

### OCR not working

- Tesseract is pre-installed in the Docker image. No host installation needed.
- For poor OCR results, check image quality and resolution.

### Database migration errors

```bash
# Check current migration state
docker compose exec backend alembic current

# If the database was created without Alembic (e.g., via create_all), stamp it:
docker compose exec backend alembic stamp head

# Then apply future migrations normally:
docker compose exec backend alembic upgrade head
```

### Frontend can't reach backend

- Verify `NEXT_PUBLIC_API_URL` points to the backend URL accessible from the browser (not internal Docker network).
- Check CORS: `ALLOWED_ORIGINS` must include the frontend's origin.
