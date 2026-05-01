# Tuki-Medic — Frontend Design Brief

> **Audiencia**: Claude Design / diseñador frontend.  
> **Objetivo**: poder producir mockups, flujos UX y specs de UI **sin abrir el backend**.  
> **HEAD del repo**: `fb456e9` · **Estado**: pre-beta · **Eval clinical**: 24/25 PASS (96%).  
> **Latencia**: P50 ≈ 50s, P95 ≈ 125s por respuesta clínica completa.  
> **Doc generado**: read-only inspection del backend en `/Users/soulkin/Documents/Tuki-Medic`.

---

## 1. Visión de producto

**Tuki-Medic** es una **app conversacional de orientación médica** para Argentina (español rioplatense, voseo). El usuario describe síntomas en chat y obtiene una respuesta sintetizada por un panel de agentes especialistas (cardio, neuro, derma, pediatría, ginecología, traumatología, endocrino, farmacología, medicina general, medicina interna). El backend ejecuta un grafo deliberativo (LangGraph): triage → anamnesis → clasificación → especialistas en paralelo → mesa médica (consenso) → guardrail → síntesis para paciente.

**Lo que NO hace** (importante para tono y disclaimers):
- **NO diagnostica** ("no tenés X")
- **NO receta** medicamentos con dosis específicas para tratamiento
- **NO atiende emergencias** — si triage = `red`, el sistema deriva a 107 / SAME / emergencias
- **NO reemplaza** la consulta médica presencial — disclaimer obligatorio en TODA respuesta

**Diferenciador**: triage clínico determinístico (red flags duros + LLM) + multi-specialist analysis + mesa médica + audit hash chain (defensibilidad médico-legal). Cada decisión clínica se firma con `previous_hash → chain_hash` (SHA-256), verificable end-to-end.

---

## 2. Stack y arquitectura

### 2.1 Frontend actual (`frontend/`)

- **Framework**: **Next.js (App Router)** — confirmado por `src/app/`, `next.config.ts`, `.next/`, `next-env.d.ts`.
- **UI lib**: **shadcn/ui** — confirmado por `components.json` y `components/ui/{button,input}.tsx` (solo dos primitives, el resto está por construir).
- **Styling**: Tailwind (vía `postcss.config.mjs` + `globals.css`).
- **State**: stores propios — `src/store/auth-store.ts`, `src/store/chat-store.ts` (probablemente Zustand por convención Next + el patrón de archivo `*-store.ts`).
- **Hooks**: `src/hooks/use-chat-ws.ts` (cliente WebSocket), `src/hooks/use-document-upload.ts`.
- **API client**: `src/lib/api.ts`.
- **Pages presentes** (`src/app/`):
  - `/` (landing — `page.tsx`, ~574 bytes, probablemente stub)
  - `/login` (page.tsx, 5.9 KB)
  - `/dashboard` (4.3 KB)
  - `/chat` (8.8 KB)
  - `/settings` (971 B — stub)
  - `/admin/{users,credentials,kb,audit}` con `layout.tsx` propio
- **Estado del frontend**: **funcional pero esquelético**. Hay estructura de páginas y conexión WS, pero la UX clínica (progress feedback, escalation cards, document viewer, multi-specialist breakdown, history) está **por diseñar**. Solo dos componentes UI primitives (button, input) — todo el sistema de design tokens, mensajes de chat, chips de especialidad, badges de triage, alarm-sign cards, escalation hero, etc., **NO existe todavía**.

> ⚠️ **Lo que falta documentar exactamente** (no pude leer los archivos durante esta sesión por bloqueo del executor): contenido exacto de `chat/page.tsx`, `use-chat-ws.ts`, `lib/api.ts`, stores. La spec de WebSocket y endpoints abajo es **autoridad** porque viene del backend.

### 2.2 Backend

- **FastAPI** + **LangGraph** + **LangChain** + **Pydantic v2** + **SQLAlchemy 2.0 async**.
- Puerto host: **`8001`** (mapeado desde container).
- Routers (todos bajo `/api/v1`):
  - `auth_router` → `/api/v1/auth/*`
  - `chat_router` → `/api/v1/chat/ws` (WebSocket)
  - `documents_router` → `/api/v1/documents/*`
  - `admin_router` → `/api/v1/admin/*`
  - `export_router` → `/api/v1/cases/{id}/export/pdf`
- **Health**: `/health` (liveness, no toca deps), `/health/ready` (postgres + redis + storage).
- **Middlewares** (orden de fuera hacia adentro):
  1. `SecurityHeadersMiddleware` (HSTS, CSP, X-Frame-Options DENY, etc.)
  2. `CORSMiddleware` (allow_origins desde settings.ALLOWED_ORIGINS, allow_credentials=True)
  3. `SlowAPIMiddleware` (rate limiting global)

### 2.3 Datos / storage

- **PostgreSQL 16** con **pgvector** — tablas en `app/models/`. Embeddings 1536-dim (text-embedding-3-small) para:
  - `clinical_facts.embedding` (memoria L2)
  - `patient_timeline.embedding` (memoria L3)
  - `knowledge_base_chunks.embedding` (RAG)
- **Redis** — sesión / window de mensajes (memoria L1), rate limit por usuario (`ws:ratelimit:{user.id}`), cache de métricas admin (5 min TTL).
- **MinIO** (S3-compat) — puerto **`9002`** — uploads. Subida soportada:
  - PDF (`application/pdf`)
  - JPEG (`image/jpeg`)
  - PNG (`image/png`)
  - **Tope**: 20 MB por archivo. Validación por **file magic** (lib `filetype`), no por Content-Type del cliente.
  - Path: `{user_id}/{doc_id}/{safe_filename}`. Sanitización de filename: solo `[A-Za-z0-9._-]`, max 200 chars, sin `..`.

### 2.4 LLM

- **Gemini** principal (vault-stored, OpenAI-compat endpoint vía `base_url`).
- Fallback **OpenAI / Anthropic** vía `app/services/llm_router.py` (DTO `ProviderCredentialDTO`).
- Tiers:
  - **fast**: triage, anamnesis, clasificación, especialistas, guardrail, synthesizer, devils_advocate.
  - **smart**: medical_board (deliberación más profunda).
