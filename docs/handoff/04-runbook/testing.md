# Testing — Correr y escribir tests

## Tests backend

### Correr todos (sin LLM real)

```bash
cd backend && poetry run pytest -q
```

Esto corre todos los tests que no requieren LLM real. Los tests con
`@pytest.mark.live_llm` se saltan automáticamente si no hay credencial activa.

### Correr un archivo específico

```bash
poetry run pytest tests/test_audit.py -v
poetry run pytest tests/core/test_sanitize.py -v
```

### Correr por marker

```bash
# Solo unit tests (sin live_llm, sin integration)
poetry run pytest -m "not live_llm and not integration" -q

# Solo integration (requiere DB + Redis)
poetry run pytest -m integration -q

# Eval clínica — requiere LLM activo y puede tardar minutos
poetry run pytest tests/clinical_eval/ -m live_llm -v
```

### Ver qué tests existen (sin correrlos)

```bash
poetry run pytest --co -q
poetry run pytest --co -q | tail -10  # últimos 10 tests colectados
```

### Stats actuales

- 82 archivos de test en `backend/tests/`
- ~132 tests en total (verificar con `pytest --co -q | tail -5`)
- Eval clínica: 25 casos, 96% pass rate (24/25 — 1 fail por 503 transient Gemini)

## Tests frontend

### Correr todos

```bash
cd frontend && npm run test
```

### Modo watch

```bash
npm run test:watch
```

### UI de Vitest (browser)

```bash
npm run test:ui
```

### Stats actuales

- 52 tests, todos passing
- Framework: Vitest 4 + React Testing Library + jsdom

## Smoke test del audit chain

```bash
cd backend && poetry run python scripts/smoke_audit_chain.py
```

Verifica que la hash chain del audit log está intacta. Si hay rows con
`chain_hash` roto → reporta los IDs afectados.

También disponible via API:
```bash
curl -H "Authorization: Bearer <admin-jwt>" \
  http://localhost:8001/api/v1/admin/audit/verify-chain
```

## Markers registrados

| Marker | Requiere | Cuándo correr |
|--------|---------|--------------|
| `live_llm` | Credencial LLM activa | Solo en dev con creds, nunca en CI sin ellas |
| `integration` | Postgres + Redis levantados | En local con stack Docker up |

Tests sin marker → unit tests puros, sin dependencias externas.

## Estructura de tests del backend

```
tests/
├── conftest.py           # fixtures: async_client, db, redis mock, etc.
├── api/                  # tests de endpoints HTTP (AsyncClient)
├── clinical_eval/        # 25 casos clínicos con @pytest.mark.live_llm
├── core/                 # sanitize, prompt_guard, security, etc.
├── integration/          # tests con DB real (alembic + asyncpg)
├── orchestrator/         # tests del grafo LangGraph
├── services/             # audit, llm_router, etc.
└── test_*.py             # tests legacy en raíz (agentes, API, features)
```

## Antes de mergear cualquier cambio

1. `poetry run pytest -q` → todos en verde (excepto `live_llm` si no hay creds)
2. `cd frontend && npm run test` → 52/52
3. `git status` → working tree limpio
4. `git log --oneline -3` → commits con mensajes convencionales

Si rompés un test existente con tu cambio, el test tiene razón. Arreglá
el código, no el test (a menos que el test testee el comportamiento incorrecto).

## Escribir tests nuevos

Seguir el patrón TDD (ver [`../03-conventions/tdd.md`](../03-conventions/tdd.md)).

Para tests de agentes, usar mocking del LLM:
```python
# Patrón común en tests de agentes
from unittest.mock import AsyncMock, patch

async def test_triage_agent_returns_yellow_on_injection(conftest_state):
    with patch("app.agents.triage.agent.safe_ainvoke") as mock_invoke:
        mock_invoke.return_value = _TRIAGE_FALLBACK
        agent = TriageAgent(chat_model=MagicMock())
        result = await agent(conftest_state)
    assert result["triage_level"] == "yellow"
```

Para tests de API, usar `AsyncClient` del conftest:
```python
async def test_login_success(async_client, test_user):
    response = await async_client.post("/api/v1/auth/login", json={
        "email": test_user.email,
        "password": "Test1234!"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```
