FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update -o Acquire::Retries=3 -o Acquire::http::Timeout=30 && apt-get install -y --no-install-recommends \
    build-essential libpq-dev poppler-utils libmagic1 \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --default-timeout=300 --no-cache-dir --user -r requirements.txt \
 && pip uninstall -y opencv-python opencv-contrib-python 2>/dev/null; \
    pip install --default-timeout=300 --no-cache-dir --user opencv-python-headless \
 && rm -rf /root/.cache/pip

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update -o Acquire::Retries=3 -o Acquire::http::Timeout=30 && apt-get install -y --no-install-recommends \
    libpq-dev poppler-utils libmagic1 \
    libgl1 libglib2.0-0 \
    tesseract-ocr tesseract-ocr-ind && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY app/ app/
COPY db/ db/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers=1"]
