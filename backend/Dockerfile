# syntax=docker/dockerfile:1.7
#
# Tuki-Medic backend — multi-stage production image.
#
# Build context: project root.   Build:   docker build -f backend/Dockerfile -t tuki-medic-backend:latest .
# Run with the rest of the stack: docker compose up backend
#
# Stage 1 (builder): install Poetry + project deps with --no-dev. Caches the
# huge resolution step on a separate layer so app-code changes don't bust it.
# Stage 2 (runtime): copies the resolved virtualenv + the source. Adds the
# system libraries the OCR pipeline needs (tesseract, poppler) and runs as a
# non-root user. Listens on 8000.

ARG PYTHON_VERSION=3.14
ARG POETRY_VERSION=2.3.4

# ---------------------------------------------------------------------------
# 1. Builder
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ARG POETRY_VERSION
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1

# Build deps for any wheels that need to compile (psycopg, pgvector, pillow…)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Resolve deps in their own layer so changing app/ doesn't re-trigger this.
COPY backend/pyproject.toml backend/poetry.lock ./
RUN poetry install --no-root --without dev

# ---------------------------------------------------------------------------
# 2. Runtime
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO

# OCR + PDF rasterisation system deps (no toolchain — runtime only).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        tesseract-ocr \
        tesseract-ocr-spa \
        tesseract-ocr-eng \
        poppler-utils \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the resolved virtualenv from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# App source — copied last so iterating on code doesn't invalidate deps cache.
COPY backend/app /app/app
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY backend/data /app/data

# Drop privileges.
RUN groupadd -r medagent && useradd -r -g medagent -d /app medagent \
    && chown -R medagent:medagent /app
USER medagent

EXPOSE 8000

# k8s/docker compose hits this — see app/main.py /health/ready
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Default command — workers tuned for typical 2-core deployment. Override
# via CMD or entrypoint args in docker compose / k8s as needed.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