- API keys **encriptadas** (AES-256-GCM) en tabla `provider_credentials`. Solo una activa por provider (partial unique index).
- Versiones de modelo auditadas:
  - `gpt-4o-mini@triage-v1`
  - `gpt-4o@guardrail-v1`
  - `gpt-4o@synthesizer-v1`
  - (los strings se mantienen aun cuando el provider real es Gemini — los versionamos por nombre canónico).

### 2.5 Puertos (front → back)

| Servicio | Puerto host | Notas |
|----------|-------------|-------|
| Frontend (Next.js) | `3001` | Build container; en dev típicamente `3000` con proxy. |
| Backend (FastAPI) | `8001` | REST + WS bajo `/api/v1`. |
| MinIO | `9002` | S3 API. La UI MinIO suele estar en otro puerto. |
| Postgres | interno | No expuesto al front. |
| Redis | interno | No expuesto al front. |

---

## 3. Modelos de datos relevantes para frontend

> Las URIs se serializan como `string` (UUID) en JSON. Pydantic v2 lo hace automático.

### 3.1 `User` (`app/models/user.py`)

```python
class User:
    id: UUID
    email: str                    # único
    password_hash: str            # bcrypt — NUNCA al frontend
    display_name: str | None
    birth_year: int | None        # privacy: año, no fecha exacta
    biological_sex: str | None    # string libre, no enum estricto
    is_active: bool               # default True
    is_verified: bool             # default False — flag pero NO hay flujo de email verify aún
    role: str                     # "customer" | "admin"
    subscription_tier: str        # "free" | "paid"  ← gating planeado, NO implementado
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None
    preferences: dict             # JSONB — campo libre para UI prefs
    deleted_at: datetime | None   # soft-delete (GDPR)
```

**Schema response (UserResponse, expuesto al front):**
```python
{
  "id": "<uuid>",
  "email": "...",
  "display_name": "...",
  "is_verified": false,
  "role": "customer" | "admin",
  "subscription_tier": "free" | "paid"
}
```

### 3.2 `Case` (sesión clínica) (`app/models/case.py`)

```python
class Case:
    id: UUID
    user_id: UUID
    title: str | None
    chief_complaint: str | None
    status: str                   # default "active"
    triage_level: str | None      # "green" | "yellow" | "red"
    triage_confidence: float | None
    patient_context: dict         # JSONB
    active_specialties: list[str] # array de specialties usadas
    message_count: int
    loop_count: int
    total_agent_invocations: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    archived_at: datetime | None
```

**Para UI**: 1 case = 1 sesión clínica. El frontend pasa `case_id` al WS para resumir el chat. Si manda `null`/omite, el backend genera UUID nuevo.

### 3.3 `Message` (`app/models/message.py`)

```python
class Message:
    id: UUID
    case_id: UUID                 # FK con CASCADE
    role: str                     # "user" | "assistant" | "system"
    content: str
    message_type: str             # default "text"
    agents_involved: list[str]
    turn_number: int
    created_at: datetime
```

### 3.4 `DocumentModel` + `LabValueModel` (`app/models/document.py`)

```python
class DocumentModel:
    id: UUID
    user_id: UUID
    case_id: UUID | None          # opcional — doc puede no atarse a un case
    original_filename: str        # ya sanitizado
    mime_type: str                # "application/pdf" | "image/jpeg" | "image/png"
    file_size: int                # bytes
    storage_path: str             # path en MinIO
    doc_type: str | None          # "lab_result" | "prescription" | "medical_report"
                                  # | "imaging_report" | "discharge_summary"
    doc_type_confidence: float | None
    ocr_text: str | None
    ocr_engine: str | None
    processing_status: str        # "pending" | "processing" | "done" | "failed"
    error_message: str | None
    created_at: datetime
    updated_at: datetime | None

class LabValueModel:
    id: UUID
    document_id: UUID             # FK
    user_id: UUID
    test_name: str
    value: str
    unit: str | None
    reference_range: str | None
    flag: str | None              # "high" | "low" | "normal" | "critical"
    raw_text: str | None
    created_at: datetime
```

**Para UI**: el doc se sube `pending` → background processing pasa a `processing` → `done` (con OCR + lab_values poblados) o `failed`. **Frontend debe pollear** el estado o mostrar un placeholder de "procesando…".

### 3.5 `AuditLog` (`app/models/audit_log.py`)

```python
class AuditLog:
    id: UUID
    user_id: UUID | None
    action: str                   # "register" | "login" | "document_upload" |
                                  # "triage_decision" | "guardrail_violation" |
                                  # "response_synthesized" | "kb_add_chunk" |
                                  # "user_patch" | "api_key_create" |
                                  # "api_key_rotate" | "api_key_activate" |
                                  # "api_key_delete" | "kb_ingest" |
                                  # "export_pdf" | "gdpr_delete" | "graph_timeout"
    entity_type: str | None       # "user" | "case" | "document" | "kb_chunk" | "api_key"
    entity_id: UUID | None
    details: dict | None          # JSONB libre
    ip_address: str | None
    previous_hash: str            # SHA-256 hex (64 chars) — chain
    chain_hash: str               # SHA-256(previous_hash || inputs_hash)
    created_at: datetime
```

**Para UI admin**: tabla paginada con filtros `action`, `user_id`. Y un endpoint dedicado `GET /admin/audit/verify-chain` que retorna `{ok, broken_ids, checked_at}` — diseñá un **status badge** (verde "íntegra" / rojo "corrupta") + tooltip con timestamp.

### 3.6 `PatientProfile` y `PatientTimelineEvent` (`app/models/patient.py`)

```python
class PatientProfile:
    id: UUID
    user_id: UUID                  # único — uno por usuario
    allergies: list                # JSONB
    active_medications: list       # JSONB
    chronic_conditions: list       # JSONB
    blood_type: str | None
    age: int | None
    sex: str | None
    updated_at: datetime | None

class PatientTimelineEvent:
    id: UUID
    user_id: UUID
    case_id: UUID | None
    event_type: str               # "consultation" | "diagnosis" |
                                  # "medication_change" | "lab_result" | "symptom"
    summary: str
    details: dict | None          # JSONB
    embedding: vector(1536)       # pgvector
    occurred_at: datetime
    created_at: datetime
```

