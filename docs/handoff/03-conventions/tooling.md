# Convenciones de Tooling

## CLI obligatoria

Nunca usar los comandos Unix clásicos. Usar los equivalentes modernos:

| Prohibido | Usar en cambio | Instalar |
|-----------|----------------|---------|
| `cat` | `bat` | `brew install bat` |
| `grep` | `rg` (ripgrep) | `brew install ripgrep` |
| `find` | `fd` | `brew install fd` |
| `sed` | `sd` | `brew install sd` |
| `ls` | `eza` | `brew install eza` |

Si alguno no está instalado:
```bash
brew install bat ripgrep fd sd eza
```

### Ejemplos de uso

```bash
# Buscar texto en el código
rg "require_subscription_tier" backend/app/

# Buscar archivos por nombre
fd --type f "test_audit" backend/tests/

# Ver archivo con syntax highlighting
bat backend/app/orchestrator/graph.py

# Listar directorio con tree
eza --tree --level=2 backend/app/

# Reemplazar texto en archivo
sd "old_text" "new_text" path/to/file.py
```

## Backend — Poetry

```bash
# Instalar dependencias
cd backend && poetry install

# Agregar dependencia
poetry add <package>

# Agregar dependencia de dev
poetry add --group dev <package>

# Entrar al entorno virtual
poetry shell

# Correr comando en el entorno sin activarlo
poetry run pytest -q
poetry run python scripts/smoke_audit_chain.py
```

## Backend — Alembic

```bash
# Crear nueva migration
cd backend && poetry run alembic revision --autogenerate -m "descripcion_corta"

# Aplicar migrations
poetry run alembic upgrade head

# Ver estado de migrations
poetry run alembic current

# Rollback una migration
poetry run alembic downgrade -1
```

**Regla**: las migrations siempre van en commits separados con
`chore(db): add migration <descripcion>`.

## Frontend — npm

```bash
cd frontend

# Instalar dependencias
npm install

# Dev server (SOLO desde terminal real, no desde bash MCP)
npm run dev

# Lint
npm run lint

# Tests
npm run test

# Agregar componente shadcn
npx shadcn@latest add <component>   # v4, con @base-ui
```

**NUNCA**: `npm run build` fuera de Docker. El build de Next.js se hace
dentro de la imagen (`frontend/Dockerfile`).

## Docker

```bash
# Levantar todo el stack
cd infra/docker && docker compose up -d

# Levantar con rebuild
docker compose up --build -d

# Ver logs backend en tiempo real
docker logs -f docker-backend-1

# Reiniciar solo el backend (después de docker cp)
docker compose restart backend

# Estado de containers
docker compose ps

# Ejecutar comando dentro del backend
docker exec -it docker-backend-1 bash

# Copiar archivo al container (requiere restart después)
docker cp path/to/file.py docker-backend-1:/app/path/to/file.py
```

## Emojis — política

**NO usar emojis** en:
- Código fuente
- Commits
- Comentarios en código
- Documentación técnica

**SÍ usar** los emojis de roadmap (convención del producto):
- ✅ ítem completado
- ❌ ítem ausente / no implementado
- 🟡 ítem parcialmente implementado
- ⚠️ advertencia / gotcha
- ⏳ en progreso
- 🔲 no planificado todavía

Estos emojis SOLO en docs de estado (roadmap, done, pending).
