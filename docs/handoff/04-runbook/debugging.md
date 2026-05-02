# Debugging

## Logs del backend

```bash
# Logs en tiempo real
docker logs -f docker-backend-1

# Últimas 100 líneas
docker logs docker-backend-1 --tail 100

# Filtrar por nivel ERROR
docker logs docker-backend-1 2>&1 | rg "ERROR|CRITICAL"
```

El backend usa logging estructurado configurado en `core/logging_setup.py`.
Nivel por defecto: `INFO`. El campo `LOG_LEVEL` en `.env` lo controla.

## Shell dentro del container

```bash
docker exec -it docker-backend-1 bash

# Dentro del container:
python -c "from app.main import app; print('OK')"
python -c "from app.orchestrator.graph import build_graph; print('OK')"
```

## Verificar que el código en el container es el correcto

```bash
# Ver el archivo dentro del container
docker exec docker-backend-1 cat /app/app/orchestrator/graph.py | head -20

# O montar el archivo con bat:
docker exec docker-backend-1 python -c "
import app.agents.synthesizer.agent as a
print(a.BASE_DISCLAIMER)
"
```

Si el código en el container NO coincide con lo que ves en disco →
hiciste `docker cp` sin reiniciar. Ver
[`../02-state/known-gotchas.md`](../02-state/known-gotchas.md) gotcha #2.

## Debuggear el grafo LangGraph

### Ver el estado antes de correr

Agregar logging temporario al inicio del WebSocket handler o al nodo
específico que querés inspeccionar.

```python
# En graph.py, dentro de un nodo:
import logging
log = logging.getLogger(__name__)
log.debug("state antes de specialists: %s", {
    k: state.get(k) for k in ["triage_level", "active_specialties", "subscription_tier"]
})
```

### Reproducir un caso fallido localmente

```python
# Script one-off para reproducir:
import asyncio
from app.orchestrator.graph import build_graph, create_initial_state
from app.services.llm_router import get_active_credential

async def reproduce():
    cred = await get_active_credential()
    graph = build_graph(cred)
    state = create_initial_state("test-case-1", "test-user-1", "tengo dolor en el pecho")
    state["subscription_tier"] = "paid"
    result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-case-1"}})
    print(result.get("synthesized_response", "")[:200])
    print("attention_level:", result.get("attention_level"))

asyncio.run(reproduce())
```

## Debuggear el audit chain

```bash
# Smoke test del chain
cd backend && poetry run python scripts/smoke_audit_chain.py

# Via API (requiere admin JWT)
TOKEN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tuki.dev","password":"Admin1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/v1/admin/audit/verify-chain | python3 -m json.tool
```

Si `broken_ids` no está vacío → hay rows con chain_hash corrupto.
Causa más común: migration `l2m3n4o5p6q7` no aplicada o rows insertados
antes de la migration con `previous_hash = NULL`.

## Debuggear tier gating

```bash
# Verificar tier del usuario
curl -H "Authorization: Bearer <token>" http://localhost:8001/api/v1/auth/me \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['subscription_tier'])"

# Intentar upload con free tier (debe dar 403)
curl -X POST http://localhost:8001/api/v1/documents/upload \
  -H "Authorization: Bearer <free-user-token>" \
  -F "file=@test.pdf" | python3 -m json.tool
# Esperado: {"detail": {"code": "tier_required", "required_tier": "paid", "current_tier": "free"}}
```

## Debuggear el WebSocket

Usar `websocat` o la consola del browser:

```bash
# Con websocat
websocat ws://localhost:8001/api/v1/chat/ws

# Primer mensaje siempre auth:
{"type":"auth","token":"<jwt-access-token>"}

# Luego un mensaje clínico:
{"type":"message","content":"tengo fiebre alta","case_id":null}
```

Frames esperados en orden:
1. `{"type":"auth_ok","user_id":"..."}`
2. `{"type":"agent_start","agent":"triage"}`
3. `{"type":"agent_start","agent":"anamnesis"}` (si aplica)
4. `{"type":"token","content":"..."}` (streaming del synthesizer)
5. `{"type":"done","response":"...","case_id":"..."}`

## Errores comunes y sus causas

| Error | Causa probable |
|-------|---------------|
| `IntegrityError: null value in column "previous_hash"` | Migration de audit chain no aplicada, o container sin restart tras docker cp |
| `asyncpg.InterfaceError: another operation is in progress` | No usar `async_session` para el audit dentro de LangGraph — usar `audit_session` (NullPool) |
| `GraphRecursionError` | Loop en el grafo sin condición de salida. Verificar `loop_count` y `max_loops` en state |
| `503 from LLM provider` | Falla transient del proveedor. El `safe_ainvoke` retry debería manejarlo. Si persiste, revisar la credencial activa |
| Frontend: "Request failed: 401" en console | Token expirado y el refresh falló (refresh token inválido o usuario desactivado) |