**⚠️ Decisión de producto pendiente**: ¿la UI deja al usuario editar su `PatientProfile` directamente (formulario tipo "ficha clínica")? Hoy el modelo se popula automáticamente desde la conversación. Recomendación: pantalla `/profile` opcional para que el usuario revise/corrija lo que el sistema infirió.

### 3.7 `KnowledgeBaseChunk` (`app/models/patient.py`)

```python
class KnowledgeBaseChunk:
    id: UUID
    source: str                   # "medlineplus" | "vademecum"
    title: str
    content: str
    chunk_index: int
    specialty_tags: list          # JSONB
    embedding: vector(1536)
    created_at: datetime
```

**Para UI admin**: gestión RAG. CRUD + reingesta.

### 3.8 `ProviderCredential` (`app/models/provider_credential.py`)

```python
class ProviderCredential:
    id: UUID
    provider: str                 # "openai" | "gemini" | "anthropic"
    label: str                    # human-readable
    encrypted_key: bytes          # AES-256-GCM ciphertext — NUNCA al front
    iv: bytes                     # nonce — NUNCA al front
    tag: bytes                    # GCM tag — NUNCA al front
    is_active: bool               # solo una activa por provider
    created_at: datetime
    rotated_at: datetime | None
    created_by_user_id: UUID | None
```

**Para UI admin**: solo se devuelven los campos seguros (`_cred_response`): `id, provider, label, is_active, created_at, rotated_at, created_by_user_id`. El plaintext_key SOLO viaja en POST/PATCH (input one-way).

### 3.9 `ClinicalFactModel` (`app/models/clinical_fact.py`)

```python
class ClinicalFactModel:
    id: UUID
    user_id: UUID
    case_id: UUID | None
    fact_type: str                # "symptom" | "diagnosis" | "medication" |
                                  # "allergy" | "vital"
    value: str                    # texto libre
    source_agent: str             # qué agente lo extrajo
    confidence: float             # 0.0-1.0
    embedding: vector(1536)
    created_at: datetime
```

Memoria clínica L2. **No expuesto directamente al usuario hoy**, pero útil para una pantalla "esto es lo que sabemos sobre vos" si decidís darle visibilidad al usuario.

### 3.10 Agent output schemas (lo que ven los agentes — NO el usuario)

**`SpecialistAnalysis`** (`app/agents/specialists/schemas.py`) — output de cada especialista:
```python
{
  "specialty_name": "cardiologia",
  "clinical_impression": "...",
  "differential_diagnosis": [
    {
      "condition": "...",
      "probability": "alta" | "media" | "baja",
      "supporting_evidence": [...],
      "against_evidence": [...]
    }
  ],
  "suggested_studies": [...],
  "risk_factors": [...],
  "recommendations": [...],
  "alarm_signs": [...],
  "confidence": 0.0-1.0,
  "needs_referral": false,
  "referral_to": []
}
```

**`TriageResult`** (`app/agents/triage/schemas.py`):
```python
{
  "level": "green" | "yellow" | "red",
  "confidence": 0.0-1.0,
  "red_flags_detected": [...],
  "reasoning": "...",
  "recommended_urgency": "rutina" | "24-48h" | "hoy" | "inmediato"
}
```

**`SynthesizedResponse`** (`app/agents/synthesizer/schemas.py`) — **lo que llega al frontend**:
```python
{
  "patient_response": "Texto en lenguaje claro para el usuario",
  "clinical_summary": "Resumen técnico (NO al frontend, audit-only)",
  "specialties_involved": ["cardiologia", "neurologia"],
  "attention_level": "rutina" | "24-48h" | "hoy" | "urgencia",
  "follow_up_questions": [...],
  "alarm_signs": [...],
  "disclaimer": "..."
}
```

> En el WebSocket actual el frontend recibe `patient_response` ya **concatenado** con `BASE_DISCLAIMER` y el separador (`\n\n---\n\n`) en el campo `response` del frame `done`. El resto de los campos (specialties, attention_level, alarm_signs, follow_ups) NO se serializan en el WS hoy — **es una oportunidad para extender el contrato del WS** y que la UI muestre badges, listas de alarmas, etc.

---

## 4. Endpoints (REST + WebSocket)

### 4.1 Auth — `/api/v1/auth/*`

| Método | Path | Auth | Rate limit | Body | Response | Errores |
|--------|------|------|------------|------|----------|---------|
| POST | `/auth/register` | none | 3/hour por IP | `{email, password, display_name?}` | 201 `TokenResponse` | 400 email exists |
| POST | `/auth/login` | none | 5/min por IP | `{email, password}` | 200 `LoginResponse` (incluye `user`) | 401 invalid creds, 403 disabled |
| POST | `/auth/refresh` | refresh JWT | 10/min | `{refresh_token}` | 200 `TokenResponse` | 401 invalid token |
| GET | `/auth/me` | access JWT | — | — | `UserResponse` | 401 |
| DELETE | `/auth/me` | access JWT | 3/hour | — | 204 (GDPR erase + anonymize) | 401 |

**Password rules** (server-side, `app/schemas/auth.py`):
- min 8 chars, max 128 chars
- el frontend DEBE replicar la validación visual antes de POST

**JWT shape**: access token con `sub, role, subscription_tier, type="access"`. Refresh con `sub, type="refresh"`.

### 4.2 Chat WebSocket — `/api/v1/chat/ws` ⚡ CRÍTICO

**Origin guard**: si la conexión llega con `Origin` header y no está en `ALLOWED_ORIGINS`, cierra con `1008`.

**Constantes** (patcheables, valores producción):
- `AUTH_TIMEOUT = 10s` (timeout para primer mensaje auth)
- `GRAPH_TIMEOUT = 120s` (max ejecución del grafo)
- `HEARTBEAT_INTERVAL = 30s`
- `RATE_LIMIT_MAX = 10` mensajes / `RATE_LIMIT_WINDOW = 60s`

**Frames del cliente al servidor:**

