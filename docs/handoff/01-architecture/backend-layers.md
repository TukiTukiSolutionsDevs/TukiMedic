# Capas del Backend

El backend sigue **Screaming Architecture** con vertical slices pragmáticas.
No es Hexagonal pura (sin puertos/adaptadores ni repositorio explícito) — es
FastAPI con FastAPI Depends como DI, SQLAlchemy directo en servicios.

## Tabla de contenidos

1. [Estructura de directorios](#estructura-de-directorios)
2. [Capa de API](#capa-de-api)
3. [Capa de agentes](#capa-de-agentes)
4. [Capa de orquestación](#capa-de-orquestación)
5. [Capa de servicios](#capa-de-servicios)
6. [Capa de modelos](#capa-de-modelos)
7. [Core (transversal)](#core-transversal)
8. [Memory system](#memory-system)

## Estructura de directorios

```
backend/app/
├── main.py                  # FastAPI app factory, middlewares, routers, health
├── api/v1/
│   ├── auth.py              # /auth/* — registro, login, refresh, me, GDPR delete
│   ├── chat.py              # /chat/ws — WebSocket clínico
│   ├── documents.py         # /documents/* — upload, list, get (paid gate)
│   ├── admin.py             # /admin/* — users, credentials, KB ingest, audit
│   └── export.py            # /export/pdf/* (paid gate)
├── agents/
│   ├── _llm_safe.py         # safe_ainvoke: retry + fallback para todos los agentes
│   ├── triage/
│   ├── anamnesis/
│   ├── classifier/
│   ├── specialists/         # base.py, registry.py, dispatcher.py + 11 agentes
│   ├── medical_board/
│   ├── devils_advocate/
│   ├── guardrail/
│   └── synthesizer/
├── orchestrator/
│   ├── state.py             # ClinicalCaseState TypedDict
│   └── graph.py             # build_graph(), nodos, edges, audit wrappers
├── services/
│   ├── audit.py             # hash chain + log_action / log_clinical_decision
│   ├── llm_router.py        # vault → credenciales → ChatOpenAI fast/smart
│   ├── document_context.py  # inyección de contexto de documentos al state
│   └── kb_sources/          # vacío — loaders PubMed/WHO pendientes
├── memory/
│   ├── __init__.py          # append_messages, load_messages, store_facts, retrieve_relevant_facts
│   ├── kb_retriever.py      # retrieve_kb_context (pgvector)
│   └── pg_timeline.py       # get_patient_timeline, get_or_create_profile, store_timeline_event
├── models/                  # SQLAlchemy ORM models
│   ├── user.py
│   ├── case.py
│   ├── message.py
│   ├── document.py
│   ├── audit_log.py
│   ├── clinical_fact.py
│   └── patient.py
├── schemas/                 # Pydantic request/response schemas
├── core/
│   ├── config.py            # Settings (pydantic-settings)
│   ├── database.py          # async_session, audit_session (NullPool), Base
│   ├── dependencies.py      # get_current_user, require_subscription_tier
│   ├── security.py          # JWT create/decode, password hashing
│   ├── redis.py             # redis_client singleton
│   ├── storage.py           # storage_client (MinIO/S3)
│   ├── rate_limit.py        # limiter (slowapi)
│   ├── graph_cache.py       # get_or_build_graph() con asyncio.Lock + TTL
│   ├── sanitize.py          # sanitize_patient_markdown (25 tests)
│   ├── prompt_guard.py      # detect_injection(), wrap_user_input() (23 tests)
│   ├── logging_setup.py     # configure_logging()
│   └── middleware/
│       └── security_headers.py  # SecurityHeadersMiddleware (HSTS, CSP, X-Frame-Options)
└── data/
    ├── red_flags.yaml       # reglas determinísticas de triage
    └── specialty_map.yaml   # mapeo síntomas → especialidades
```

## Capa de API

Todos los routers se registran en `main.py` con prefijo `/api/v1`.

**Middlewares (orden de aplicación, el último es el más externo):**
1. `SlowAPIMiddleware` — rate limiting
2. `CORSMiddleware` — ALLOWED_ORIGINS desde settings
3. `SecurityHeadersMiddleware` — HSTS, CSP, X-Frame-Options (outermost)

**Autenticación**: HTTPBearer → `get_current_user` dependency → JWT decode →
`SELECT User WHERE id = sub AND is_active = true`.

**Rate limits definidos:**
- `POST /auth/register` → 3/hour
- `POST /auth/login` → 5/minute
- `POST /auth/refresh` → 10/minute
- `DELETE /auth/me` → 3/hour
- WebSocket: Redis INCR/EXPIRE, 10 msgs/60s por user

## Capa de agentes

Cada agente sigue el patrón:

```python
class XxxAgent:
    def __init__(self, chat_model=None, *, api_key=None, model="...", base_url=None):
        # Preferir chat_model (del LLM router) sobre api_key legacy
        self.llm = chat_model.with_structured_output(XxxSchema)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        # Devuelve partial state update
```

`safe_ainvoke` en `agents/_llm_safe.py` wrappea toda invocación LLM:
retry automático + fallback defensivo si el LLM no está disponible.

## Capa de orquestación

`graph.py` construye el `StateGraph` de LangGraph. Recibe un
`ProviderCredentialDTO` (credencial activa del vault) y crea todos
los agentes con los modelos resueltos.

El grafo se **cachea** en `core/graph_cache.py` por `user_id` con TTL 5 min
y un `asyncio.Lock` por instancia. En multi-worker (Gunicorn), cada proceso
tiene su propio cache → la rotación de credenciales tarda hasta 5 min en
propagarse a todos los workers.

## Capa de servicios

- **`audit.py`**: hash chain global. `log_action` para acciones de API,
  `log_clinical_decision` para nodos clínicos (triage, guardrail, synthesizer).
- **`llm_router.py`**: resuelve la credencial activa del vault AES-256-GCM
  y construye `ChatOpenAI` con `api_key + base_url` explícitos.
- **`document_context.py`**: reúne documentos + lab values del user para
  inyectar como contexto al grafo cuando el mensaje los referencia.

## Capa de modelos

SQLAlchemy 2 con `Mapped` / `mapped_column`. Todos async via `asyncpg`.

Modelos principales:
- `User`: id (UUID), email, password_hash, role, subscription_tier, is_active
- `Case`: id (UUID), user_id, title, status
- `Message`: case_id, role, content
- `DocumentModel`: user_id, storage_path, doc_type, ocr_text
- `AuditLog`: user_id, action, entity_type, entity_id, details (JSONB), previous_hash, chain_hash
- `ClinicalFactModel`: user_id, case_id, key, value, embedding (pgvector)
- `PatientProfile`, `PatientTimelineEvent`: L3 memory

## Core (transversal)

Módulos sin dominio específico usados por todas las capas:

- `config.py`: `Settings` via pydantic-settings. Fuente única de configuración.
- `database.py`: `async_session` (pool normal), `audit_session` (NullPool —
  evita `asyncpg InterfaceError` en greenlets de LangGraph).
- `prompt_guard.py`: regex pre-filtro de prompt injection. Corre antes del
  LLM en Triage y Synthesizer.
- `sanitize.py`: limpia el markdown de respuestas antes de enviarlo al paciente
  (HTML tags, URL schemes peligrosos, imágenes, zero-width unicode).

## Memory system

```
L1 Redis     append_messages / load_messages      historial del turno (efímero)
L2 Postgres  store_facts / retrieve_relevant_facts hechos clínicos con embeddings
L3 Postgres  patient_timeline / patient_profile    historia entre sesiones
KB Postgres  kb_retriever (pgvector)               conocimiento médico estructurado
```

Los cuatro niveles fallan gracefully — si cualquiera falla, el chat continúa.
