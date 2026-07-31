# Root Dockerfile for the Jenkins backend build (job Stage_Taxsync_BE), which
# runs `docker build .` at the repo root. The FastAPI app lives under backend/,
# so this builds from there. It mirrors backend/Dockerfile (used by local
# docker-compose via `build: ./backend`); keep the two in sync when backend
# system/Python deps change. Prod backend serves :8025 (frontend serves :8026).
FROM python:3.11-slim

# System dependencies for OCR (Tesseract) + OpenCV runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (from backend/)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code: contents of backend/ -> /app
COPY backend/ .

# Non-root user + writable dirs
RUN adduser --disabled-password --gecos '' appuser \
    && mkdir -p uploads models \
    && chown -R appuser:appuser /app
USER appuser

# Campus nginx publishes host :8025 -> container :8000 (see docker-compose.prod.yml).
# Do NOT set PORT=8025 here — Jenkins/campus jobs must map -p 8025:8000.
EXPOSE 8000

# start.sh runs uvicorn (and, when RENDER/COMBINED_MODE=true, a celery worker too)
CMD ["bash", "start.sh"]