| `type` | Payload | Cuándo |
|--------|---------|--------|
| `auth` | `{type:"auth", token:"<JWT access>"}` | **PRIMER mensaje obligatorio** dentro de 10s |
| `message` | `{type:"message", content:"...", case_id:"<uuid>?"}` | Cada turno del chat |
| `ping` | `{type:"ping"}` | Opcional — el servidor responde inmediato `pong` |

**Frames del servidor al cliente:**

| `type` | Payload | Significado |
|--------|---------|-------------|
| `auth_ok` | `{type:"auth_ok", user_id:"<uuid>"}` | Autenticación exitosa |
| `pong` | `{type:"pong"}` | Heartbeat (cada 30s) o respuesta a `ping` |
| `agent_start` | `{type:"agent_start", agent:"<name>"}` | Empezó un nodo del grafo. Nombres posibles: `triage`, `anamnesis`, `classification`, `specialists`, `medical_board`, `devils_advocate`, `guardrail`, `synthesizer`, `escalation`. **Filtrados**: `LangGraph`, `__start__`, `ChannelWrite`, `ChannelRead`, `__end__`. |
| `token` | `{type:"token", content:"<chunk>"}` | Streaming token a token (vienen del LLM del synthesizer principalmente). **CUIDADO**: estos tokens son pre-guardrail; la respuesta autoritativa final viene en `done`. |
| `done` | `{type:"done", response:"<final post-guardrail>", case_id:"<uuid>"}` | Fin del turno. `response` ya tiene disclaimer concatenado. |
| `error` | `{type:"error", code:"...", message:"..."}` | Códigos: `unauthorized` (auth fail → close 1008), `invalid_message`, `forbidden` (case_id de otro user), `rate_limited`, `timeout` (close 1011), `graph_error` (close 1011) |

**WebSocket close codes**:
- `1008` — auth/policy violation (no reconectar con mismo token)
- `1011` — server error (timeout/graph_error — reintento OK)

**Flujo:**
1. Conectar → recibir `accept`
2. Enviar `{type:"auth", token}` ANTES de 10s
3. Recibir `auth_ok` o `error+close(1008)`
4. Loop: enviar `message` → recibir secuencia `agent_start*` + `token*` + `done`
5. Cada 30s recibir `pong` espontáneo (heartbeat); el cliente puede enviar `ping` en cualquier momento

**Persistencia**: el backend persiste `(user_message, response_text)` en Redis (window) y opcionalmente en `messages` PG si está cableado. El cliente NO necesita reenviar historial — el servidor lo carga vía `case_id`.

**Reglas para el frontend**:
- Mostrar **progress UI fuerte** durante los 50-125s (`agent_start` te da hitos: "Evaluando triage...", "Consultando especialistas...", "Sintetizando respuesta...").
- **Buffering**: opcionalmente mostrar tokens en streaming pero **el texto autoritativo es `done.response`**. Si el guardrail interrumpe, los tokens streamed serán reemplazados.
- Si el último frame fue `error code:"timeout"` o `code:"graph_error"`, ofrecer botón "Reintentar".
- Si `code:"rate_limited"`, mostrar "esperá 60s" — la conexión se mantiene abierta.

### 4.3 Documents — `/api/v1/documents/*`

| Método | Path | Auth | Body | Response | Errores |
|--------|------|------|------|----------|---------|
| POST | `/documents/upload` | user JWT | `multipart`: `file` + `case_id?` | 201 doc summary (status=pending) | 400 invalid mime, 413 too large (>20MB), 401 |
| GET | `/documents/?skip=0&limit=20` | user JWT | — | array doc summaries | 401 |
| GET | `/documents/{id}` | user JWT | — | doc + `lab_values[]` | 403 not your doc, 404, 401 |
| DELETE | `/documents/{id}` | user JWT | — | 204 | 403, 404, 401 |

**Para UI**: siempre POST con `multipart/form-data`. Validá tamaño/mime client-side ANTES de subir (UX), pero el server es autoridad. El procesamiento es **asíncrono** — pollear `GET /documents/{id}` cada 2-3s hasta `processing_status="done"` o `"failed"`.

### 4.4 Admin — `/api/v1/admin/*` (todos requieren `role="admin"`)

| Método | Path | Notas |
|--------|------|-------|
| GET | `/admin/metrics` | Cache 5 min — `{total_cases, total_users, total_documents, kb_chunks, cases_by_status, triage_distribution}` |
| GET | `/admin/audit-log?page&page_size&action&user_id` | Paginado, max page_size=100 |
| GET | `/admin/audit/verify-chain` | `AuditChainStatus { ok: bool, broken_ids: [uuid], checked_at: ISO8601 }` — **integridad del chain** |
| GET | `/admin/users?page&page_size` | Paginado |
| GET | `/admin/users/{id}` | Detalle |
| PATCH | `/admin/users/{id}` | `{role?, subscription_tier?, is_active?}` — guard "última admin" (no podés demote al último) |
| GET | `/admin/kb?page&page_size&source?` | KB chunks (content trunc a 200 chars) |
| POST | `/admin/kb` | Crear chunk + embedding |
| DELETE | `/admin/kb/{id}` | 204 |
| GET | `/admin/kb/stats` | `{by_source: [...], total}` |
| POST | `/admin/kb/ingest` | 202 — dispara reingesta MedlinePlus en background |
| POST | `/admin/credentials` | Crear API key — `{provider, label, plaintext_key, activate?}` |
| GET | `/admin/credentials` | Listar (sin secretos) |
| PATCH | `/admin/credentials/{id}/rotate` | `{plaintext_key}` |
| PATCH | `/admin/credentials/{id}/activate` | Activa esta y desactiva resto del mismo provider |
| DELETE | `/admin/credentials/{id}` | 204 |

**Para UI admin**:
- Form de credencial con campo **password-like** para `plaintext_key` (no mostrar después de POST — el server NO lo retorna).
- Banner de "última admin" cuando intenta demote.
- Para `/audit/verify-chain`: status pill con polling diario o botón "Verificar ahora".

### 4.5 Export — `/api/v1/cases/{case_id}/export/pdf`

```
GET /api/v1/cases/{case_id}/export/pdf
Auth: user JWT
Response: application/pdf (Content-Disposition: attachment; filename=case_<uuid>.pdf)
Errors: 403 (not yours), 404
```

