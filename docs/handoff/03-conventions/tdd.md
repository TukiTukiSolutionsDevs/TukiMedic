# Convención TDD — Strict TDD Mode

El proyecto tiene **Strict TDD Mode activo**. Esto no es negociable y no
puede saltarse porque "es una feature simple".

## El ciclo obligatorio

```
RED   → escribir el test que falla
         ↓
         correr: cd backend && poetry run pytest path/test.py -q
         verificar: el test FALLA (no error de sintaxis — FALLA)
         commit: test(scope): red — describe qué testea
         ↓
GREEN → escribir la implementación MÍNIMA que hace pasar el test
         ↓
         correr: pytest path/test.py -q
         verificar: el test PASA
         commit: fix(scope): green — describe qué implementa
         ↓
REFACTOR → limpiar sin cambiar comportamiento
         ↓
         correr: pytest path/test.py -q  (debe seguir en verde)
         commit: refactor(scope): describe qué se limpió
```

Cada fase es un **commit separado**. No hay fase que combine RED + GREEN
en un solo commit.

## Backend — pytest

```bash
# Correr todos los tests
cd backend && poetry run pytest -q

# Correr un archivo específico
poetry run pytest tests/test_audit.py -v

# Correr con marker (sin LLM real)
poetry run pytest -m "not live_llm" -q

# Correr eval clínica (requiere LLM activo)
poetry run pytest tests/clinical_eval/ -m live_llm

# Solo collect (ver qué tests existen sin correrlos)
poetry run pytest --co -q
```

### Markers registrados

| Marker | Cuándo se usa |
|--------|--------------|
| `live_llm` | Tests que invocan el LLM real — NO correr en CI sin creds |
| `integration` | Tests que requieren DB o Redis levantados |

Tests sin marker → unit tests puros, sin dependencias externas.

## Frontend — Vitest

```bash
cd frontend && npm run test          # run once
npm run test:watch                   # watch mode
npm run test:ui                      # Vitest UI en browser
```

El framework es **Vitest 4** con React Testing Library + jsdom. NO Jest.
La configuración es `vitest.config.ts` (o en `vite.config.ts`).

## Qué NO hacer

- **NO escribir código antes del test**. Si escribís la implementación y
  después el test, no es TDD — es test-after y el ciclo rojo nunca existió.
- **NO commitear RED + GREEN en un solo commit**. El historial debe mostrar
  que el test existía antes de la implementación.
- **NO saltear REFACTOR** diciendo "ya está limpio". La fase de refactor
  es donde se remueve duplicación y se mejoran nombres.
- **NO correr `npm run build`** en dev (solo dentro de Docker).

## Estructura de tests backend

```
backend/tests/
├── conftest.py              # fixtures globales (db, redis, etc.)
├── api/                     # tests de endpoints (httpx AsyncClient)
├── clinical_eval/           # 25 casos clínicos (live_llm marker)
├── core/                    # tests de módulos core (sanitize, prompt_guard, etc.)
├── integration/             # tests con DB + Redis reales
├── orchestrator/            # tests del grafo LangGraph
├── services/                # tests de audit, llm_router, etc.
└── test_*.py                # tests en el nivel raíz (legacy location)
```

82 archivos de test. Todos deben pasar antes de mergear cualquier cambio.
