# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# Order Service Dockerfile
# Build arg VERSION is baked into the image as APP_VERSION env var and is
# surfaced via the /health endpoint and the Prometheus `app_info` metric.
# ─────────────────────────────────────────────────────────────────────────────

ARG VERSION=dev

# ── Stage 1: dependency build ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ARG VERSION
ENV APP_VERSION=${VERSION}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime OS deps only (libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/
COPY seed.py .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
