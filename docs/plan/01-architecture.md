# 01 — Arquitectura del Sistema

## 1. Vista General

MedAgent sigue una arquitectura de **3 capas** con un motor de orquestación central:

```
┌─────────────────────────────────────────────────────────────┐
│                     CAPA DE PRESENTACIÓN                     │
│         Next.js 15 · TypeScript · Tailwind · shadcn/ui       │
│    Chat UI · Upload · Case History · Settings · Dashboard    │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket (streaming) + REST (CRUD)
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      CAPA DE APLICACIÓN                      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              API Gateway (FastAPI)                     │   │
│  │   Auth · Rate Limit · Validation · File Upload        │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │         Motor de Orquestación (LangGraph)             │   │
│  │                                                       │   │
│  │  Orchestrator → Triage → Anamnesis → Classification   │   │
│  │       ↓              ↓          ↓                     │   │
│  │  Specialist Agents (N) → Mesa Médica → Synthesizer    │   │
│  │       ↓                    ↓               ↓          │   │
│  │  ┌─ Devil's Advocate ─┘   Loop Control                │   │
│  │  │                                                    │   │
│  │  └─ Guardrail Agent (monitor paralelo en tiempo real) │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │           Servicios de Soporte                        │   │
│  │  Memory Manager · Doc Processor · Knowledge Retriever │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
└─────────────────────────┼────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                      CAPA DE DATOS                            │
│                                                               │
│  PostgreSQL     Redis       S3/MinIO     pgvector             │
│  (structured)   (cache)     (files)      (embeddings)         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## 2. Componentes principales

### 2.1 API Gateway (FastAPI)

Punto de entrada único para todas las peticiones del frontend.

**Responsabilidades:**
- Autenticación y autorización (JWT)
- Rate limiting por usuario
- Validación de input (Pydantic models)
- File upload con validación de formato/tamaño
- WebSocket management para streaming
- CORS, logging, error handling

**Endpoints principales:**
- `POST /api/v1/chat/message` — Enviar mensaje al sistema
- `WS /api/v1/chat/stream/{case_id}` — WebSocket para streaming
- `POST /api/v1/documents/upload` — Subir documento
- `GET /api/v1/cases/{case_id}/history` — Historial del caso
- `GET /api/v1/cases/{case_id}/summary` — Resumen clínico
- `POST /api/v1/auth/login` — Login
- `POST /api/v1/auth/register` — Registro

### 2.2 Motor de Orquestación (LangGraph)

El corazón del sistema. Un **StateGraph** que define el flujo de ejecución de agentes.

**Características clave:**
- Grafos con ciclos (loops deliberativos)
- Estado compartido tipado (ClinicalCaseState)
- Checkpointing para recovery y debugging
- Ruteo condicional basado en estado
- Ejecución paralela de agentes cuando es posible
- Límite de iteraciones configurable (safety)

**Nodos del grafo:**
1. `triage_node` — Clasificación de urgencia
2. `anamnesis_node` — Preguntas clínicas dirigidas
3. `classification_node` — Selección de especialidades
4. `specialist_node` — Ejecución de agentes especializados (paralelo)
5. `medical_board_node` — Mesa Médica: debate multi-ronda entre especialistas (reemplaza reviewer)
6. `devils_advocate_node` — Desafía conclusiones para evitar falso consenso
7. `guardrail_node` — Monitor de seguridad en tiempo real (paralelo con cada nodo)
8. `clarification_node` — Solicitud de info faltante
9. `synthesizer_node` — Consolidación de respuesta

**Edges condicionales:**
- `classification → specialist`: rutea a 1-N especialidades según scoring
- `specialist → medical_board`: los análisis pasan a la Mesa Médica
- `medical_board → devils_advocate`: Round 2 — desafío de conclusiones
- `devils_advocate → medical_board`: Round 3 — especialistas responden y ajustan
- `medical_board → synthesizer`: si hay consenso
- `medical_board → medical_board`: si hay desacuerdo → ronda extra
- `medical_board → clarification`: si falta información crítica
- `clarification → specialist`: loop back con nueva información
- `guardrail → INTERRUPT`: puede interrumpir cualquier nodo en tiempo real si detecta riesgo
- `synthesizer → END`: respuesta final (guardrail ya validó en paralelo)

### 2.3 Servicios de Soporte

#### Memory Manager
- Gestiona los 3 niveles de memoria
- Decide qué guardar, dónde y cuándo comprimir
- Recupera contexto relevante por caso
- Ver detalle en `04-memory-system.md`

#### Document Processor
- Pipeline de ingestión de archivos
- OCR, clasificación, extracción de datos
- Vinculación con el caso activo
- Ver detalle en `06-document-processing.md`

#### Knowledge Retriever
- Búsqueda RAG en la base de conocimiento médico
- Retrieval semántico por síntomas, condiciones, medicamentos
- Grounding de respuestas con evidencia
- Ver detalle en `05-knowledge-base.md`

## 3. Patrones arquitectónicos

### 3.1 Event-Driven dentro del grafo
Cada nodo del grafo emite eventos que el sistema puede observar:
- `agent.started` — Un agente comenzó a ejecutarse
- `agent.completed` — Un agente terminó con resultado
- `agent.escalated` — Un agente detectó algo que requiere escalamiento
- `loop.iteration` — Se inició un nuevo ciclo de deliberación
- `case.synthesized` — Se generó una respuesta final

### 3.2 Streaming Pipeline
```
LangGraph Node (generating)
    │ token por token
    ▼