Genera PDF de la sesión clínica para que el paciente lleve al médico de cabecera. **Para UI**: botón "Descargar PDF" en cada Case del historial.

### 4.6 Health

```
GET /health        → {status: "healthy", service, version}
GET /health/ready  → {status: "ready"|"degraded", components: {postgres, redis, storage}, version}
```

---

## 5. Estados y flujos clave del usuario

### 5.1 Onboarding / Auth

```
[/login] ── click "Crear cuenta" ──> [/register]
[/register] ── POST /auth/register ──> token guardado ──> [/dashboard]
[/login] ── POST /auth/login ──> token guardado ──> [/dashboard]
```

**⚠️ Faltan en backend** (planeá vos cómo lo simulamos vs. ocultamos):
- **No hay verificación de email** (`is_verified` existe pero no hay endpoint de send/confirm)
- **No hay password reset** ("olvidé mi contraseña")
- **No hay 2FA**

### 5.2 Sesión clínica completa (chat)

```
1. /chat (page mount)
   └─ open WS /api/v1/chat/ws
   └─ send {type:"auth", token}
   └─ receive auth_ok ─────────────────────────────► state: idle

2. usuario tipea + envía
   └─ send {type:"message", content, case_id?} ───► state: connecting/sending
   └─ receive agent_start "triage" ───────────────► state: triage (~3s)
   └─ Path A: triage RED + red_flags
        └─ receive agent_start "escalation"
        └─ receive done(response with ⚠️ ATENCIÓN) ─► state: ESCALATION (UI especial)
   └─ Path B: triage no-red
        └─ receive agent_start "anamnesis" (opcional, ~3-6s)
        └─ receive agent_start "classification" (~3s)
        └─ receive agent_start "specialists" (~10-30s — paralelo)
        └─ Path B1 (green o yellow consensus)
             └─ receive agent_start "synthesizer" (~10s, streaming tokens)
             └─ receive token* (stream)
        └─ Path B2 (yellow sin consenso)
             └─ receive agent_start "medical_board" (~20-40s, smart-tier)
             └─ optionally agent_start "devils_advocate" / "anamnesis"
             └─ receive agent_start "synthesizer"
             └─ receive token* (stream)
        └─ receive agent_start "guardrail" (~3s)
             └─ Path B-guard-pass: receive done(response) ─► state: done (UI normal)
             └─ Path B-guard-block: receive agent_start "escalation"
                                    receive done(response with safety msg) ─► state: blocked
```

### 5.3 Estados de UI durante WS

| Estado | Trigger | Qué mostrar |
|--------|---------|-------------|
| `connecting` | open WS | Spinner pequeño, "Conectando..." |
| `authenticating` | sent auth | "Verificando sesión..." |
| `authenticated` / `idle` | received auth_ok | Composer habilitado |
| `sending` | user clicked send | Burbuja del usuario aparece, composer disabled |
| `triaging` | agent_start "triage" | "Evaluando urgencia..." (chip 🟢🟡🔴 placeholder gris) |
| `gathering` | agent_start "anamnesis" | "Recogiendo más datos..." |
| `classifying` | agent_start "classification" | "Identificando especialidades..." |
| `consulting` | agent_start "specialists" | Chips de especialistas activadas en gris → coloreadas a medida que cierran (ojo: el frontend hoy no recibe `chain_end` de cada especialista — solo el agregado. Diseñá pensando en chips activas, sin progreso individual.) |
| `deliberating` | agent_start "medical_board" | "Mesa médica deliberando..." (icono de balanza). En P95 esto agrega 30-40s. |
| `streaming` | recibiendo `token` | Burbuja del asistente con cursor animado, tokens fluyendo |
| `safety_check` | agent_start "guardrail" | "Revisando recomendaciones..." (~3s — micro-pausa) |
| `done` | recibió `done` | Burbuja final con disclaimer separado (`---`) |
| `escalation` | agent_start "escalation" | **Vista especial roja** (ver §5.5) |
| `error` | recibió `error` | Toast/banner según `code` (ver §5.6) |

### 5.4 Loading time esperado — **DISEÑO CRÍTICO**

- **P50: 50s · P95: 125s.** Eternidad para un usuario.
- **Mostrar progreso narrativo**: "Te estamos escuchando", "Triando urgencia", "Llamando a Cardiología y Neurología", "Mesa médica deliberando", "Sintetizando recomendaciones".
- **Skeleton de la respuesta**: cuando empiecen los `token`, mostrar burbuja vacía con cursor parpadeante. Cuando lleguen tokens, escribilos.
- **Cancel button** (a discutir): si el usuario quiere abortar, podés cerrar la WS y reabrir; el backend ya tiene `GRAPH_TIMEOUT=120s`.
- **Anti-frustración**: agregá un mensaje de "demoramos hasta 2 min porque tu caso es revisado por varios especialistas" en el primer turno.

### 5.5 Escalation (RED) — **CRÍTICO**

Cuando el usuario recibe `done` después de `agent_start "escalation"` con triage RED, el `response` empieza con `⚠️ ATENCIÓN`. Texto literal:

```
⚠️ ATENCIÓN: Se detectaron señales que requieren atención médica inmediata.

Señales detectadas: <red_flags>

Por favor, acude a urgencias o llama a servicios de emergencia lo antes posible.

Este sistema no puede atender emergencias médicas.
Si estás en peligro inmediato, llama al número de emergencias de tu país.

---

MedAgent es una herramienta de orientación; no reemplaza la consulta médica profesional.
```

**Para UI**:
- **Hero card rojo full-width** con icono ⚠️ + headline.
- Lista de red_flags como bullets destacados.
- **CTAs grandes**:
  - 🚑 **107** (SAME — Argentina)
  - 📞 **Llamar emergencias** → `tel:107`
  - 🏥 **Hospitales cercanos** → opcional: link a Google Maps con `?q=hospital%20cerca`
- **NO mostrar el composer** (input deshabilitado) — el sistema NO continúa el chat normal. El usuario debe abrir un caso nuevo si quiere consultar otra cosa.
- Botón secundario: "Crear nuevo caso" (resetea `case_id`).

### 5.6 Manejo de errores

