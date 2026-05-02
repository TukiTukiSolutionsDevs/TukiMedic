# Setup — Levantar el stack

## Prerrequisitos

```bash
# Verificar que están instalados:
docker --version          # Docker Desktop o Docker Engine
docker compose version    # Compose v2 (el comando es `docker compose`, no `docker-compose`)
poetry --version          # Para correr tests y scripts sin Docker
node --version            # >= 20 (para frontend fuera de Docker)
```

## Levantar el stack completo con Docker

```bash
cd infra/docker
docker compose up -d
```

Esto levanta: postgres, redis, minio, backend, frontend.

Los healthchecks garantizan el orden de arranque: postgres + redis + minio
deben estar `healthy` antes de que backend arranque.

**Verificar que todo está up**:
```bash
docker compose ps
```

Todos los servicios deben estar en estado `running` (no `restarting`).

## Puertos

| Servicio | URL |
|----------|-----|
| Backend API | http://localhost:8001 |
| Frontend | http://localhost:3001 |
| MinIO console | http://localhost:9001 |
| Postgres | localhost:5432 (interno, no expuesto por default) |

## Smoke tests de healthcheck

```bash
# Liveness
curl http://localhost:8001/health

# Readiness (postgres + redis + minio)
curl http://localhost:8001/health/ready
```

Respuesta esperada de `/health/ready`:
```json
{"status": "ready", "components": {"postgres": "ok", "redis": "ok", "storage": "ok"}}
```

## Credenciales de desarrollo

| Usuario | Email | Contraseña | Tier |
|---------|-------|-----------|------|
| Admin | admin@tuki.dev | Admin1234! | — |
| Cliente free | cliente@tuki.dev | Cliente1234! | free |

## Levantar el backend solo (para desarrollo Python)

```bash
cd backend
poetry install          # primera vez
poetry run alembic upgrade head   # aplicar migrations
poetry run uvicorn app.main:app --reload --port 8000
```

Nota: para esto necesitás postgres, redis y minio levantados (pueden
estar en Docker). El backend no es la imagen — es el proceso uvicorn local.

## Levantar el frontend solo (para desarrollo Next.js)

```bash
cd frontend
npm install             # primera vez
npm run dev             # NO desde bash MCP — usar terminal real
```

El frontend dev corre en http://localhost:3000.
Asegurate de que `NEXT_PUBLIC_API_URL` apunta al backend:
```bash
# en frontend/.env.local (si no existe, crear):
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

## Troubleshooting de setup

**Backend no arranca (exit code 1)**:
```bash
docker logs docker-backend-1 --tail 50
```
Causa más común: migration pendiente o credencial LLM no configurada.

**Frontend no muestra nada**:
```bash
docker logs docker-frontend-1 --tail 20
```
Verificar que `NEXT_PUBLIC_API_URL` está configurado correctamente.

**Postgres connection refused**:
El container de postgres puede tardar hasta 30s en estar `healthy`. Esperar
o revisar:
```bash
docker compose ps postgres
```

**MinIO no inicializa el bucket**:
El backend crea el bucket al arrancar si no existe. Si minio arranca después
del backend (healthcheck fallido), puede que el bucket no exista. Reiniciar:
```bash
docker compose restart backend
```