Streaming Buffer
    │ 
    ▼
WebSocket Server
    │
    ▼
Frontend (render incremental)
```

El usuario ve la respuesta construirse en tiempo real, incluso mientras el sistema todavía está en fase de síntesis.

### 3.3 Separation of Concerns
- **Agentes** solo tienen lógica clínica (no saben de DB, auth, files)
- **Servicios** manejan infraestructura (DB, cache, storage)
- **Gateway** maneja comunicación (HTTP, WS, auth)
- **Orquestador** maneja flujo (quién ejecuta, cuándo, loops)

### 3.4 Plugin Architecture para especialidades
Cada especialidad médica es un **plugin** que se registra en el sistema:

```python
@register_specialty("cardiologia")
class CardiologyAgent(BaseSpecialistAgent):
    name = "Cardiología"
    triggers = ["dolor torácico", "palpitaciones", "hipertensión", ...]
    knowledge_scope = "cardiology"
    risk_level = "high"  # especialidad de alto riesgo
    
    async def analyze(self, state: ClinicalCaseState) -> SpecialistAnalysis:
        # Lógica específica de cardiología
        ...
```

Esto permite agregar nuevas especialidades **sin tocar el core**.

## 4. Comunicación entre capas

### Frontend ↔ API Gateway
- **REST** para CRUD (casos, documentos, auth)
- **WebSocket** para chat en tiempo real (streaming de tokens)
- **Server-Sent Events** como fallback si WS no está disponible

### API Gateway ↔ Orquestador
- Invocación directa (Python → Python, misma instancia en MVP)
- En futuro: message queue (Redis Streams o RabbitMQ) para escalar

### Orquestador ↔ LLM
- OpenAI API (GPT-4o) como LLM principal
- Anthropic API (Claude) como fallback/alternativa
- Cada agente puede usar un modelo diferente según necesidad:
  - Triage: modelo rápido (GPT-4o-mini)
  - Especialistas: modelo completo (GPT-4o)
  - Síntesis: modelo completo (GPT-4o)

### Orquestador ↔ Base de datos
- SQLAlchemy (async) para PostgreSQL
- Redis client (aioredis) para cache
- boto3 / MinIO client para files

## 5. Escalabilidad

### MVP (monolito inteligente):
- Un solo servicio FastAPI con LangGraph embebido
- PostgreSQL + Redis + MinIO en contenedores
- Deploy en Railway / Fly.io
- Soporta ~100-500 usuarios concurrentes

### Producción (microservicios):
- API Gateway separado del motor de orquestación
- Workers de LangGraph en pool (Celery o similar)
- PostgreSQL con read replicas
- Redis cluster
- S3 para storage
- Kubernetes para orquestación de infra
- Soporta ~10K+ usuarios concurrentes

## 6. Seguridad de la arquitectura

- **HTTPS obligatorio** en todas las comunicaciones
- **JWT tokens** con refresh rotation
- **Input sanitization** en todo endpoint
- **File validation** antes de procesamiento
- **Rate limiting** por usuario y por IP
- **Audit log** de todas las acciones del sistema
- **Encriptación at rest** para datos clínicos
- **No training** con datos del usuario (contratos con proveedores de LLM)