| `error.code` | Mensaje al usuario | Acción de UI |
|--------------|--------------------|--------------|
| `unauthorized` | "Sesión vencida. Iniciá sesión otra vez." | Logout + redirect `/login`. WS cierra con 1008. |
| `invalid_message` | "El mensaje no se entendió. Probá de nuevo." | Toast + composer habilitado. |
| `forbidden` | "No podés acceder a esta sesión." | Toast. |
| `rate_limited` | "Esperá un momento antes del próximo mensaje." | Toast con cuenta regresiva 60s. WS sigue abierta. |
| `timeout` | "Tu consulta tardó demasiado. Reintentá." | Botón "Reintentar". WS cierra 1011 → reabrir. |
| `graph_error` | "Hubo un error procesando tu consulta. Reintentá en unos minutos." | Botón "Reintentar". WS cierra 1011. |
| `invalid_input` (futuro / prompt guard) | "Reformulá tu consulta describiendo síntomas, intensidad y desde cuándo." | Toast didáctico. |

### 5.7 Disclaimer obligatorio (legal)

Texto literal definido en `app/agents/synthesizer/agent.py`:

```
MedAgent es una herramienta de orientación; no reemplaza la consulta médica profesional.
```

Separador antes del disclaimer en el `response`: `\n\n---\n\n`.

⚠️ **OJO**: el branding interno todavía dice **"MedAgent"** en el código aunque el producto se llama **Tuki-Medic**. Coordinar con product cuándo migrar el string. Si la UI lo renderiza tal cual viene, el usuario va a leer "MedAgent". Recomendación: o se cambia el constante backend (1 línea) o el frontend hace replace del string a "Tuki-Medic" (frágil).

**Render**: el disclaimer debe ser **visualmente separado** (regla horizontal `<hr>` o card secundaria gris-clarito), nunca confundirse con el contenido clínico.

---

## 6. Tier gating (free vs. paid)

### 6.1 Estado actual del backend

- `User.subscription_tier: str` con default `"free"`. Validación pydantic en `AdminUserPatch` permite `"free"` | `"paid"`.
- **NO hay middleware de gating implementado**. Cualquier usuario activo puede usar todos los endpoints excepto `/admin/*`.
- El admin puede setear el tier vía `PATCH /admin/users/{id}`.

### 6.2 Recomendación de producto (para que el frontend deje preparados los hooks)

| Feature | Free | Paid |
|---------|------|------|
| Chat con triage + 1 specialty | ✅ | ✅ |
| Chat con multi-specialist + medical_board (deliberación completa) | ❌ (degradado a 1 spec) | ✅ |
| Document upload | 3 docs/mes | ilimitado |
| Export PDF | ❌ | ✅ |
| Patient timeline / historial | últimas 5 consultas | completo |
| Foto upload (derma) | ❌ | ✅ |

**Para UI**: ya diseñá las paywalls ("Esta función está en Tuki Pro" + CTA upgrade). El frontend lee `auth.user.subscription_tier` y bloquea el flujo. Backend lo va a aplicar después.

---

## 7. Seguridad y guardrails que afectan UI

### 7.1 Rate limiting

- **REST**: SlowAPI middleware. Límites por endpoint:
  - `/auth/register`: 3/hour por IP
  - `/auth/login`: 5/min por IP
  - `/auth/refresh`: 10/min
  - `/auth/me` (DELETE): 3/hour
- **WS**: 10 messages / 60s por usuario (Redis INCR). El frame `error code:"rate_limited"` se emite y la conexión se mantiene.
- **UI**: handle 429 → toast "Esperá X segundos antes de reintentar". Nunca encolar mensajes silenciosamente — frustrante.

### 7.2 Security headers (`SecurityHeadersMiddleware`)

⚠️ No pude leer el archivo exactamente, pero por el comentario en `main.py` aplican:
- **HSTS** (Strict-Transport-Security)
- **CSP** (Content-Security-Policy) — restringe sources
- **X-Frame-Options: DENY** → **el frontend NO puede ser embebido en un iframe** (importante si pensabas mostrarlo dentro de otra app).
- **X-Content-Type-Options: nosniff**
- **Permissions-Policy** — bloquea cámara/mic/geo a menos que estén explícitamente habilitados.

**Implicación de diseño**: si querés foto upload (derma) tomada **directamente desde el browser con `<input type="file" capture="environment">`**, eso debería funcionar (es file picker, no `getUserMedia`). Si querés grabar audio o usar webcam viva, **necesitás coordinar con backend para permitir esos features en Permissions-Policy** primero.

### 7.3 Prompt injection guard

`app/core/prompt_guard.py` filtra patrones conocidos en el mensaje del usuario. Si dispara:
- El triage NO llama al LLM → devuelve YELLOW + confidence 0.2.
- El usuario recibe una respuesta normal pero con tono "no podemos procesar de forma segura, reformulá".

**Para UI**: NO mostrás un error visible al usuario hoy (el sistema responde igual con un yellow defensivo). Pero podrías mostrar un hint si detectás server-side patterns conocidos antes de mandar (low-priority).

### 7.4 LLM output sanitization

`app/core/sanitize.py:sanitize_patient_markdown` se aplica a TODA respuesta antes de llegar al WS. Remueve:
- HTML tags
- URLs con esquemas peligrosos (sólo http/https permitido — allowlist)
- Markdown image references (`![]()`)
- Caracteres Unicode zero-width

**Para UI**: si renderizás markdown:
- ✅ Usá `react-markdown` con `rehype-sanitize` (defensa en profundidad — el server ya sanitiza pero no confíes).
- ❌ NUNCA `dangerouslySetInnerHTML`.
- Renderizá: headings (h1-h6), bold, italic, lists, links, code blocks, hr.
- Bloqueá: imágenes, raw HTML, scripts.

### 7.5 Audit chain

- Cada decisión clínica firma un hash. Endpoint `GET /admin/audit/verify-chain` → `{ok, broken_ids, checked_at}`.
- **UI admin**: badge en topbar admin tipo:
  - 🟢 "Audit chain íntegro · verificado hace 1h"
  - 🔴 "Chain corrupto: 2 entradas inválidas" + link a tabla audit-log filtrada.
- Polling: 5-10 min, o botón "Verificar ahora".

