# Secrets y Configuración

## Variables de entorno del backend

El backend lee su config desde `backend/.env` (cargado por Docker Compose
via `env_file: ../../backend/.env`).

Variables mínimas para que el stack levante:

```bash
# Base de datos
DATABASE_URL=postgresql+asyncpg://medagent:medagent@postgres:5432/medagent

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
SECRET_KEY=<string aleatorio >= 32 chars>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Vault AES — para cifrar las API keys de LLM
VAULT_KEY=<bytes base64 de 32 bytes>

# Storage (MinIO)
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=tuki-medic-docs

# CORS
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:3001"]

# Proyecto
PROJECT_NAME=TukiMedic
VERSION=0.1.0
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Nota sobre LLM keys**: las API keys de LLM (OpenAI, Gemini, etc.) NO van
en `.env`. Se cargan en el vault AES desde el panel admin.
`OPENAI_API_BASE` puede ir en `.env` para los servicios de embedding que
todavía no fueron migrados al vault.

## Credenciales de desarrollo

| Secreto | Valor dev |
|---------|----------|
| Postgres user/pass/db | medagent / medagent / medagent |
| MinIO root user | minioadmin |
| MinIO root password | minioadmin |
| Admin email | admin@tuki.dev |
| Admin password | Admin1234! |
| Cliente email | cliente@tuki.dev |
| Cliente password | Cliente1234! |

**NUNCA usar estas credenciales en producción**.

## Vault AES-256-GCM

El vault almacena las API keys de LLM cifradas en Postgres. Para agregar
una credencial:

1. Loguear como admin.
2. `POST /api/v1/admin/credentials` con el provider + api_key.
3. El backend cifra con la `VAULT_KEY` y persiste en DB.
4. Solo puede existir una credencial activa por proveedor.

La `VAULT_KEY` debe ser 32 bytes en base64. Generar:
```python
import secrets, base64
print(base64.b64encode(secrets.token_bytes(32)).decode())
```

## Variables del frontend

El frontend usa `NEXT_PUBLIC_*` (expuestas al browser):

```bash
# frontend/.env.local (para dev local sin Docker)
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

En Docker Compose, estas se pasan como `args` al build y como `environment`
al container (ver `infra/docker/docker-compose.yml:84-91`).

## Rotación de secrets

### JWT SECRET_KEY
Si rotás `SECRET_KEY`, todos los tokens existentes se invalidan (todos los
usuarios quedan deslogueados). Hacerlo en maintenance window.

### VAULT_KEY
Si rotás `VAULT_KEY`, necesitás re-cifrar todas las credenciales LLM en DB.
No hay script de migración de vault todavía — requiere trabajo manual.

### LLM API Key
Desde el panel admin → Credenciales → marcar nueva credencial como activa.
La credencial vieja queda en DB pero inactiva. El graph cache tarda hasta
5 min en usar la nueva (TTL del cache).

## Qué NO commitear

```
backend/.env
frontend/.env.local
*.pem, *.key, *.p12
```

El `.gitignore` ya los excluye. Verificar antes de commitear:
```bash
git status --short | rg "\.env"    # no debe aparecer nada
```
