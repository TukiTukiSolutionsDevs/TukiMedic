# 12 — Stack Tecnológico con Reasoning

## 1. Criterios de selección

Cada tecnología fue elegida evaluando:
1. **Fit con el problema** — ¿resuelve lo que necesitamos?
2. **Madurez** — ¿es estable, bien documentada, con comunidad?
3. **Ecosistema** — ¿se integra bien con el resto del stack?
4. **DX** — ¿la experiencia de desarrollo es buena?
5. **Costo** — ¿es viable para un MVP?
6. **Escalabilidad** — ¿aguanta crecimiento?

## 2. Decisiones por capa

### Frontend: Next.js 15 + TypeScript + Tailwind + shadcn/ui

| Alternativa considerada | Por qué no |
|-------------------------|-----------|
| React puro (Vite) | Sin SSR nativo, sin API routes, más config manual |
| Remix | Buen framework pero menor ecosistema que Next.js |
| Vue/Nuxt | Ecosistema AI/componentes más limitado que React |
| Svelte/SvelteKit | Excelente DX pero menor ecosistema de componentes médicos |

**Por qué Next.js 15:**
- App Router con Server Components (reduce JS al cliente)
- API Routes para BFF (Backend for Frontend) si se necesita
- Streaming SSR nativo (útil para respuestas largas)
- Ecosistema React gigante (shadcn, React Query, Zustand)
- Deploy trivial en Vercel, Railway, o Docker

**Por qué shadcn/ui:**
- No es una librería, son componentes que copiás a tu proyecto
- Accesibilidad (Radix UI base) incluida
- Totalmente customizable (Tailwind)
- Componentes profesionales sin look "genérico de librería"
- Perfecto para UI médica que necesita confianza y claridad

**Por qué Zustand sobre Redux:**
- 90% menos boilerplate
- API simple e intuitiva
- Perfecto para estado de chat (mensajes, caso activo, UI state)
- No necesitamos la complejidad de Redux para este caso

### Backend: FastAPI (Python)

| Alternativa | Por qué no |
|-------------|-----------|
| Express.js (Node) | Ecosistema AI/ML mucho menor que Python |
| NestJS (Node) | Mismo problema — el mundo de AI es Python |
| Django | Más pesado, ORM sincrónico, no tan bueno para async + streaming |
| Flask | Sin async nativo, sin validación automática |
| Go (Gin/Fiber) | Excelente performance pero LangGraph es Python |

**Por qué FastAPI:**
- **Async nativo** — crítico para llamadas concurrentes a LLMs
- **Pydantic** — validación de tipos automática (request/response)
- **OpenAPI auto** — docs generados automáticamente
- **WebSocket nativo** — streaming de chat
- **Python** — LangGraph, LangChain, OpenAI SDK, todo es Python
- Performance excelente para Python (uvicorn + ASGI)

### Orquestación de agentes: LangGraph

| Alternativa | Por qué no |
|-------------|-----------|
| CrewAI | Roles predefinidos, menos control sobre flujo |
| AutoGen | Orientado a conversación multi-agente, no a grafos deliberativos |
| Custom (asyncio) | Reinventar la rueda: checkpointing, state management, etc. |
| LangChain Agents | No soporta ciclos/loops nativamente |
| Semantic Kernel | Ecosistema Microsoft, menos flexible |

**Por qué LangGraph:**
- **Grafos con ciclos** — exactamente lo que necesita la orquestación deliberativa
- **Estado tipado compartido** — ClinicalCaseState accesible por todos los nodos
- **Checkpointing** — guarda estado en cada nodo (recovery + audit)
- **Ruteo condicional** — edges dinámicos según el estado
- **Ejecución paralela** — múltiples especialistas simultáneamente
- **Streaming de eventos** — cada nodo emite eventos en tiempo real
- **Madurez** — LangChain team, buena documentación, activamente mantenido

### LLM: OpenAI GPT-4o (principal) + Claude (fallback)

| Modelo | Uso | Razón |
|--------|-----|-------|
| GPT-4o | Especialistas, síntesis, seguridad | Mejor balance costo/capacidad, tool-use excelente |
| GPT-4o-mini | Triage, clasificación, extracción | Rápido, barato, suficiente para tareas de scoring |
| Claude 3.5 Sonnet | Fallback, respuestas largas | Excelente en análisis largo, buena alternativa |