---

## 8. Cobertura clínica actual (specialists)

10 agentes especialistas registrados (`app/agents/specialists/__init__.py`):

| Specialty key | Cubre |
|---------------|-------|
| `medicina_general` | Consultas no-específicas, síntomas vagos, prevención. Family medicine cae aquí (alias). |
| `medicina_interna` | Adultos, multi-sistema, comorbilidades. |
| `pediatria` | <14 años. |
| `ginecologia` | Salud femenina + embarazo (alias `obstetricia`). |
| `cardiologia` | Cardiovascular: dolor torácico, palpitaciones, HTA, etc. |
| `traumatologia` | Lesiones musculoesqueléticas, ortopedia, medicina deportiva (aliases). |
| `neurologia` | Cefaleas, mareos, déficit motor/sensitivo, convulsiones. |
| `dermatologia` | Lesiones de piel, rash, alergias dérmicas. **Acepta foto upload**. |
| `endocrinologia` | Diabetes, tiroides, metabolismo. |
| `farmacologia` | Interacciones, dosis, efectos adversos. Schema extendido `PharmacologyAnalysis` con lista de `DrugInteraction`. |

**Aliases interesantes para UI** (cuando renderizás chips de "especialidades consultadas", normalizá nombres):
- "Traumatología y Ortopedia" / "Ortopedia" / "Medicina Deportiva" → muestra "Traumatología"
- "Obstetricia" / "Ginecología y Obstetricia" → muestra "Ginecología"
- "Medicina General/Familiar" → muestra "Medicina General"

**Consultas reales esperadas** (de `backend/tests/clinical_eval/cases/*.yaml` — no leí los YAML pero las trazas en código apuntan a):
- Pediatría administrativa (dosis paracetamol)
- HTA + interacciones (farmacología)
- Cefaleas leves (medicina general / neuro)
- Higiene del sueño (medicina general)
- Fiebre + decaimiento en lactante (pediatría / medicina general)
- Dolor torácico agudo (cardio — RED)
- Stroke prodromos (neuro — RED)
- Embarazo + sangrado (gineco — RED)
- Trauma deportivo (traumatología)
- Rash en pediátrico (derma + foto)

---

## 9. Tono y voz de marca

### 9.1 Idioma

- **Español rioplatense** (voseo): "tenés", "podés", "consultá", "reformulá".
- **NO neutro**: el código está lleno de "vos", "te recomendamos", "basándonos en lo que nos contás".
- Sin español de España. Sin "tú".

### 9.2 Registro

- **Cálido pero clínico-formal**.
- **NO médico paternalista** ("vamos a ver, mi querido…")
- **NO chatbot informal** ("dale, copado, viste")
- Empático sin ser meloso. Directo sin ser cortante.
- **Frases cortas** (synth prompt: "Frases cortas y directas").
- **Cero jerga sin explicar**. Ejemplo del prompt: NO "taquicardia" sino "el corazón latiendo más rápido de lo normal".

### 9.3 Estructura del mensaje sintetizado (lo que renderiza el frontend)

El synthesizer prompt instruye a producir respuestas con esta estructura — el frontend puede asumirla y stylearla con secciones visuales (headings + dividers):

1. **Lo que evaluamos** — qué especialidades revisaron
2. **Lo que encontramos** — hallazgos sin diagnóstico definitivo
3. **Signos a vigilar** — alarm signs (lista)
4. **Próximos pasos** — qué hacer ahora (rutina/24-48h/hoy/urgencia)
5. **Disclaimer** — siempre al final, separado por `---`

⚠️ Pero el LLM no siempre cumple la estructura literal. Renderizá markdown con buen typography (headings, listas, hr) y vas a obtener algo legible casi siempre.

### 9.4 Disclaimer literal

```
MedAgent es una herramienta de orientación; no reemplaza la consulta médica profesional.
```

Separador: `\n\n---\n\n`. (Render como `<hr>` con margen vertical generoso.)

---

## 10. Pendientes / known issues que afectan diseño

| Issue | Impacto en diseño |
|-------|-------------------|
| **Latencia P95 125s** | Progress UI fuerte, mensajería narrativa, expectation management ("este análisis tarda hasta 2 minutos") |
| **green-003 flaky** (eval 24/25) | El LLM a veces clasifica yellow cuando el usuario espera green. Mostrá la `attention_level` con un tone de "consultá pronto" empático, no alarmista. Evitar pánico sobre síntomas que el usuario considera leves. |
| **No hay i18n** | Todo el español está hardcodeado en backend (prompts, fallbacks, escalation msg). El frontend debería usar i18n (next-intl, react-intl) DESDE EL DÍA 1 incluso con un solo locale `es-AR`, para no rehacer luego. |
| **Branding "MedAgent" residual** | El disclaimer y el escalation msg dicen "MedAgent", no "Tuki-Medic". Decisión de producto: dejar como está hasta migrar backend, o el frontend hace string replace en render (frágil pero funcional). |
| **No email verify ni password reset** | UI debe ocultar "olvidé contraseña" en `/login` y "verificá tu email" en signup, o hacer wireframes pero marcarlos `[stub]`. |
| **Tier gating no implementado** | Pero el campo existe. Diseñá paywalls; el backend va a alinearse después. |
| **Frontend actual = stubs** | Hay scaffolding de Next.js + páginas con placeholder, pero el sistema visual completo es greenfield. Diseñá design tokens, componentes (chat bubble, agent badge, triage chip, alarm card, escalation hero, paywall, etc.) desde cero. |
| **WS no manda `attention_level` ni `alarm_signs` separados** | Hoy todo viene fundido en `done.response`. Si querés badges/cards específicos (chip de "ATENCIÓN: hoy" + lista de alarmas), hay que extender el contrato del WS. **Sugerencia**: `done` debería incluir `{response, attention_level, alarm_signs[], specialties_involved[], follow_up_questions[]}` aprovechando que el backend YA los produce. |
| **Document processing async** | El UI debe mostrar estado "procesando" y permitir consultar el chat usando el doc aunque no esté listo (el chat referencia docs por ID). |

---

## 11. Casos de uso priorizados (top 5 para mockups)

