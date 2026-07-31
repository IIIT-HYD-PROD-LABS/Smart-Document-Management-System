# =============================================================================
# Taxsync_Backend — campus deploy uses THIS FILE ONLY (IIITH Product Labs).
# Branch: staging (tracked .env is copied into the image at build time).
#
#   docker build -t tt0docker/stage_taxsync_be:${BUILD_NUMBER:-latest} .
#   docker rm -f smartdocs-backend 2>/dev/null || true
#   docker run -d --name smartdocs-backend --restart unless-stopped \
#     -p 8025:8000 tt0docker/stage_taxsync_be:${BUILD_NUMBER:-latest}
#
# MUST map host 8025 → container 8000 (not 8025:8025). Public 502 = wrong map
# or container down. Logs must show GOOGLE_OAUTH=configured and Redis host IP.
#
# No --env-file, no deploy scripts: secrets live in /app/.env inside the image.
# Host 8025 → container 8000 (uvicorn). Public: canvas.iiit.ac.in/taxsyncbestage
# =============================================================================

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production config (SECRET_KEY, DATABASE_URL, OAuth, Redis, …) — required in git on staging.
COPY .env .env
RUN test -s .env \
    && grep -q '^SECRET_KEY=.' .env \
    && grep -q '^DATABASE_URL=.' .env \
    || (echo "ERROR: commit .env on staging before docker build." && exit 1)

COPY . .

RUN chmod +x start.sh

RUN adduser --disabled-password --gecos '' appuser \
    && mkdir -p uploads models \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=10s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live')"

CMD ["bash", "start.sh"]
