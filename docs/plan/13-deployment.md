# 13 — Infraestructura y Deployment

## 1. Entornos

| Entorno | Propósito | Infra |
|---------|----------|-------|
| **Local** | Desarrollo | Docker Compose |
| **Staging** | Testing + QA | Railway / Fly.io |
| **Production** | Usuarios reales | Railway / Fly.io → K8s |

## 2. Docker Compose (desarrollo local)

```yaml
# docker-compose.yml
version: "3.9"

services:
  # Frontend
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXT_PUBLIC_WS_URL=ws://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend

  # Backend
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://medagent:medagent@postgres:5432/medagent
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./backend:/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  # PostgreSQL + pgvector
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=medagent
      - POSTGRES_PASSWORD=medagent
      - POSTGRES_DB=medagent
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medagent"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  # MinIO (S3-compatible storage)
  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

## 3. Dockerfiles

### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema (OCR)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN pip install poetry
RUN poetry config virtualenvs.create false

# Copiar dependencias
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-root

# Copiar código
COPY . .

# Ejecutar migraciones y arrancar
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

FROM node:20-alpine AS runner
WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
```

## 4. CI/CD (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint-and-type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      # Frontend
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: cd frontend && pnpm install && pnpm lint && pnpm type-check
      
      # Backend
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: cd backend && pip install poetry && poetry install && poetry run ruff check . && poetry run mypy .

  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: |
          cd backend
          pip install poetry
          poetry install
          poetry run pytest --cov=app --cov-report=xml
      
  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: cd frontend && pnpm install && pnpm test

  safety-tests:
    runs-on: ubuntu-latest
    needs: [test-backend]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: |
          cd backend
          pip install poetry
          poetry install
          poetry run pytest tests/safety/ -v --tb=long
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## 5. Deploy en Railway (MVP)

```
railway/
├── frontend (Next.js service)
│   └── Connected to GitHub, auto-deploy on push
├── backend (FastAPI service)
│   └── Connected to GitHub, auto-deploy on push
├── postgresql (Railway managed)
│   └── pgvector extension enabled
├── redis (Railway managed)
└── volumes
    └── /data (for MinIO or use Railway's S3-compatible storage)
```

### Variables de entorno (Railway)

```env
# Backend
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
S3_ENDPOINT=...
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=medagent-docs
JWT_SECRET=...
CORS_ORIGINS=https://medagent.app

# Frontend
NEXT_PUBLIC_API_URL=https://api.medagent.app
NEXT_PUBLIC_WS_URL=wss://api.medagent.app
```

## 6. Monitoring

### Sentry (errores)
```python
# backend/app/main.py
import sentry_sdk
sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
```

### LangSmith (tracing de agentes)
```python
# backend/app/config.py
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"] = "medagent-production"
```

### Health checks

```python
@app.get("/health")
async def health():
    checks = {
        "api": "ok",
        "database": await check_db(),
        "redis": await check_redis(),
        "storage": await check_s3(),
    }
    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
```

## 7. Backups

```yaml
backup_strategy:
  postgresql:
    frequency: "diario"
    retention: "30 días"
    method: "pg_dump comprimido → S3"
    
  redis:
    frequency: "no requiere" # datos efímeros
    
  s3_documents:
    frequency: "replicación cross-region"
    retention: "según política de retención de docs"
    
  audit_logs:
    frequency: "diario"
    retention: "5 años"
    method: "export a S3 con lifecycle rules"
```

## 8. Escalamiento futuro (post-MVP)

```
MVP (monolito):
  1 Frontend service
  1 Backend service (FastAPI + LangGraph)
  1 PostgreSQL
  1 Redis

→ Producción (microservicios):
  N Frontend replicas (stateless, Vercel o K8s)
  N API Gateway replicas (stateless)
  M LangGraph Worker replicas (procesamiento de agentes)
  1 PostgreSQL primary + N read replicas
  Redis cluster (3+ nodos)
  S3 (managed)
  Message queue (Redis Streams o RabbitMQ) entre API y workers
```