1. **GREEN — Pediatría administrativa**  
   _"Mi nena de 4 años pesa 17 kg, tiene 37.8°C de fiebre. ¿Cuánto paracetamol le doy?"_  
   → triage `green` · synth: dosis pediátrica + signos de alarma + "rutina"  
   → **Mockup**: respuesta tranquila, dosis presentada como tabla compacta, sin alarmas.

2. **YELLOW — Musculoesquelético**  
   _"Hace 3 días corrí y me lastimé la rodilla, hincha y duele al apoyar."_  
   → triage `yellow` · specialists: traumatología + medicina general · attention `24-48h`  
   → **Mockup**: chips activas Traumatología + General, recommendations, "consultá en 24-48h", alarm signs.

3. **RED — Cardio agudo**  
   _"Tengo dolor en el pecho que me agarra el brazo izquierdo, sudo frío, hace 20 min."_  
   → triage `red` con red_flags `["dolor torácico agudo + irradiación", "diaforesis"]` · escalation directa  
   → **Mockup**: hero rojo ⚠️, lista de red_flags, CTA `tel:107`, composer **disabled**.

4. **ESCALATION — Neurológico (cefalea súbita)**  
   _"Tengo la peor jaqueca de mi vida, vino de golpe hace 10 min, no había tenido antes."_  
   → triage `red` (red_flag: "cefalea peor de mi vida")  
   → **Mockup**: misma escalation card, pero remarcar que la diferencia con migraña común está en el inicio súbito.

5. **DERMA + foto upload**  
   _"Me salió esta mancha rara en el brazo." [adjunta foto]_  
   → POST `/documents/upload` (image/jpeg, case_id) → polling status → chat con dermatologia consultada  
   → **Mockup**: composer con botón 📎, preview del thumb, indicador "procesando OCR/clasificación", luego respuesta con dermatologia + recomendaciones.

---

## 12. Open questions que el diseño tiene que resolver

| # | Pregunta | Datos del backend | Recomendación |
|---|----------|-------------------|---------------|
| 1 | **¿Multi-paciente?** ¿El user consulta para sí o para hijos/familia? | `User` tiene `birth_year`, `biological_sex` propios. `PatientProfile` es **1:1 con user**. NO hay tabla "dependientes". | **MVP: solo el user**. Si quiere consultar por hijo, lo pone en el mensaje ("mi nena de 4 años"). En v2: agregar `Dependents` table. |
| 2 | **¿Historial de sesiones?** | `Case` + `Message` se persisten en PG. NO hay endpoint REST `GET /cases` hoy — solo se accede vía `case_id` en el WS. | Backend necesita un `GET /api/v1/cases?status=active`. Diseñá la pantalla `/history` asumiendo que va a existir. |
| 3 | **¿Foto upload para derma?** | Soportado (`image/jpeg`, `image/png`). Background OCR + clasificación. NO hay vision-LLM aún. | Mockup desde día 1 — sólo asegurate que el prompt al especialista mencione "el paciente subió una foto" hasta que se conecte el vision pipeline. |
| 4 | **¿Export PDF compartible con médico?** | ✅ Existe: `GET /api/v1/cases/{id}/export/pdf`. | Botón "Llevarle esto a mi médico" en cada Case del historial. |
| 5 | **¿Notificaciones push? Email summary?** | NO hay infra de notificaciones, ni email transactional, ni mailers. | Out of scope MVP. En v2: email summary post-consulta (si user opt-in en `preferences`). |
| 6 | **¿Edición de PatientProfile?** | El profile se popula automáticamente. NO hay endpoint PUT `/profile`. | Decidir si exponemos formulario "ficha clínica" — UX gana mucho, pero requiere endpoint nuevo. |
| 7 | **¿Multi-device sync?** | JWT + Redis sessions, sí soportable. NO hay sync explícito hoy. | Funciona en multi-tab por simple JWT en localStorage. |
| 8 | **¿Modo oscuro?** | Sin opinión backend. | Hacelo. Es 2026. |
| 9 | **¿Voice input?** | Permissions-Policy bloquea mic por default. | v2 — requiere coordinación backend para Permissions-Policy. |
| 10 | **¿Onboarding tutorial?** | Sin opinión backend. | Recomendado: 3 pantallas explicando "qué hace / qué NO hace / disclaimer" antes del primer chat. |

---

## TL;DR ejecutivo

1. **Producto**: chat de orientación médica multi-agente en español rioplatense. NO diagnostica, NO receta. Disclaimer legal obligatorio en cada respuesta.
2. **Latencia 50-125s ⇒ progreso narrativo es ESENCIAL**. El frontend recibe `agent_start` por cada nodo del grafo (triage, anamnesis, classification, specialists, medical_board, guardrail, synthesizer) — usalos para construir un timeline de progreso que mantenga al usuario enganchado.
3. **WebSocket es el contrato crítico**: `auth → message → (agent_start* + token* + done) | error`. El texto autoritativo está en `done.response`, ya con disclaimer concatenado. Los `token` streamed son pre-guardrail y pueden ser sobreescritos.
4. **Escalation (RED) es una vista totalmente distinta**: hero rojo + CTAs de emergencia + composer disabled. Disparada por `triage_level=red` y/o red_flags. El usuario no debe poder seguir el chat normal en este estado.
5. **Frontend actual es esqueleto**: hay Next.js App Router + páginas placeholder + 2 primitives shadcn. **El sistema visual completo (chat bubbles, agent badges, triage chips, attention-level pills, alarm cards, escalation hero, paywall, document viewer, audit-chain badge admin) es greenfield**. Diseñá design tokens y componentes desde cero, pensando en 10 specialties, 4 niveles de atención (rutina/24-48h/hoy/urgencia), 3 niveles de triage (green/yellow/red), y un disclaimer que NO se debe perder visualmente nunca.

---

_Documento generado read-only, sin tocar el repo. Fuentes verificadas: `backend/app/main.py`, `app/api/v1/{auth,chat,documents,admin,export}.py`, `app/models/*.py`, `app/schemas/{auth,admin}.py`, `app/agents/{triage,synthesizer,specialists}/*.py`, `app/orchestrator/graph.py`, frontend tree (`frontend/src/{app,components,hooks,lib,store}`)._
