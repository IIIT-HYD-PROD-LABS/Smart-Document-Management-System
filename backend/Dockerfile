FROM python:3.11-slim

# Install system dependencies for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application + tracked production defaults (private repo). Host .env.prod overrides
# duplicate keys when compose lists both env files.
COPY . .

RUN chmod +x start.sh

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

# Create necessary directories with correct ownership
RUN mkdir -p uploads models && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=10s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live')"

# Run server (start.sh runs combined celery+uvicorn when RENDER=true)
CMD ["bash", "start.sh"]