**Ruteo por modelo:**
```python
MODEL_ROUTING = {
    "triage": "gpt-4o-mini",          # Rápido, scoring
    "anamnesis": "gpt-4o",            # Necesita generar preguntas clínicas
    "classification": "gpt-4o-mini",   # Scoring de especialidades
    "specialist": "gpt-4o",           # Análisis clínico complejo
    "reviewer": "gpt-4o",             # Detección de contradicciones
    "synthesizer": "gpt-4o",          # Consolidación de respuesta
    "safety": "gpt-4o",              # Validación de seguridad (no se escatima)
    "fact_extraction": "gpt-4o-mini", # Extracción de hechos
    "doc_classification": "gpt-4o-mini", # Clasificación de documentos
}
```

**Costos estimados por consulta:**
```
Triage (4o-mini):        ~$0.001
Anamnesis (4o):          ~$0.005
Classification (4o-mini): ~$0.001
2 Specialists (4o):      ~$0.020
Reviewer (4o):           ~$0.005
Synthesizer (4o):        ~$0.010
Safety (4o):             ~$0.005
───────────────────────
Total por consulta:      ~$0.05 - $0.10
Con 1 loop adicional:    ~$0.10 - $0.15
```

### Base de datos: PostgreSQL 16 + pgvector

| Alternativa | Por qué no |
|-------------|-----------|
| MongoDB | No necesitamos flexibilidad de schema — nuestros datos son estructurados |
| Pinecone | Servicio separado para vectores = más complejidad + costo |
| Weaviate | Bueno pero agregar otro servicio solo para vectores es overkill en MVP |
| Supabase | Es PostgreSQL por debajo, pero con vendor lock-in |

**Por qué PostgreSQL + pgvector:**
- **Un solo servicio** para structured data + vector search
- pgvector soporta IVFFlat y HNSW indexes (rápido para nuestro volumen)
- PostgreSQL es el estándar de la industria — maduro, confiable
- Full-text search en español incluido (tsvector)
- JSONB para datos semi-estructurados (extracted_data de documentos)
- Alembic para migraciones versionadas

### Cache: Redis

**Por qué Redis:**
- Memoria inmediata (Nivel 1) con TTL automático
- Session storage
- Rate limiting
- Pub/Sub para eventos en tiempo real (futuro)
- Extremadamente rápido (<1ms)

### File Storage: S3/MinIO

- MinIO en desarrollo (S3-compatible, self-hosted)
- S3 en producción
- Encriptación at rest (AES-256)
- Presigned URLs para acceso temporal

### OCR: Tesseract + Google Cloud Vision

- Tesseract: gratis, local, suficiente para documentos claros
- Cloud Vision: fallback cuando Tesseract no alcanza (PDFs escaneados borrosos)
- Costo de Cloud Vision: ~$1.50 por 1000 páginas

### Monitoring: LangSmith / LangFuse

| Tool | Uso |
|------|-----|
| LangSmith | Tracing de LangGraph, debugging de prompts, evaluaciones |
| LangFuse | Alternativa open-source, self-hosteable |

Se elige según preferencia de hosting:
- LangSmith si se prefiere SaaS (más features, menos setup)
- LangFuse si se necesita self-hosted (privacidad)

## 3. Resumen del stack

```
┌─ Frontend ─────────────────────────────────┐
│  Next.js 15 · TypeScript · Tailwind        │
│  shadcn/ui · Zustand · React Query         │
│  Socket.io-client · Framer Motion          │
├─ Backend ──────────────────────────────────┤
│  FastAPI · Python 3.12 · Pydantic          │
│  SQLAlchemy (async) · Alembic              │
│  LangGraph · LangChain · OpenAI SDK        │
├─ Data ─────────────────────────────────────┤
│  PostgreSQL 16 + pgvector                  │
│  Redis                                     │
│  S3 / MinIO                                │
├─ AI/ML ────────────────────────────────────┤
│  GPT-4o / GPT-4o-mini (OpenAI)             │
│  Claude 3.5 Sonnet (fallback)              │
│  text-embedding-3-small (embeddings)       │
│  Tesseract + Cloud Vision (OCR)            │
├─ Infra ────────────────────────────────────┤
│  Docker · Docker Compose                   │
│  Railway / Fly.io (MVP)                    │
│  Kubernetes (producción)                   │
│  GitHub Actions (CI/CD)                    │
├─ Monitoring ───────────────────────────────┤
│  LangSmith / LangFuse                      │
│  Sentry (errors)                           │
│  Prometheus + Grafana (métricas)           │
└────────────────────────────────────────────┘
```
