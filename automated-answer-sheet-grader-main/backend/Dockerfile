FROM python:3.12-slim

# Tesseract OCR engine
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    ENVIRONMENT=production DATA_DIR=/data TESSERACT_CMD=/usr/bin/tesseract

WORKDIR /app
COPY requirements.txt requirements-semantic.txt ./
# Set --build-arg WITH_SEMANTIC=true to include SBERT paraphrase matching (adds ~GBs via PyTorch)
ARG WITH_SEMANTIC=false
RUN pip install -r requirements.txt \
    && if [ "$WITH_SEMANTIC" = "true" ]; then pip install -r requirements-semantic.txt; fi

COPY *.py ./
RUN useradd --create-home app && mkdir /data && chown app /data
USER app
VOLUME /data

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# One worker: SQLite + in-memory login rate limiter. --proxy-headers so the limiter sees real client IPs.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
