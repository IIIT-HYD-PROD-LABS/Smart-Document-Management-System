FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN chmod +x start.sh

RUN adduser --disabled-password --gecos '' appuser \
    && mkdir -p uploads models \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["bash", "start.sh"]
