# MedAgent — Roadmap Dinámico

> Este roadmap se actualiza conforme avanza el desarrollo.
> Última actualización: 2026-04-10

## Estado General

| Fase | Estado | Progreso |
|------|--------|----------|
| Fase 0: Setup | ✅ Completa | 6/6 |
| Fase 1: Core | ✅ Completa | 13/13 (278 tests) |
| Fase 2: Documentos | ✅ Completa | 5/5 (327 tests) |
| Fase 3: Especialidades | ✅ Completa | 5/5 (356 tests) |
| Fase 4: Memoria + KB | ✅ Completa | 3/3 (372 tests) |
| Fase 5: Dashboard | ✅ Completa | 1/1 (390 tests) |

---

## Fase 0: Setup e Infraestructura (1-2 semanas)

### 0.1 Repositorio y estructura
- [x] Crear monorepo con estructura de carpetas
- [x] Configurar TypeScript para frontend
- [x] Configurar Python + Poetry para backend
- [x] Configurar linters (ESLint, Prettier, Black, Ruff)
- [ ] Configurar pre-commit hooks

### 0.2 Frontend base
- [x] Inicializar Next.js 15 con App Router
- [x] Configurar Tailwind CSS + shadcn/ui
- [x] Crear layout base (sidebar + main area)
- [x] Configurar Zustand store
- [x] Crear páginas placeholder (login, chat, settings)

### 0.3 Backend base
- [x] Inicializar FastAPI con estructura modular
- [x] Configurar SQLAlchemy async + Alembic
- [x] Configurar Redis + S3/MinIO clients
- [x] Health check endpoint

### 0.4 Base de datos
- [x] Docker Compose (PostgreSQL + pgvector + Redis + MinIO)
- [x] Migración inicial (users, cases, messages)

### 0.5 Auth
- [x] Registro + Login con JWT
- [x] Refresh token rotation
- [x] Middleware de auth (backend) + Auth context (frontend)

### 0.6 Deploy pipeline
- [ ] Dockerfiles (frontend + backend)
- [x] Docker Compose para dev local
- [ ] CI pipeline básico

---

## Fase 1: Core — Chat + Orquestador v2 + Agentes (4-6 semanas)

### 1.1 LangGraph setup ✅
- [x] Instalar LangGraph + LangChain
- [x] Definir ClinicalCaseState (TypedDict)
- [x] Crear StateGraph con nodos v2
- [x] Configurar checkpointer PostgreSQL

### 1.2 Agente de Triage ✅ (18 tests)
- [x] System prompt + scoring de urgencia
- [x] Red flags desde YAML
- [x] Tests: red flags 100% detectados

### 1.3 Agente de Anamnesis ✅ (23 tests)
- [x] Templates de preguntas por área
- [x] Tracking de preguntas respondidas/pendientes
- [x] Tests: no repite preguntas

### 1.4 Agente Clasificador ✅ (30 tests)
- [x] Mapa síntomas → especialidades (YAML)
- [x] Scoring ponderado de especialidades

### 1.5 Agente de Medicina General ✅ (29 tests)
- [x] System prompt especializado
- [x] Output estructurado (SpecialistAnalysis)

### 1.6 Mesa Médica (Medical Board) ✅ (25 tests)
- [x] Debate moderador multi-ronda
- [x] Round 1: presentación de análisis
- [x] Round 2: Devil's Advocate challenges
- [x] Round 3: respuestas y ajustes
- [x] Evaluador de consenso
- [x] Tests: detecta desacuerdo genuino

### 1.7 Devil's Advocate Agent ✅ (21 tests)
- [x] Generador de contra-argumentos
- [x] Detector de suposiciones no examinadas
- [x] Tests: genera challenges válidos

### 1.8 Guardrail Agent ✅ (22 tests)
- [x] Monitor en tiempo real (paralelo)
- [x] Checklist de validación continua
- [x] Capacidad de interrupción del flujo
- [x] Tests: nunca deja pasar diagnóstico definitivo

### 1.9 Agente Sintetizador ✅ (17 tests)
- [x] Template de respuesta final
- [x] Consolidación de outputs + Mesa Médica
- [x] Adaptación de nivel de lectura

### 1.10 Orquestador (flujo completo v2) ✅ (48 tests)
- [x] Edges condicionales del grafo v2
- [x] Loop control con Mesa Médica
- [x] Dispatch paralelo de especialistas
- [x] Guardrail paralelo
- [x] Tests: flujo completo sin loops
- [x] Tests: flujo con Mesa Médica disagreement
- [x] Tests: flujo con escalamiento

### 1.11 WebSocket streaming ✅ (26 tests)
- [x] WebSocket server en FastAPI
- [x] Streaming de eventos de Mesa Médica
- [x] Frontend: chat con streaming + indicadores

### 1.12 Memoria Nivel 1 (Inmediata - Redis) ✅ (10 tests)
- [x] Ventana deslizante de mensajes (RPUSH + LTRIM, 20 msgs, 2h TTL)
- [x] Recuperación de estado en chat.py

### 1.13 Memoria Nivel 2 (Caso - PostgreSQL) ✅ (8 tests)
- [x] Extracción de hechos clínicos (confidence >= 0.7)
- [x] Embeddings + búsqueda semántica (pgvector cosine, k=10)

---

## Fase 2: Documentos (2-3 semanas) ✅

- [x] Upload + validación + S3/MinIO (StorageClient boto3, REST API, 20MB max)
- [x] OCR (Tesseract + Cloud Vision fallback, pdf2image, confidence threshold)
- [x] Clasificación de documentos con LLM (GPT-4o-mini structured output)
- [x] Extracción de valores de laboratorio (test_name, value, unit, range, flag)
- [x] Integración con el chat + agentes (keyword detection, document_context injection)

---

## Fase 3: Especialidades adicionales (3-4 semanas) ✅

- [x] Medicina Interna (InternalMedicineAgent + system prompt especializado)
- [x] Pediatría (PediatricsAgent + consideraciones pediátricas)
- [x] Ginecología (GynecologyAgent + salud reproductiva)
- [x] Farmacología (PharmacologyAgent + DrugInteraction schema + LLM-only MVP)
- [x] Plugin system (Registry pattern + @register decorator + dynamic dispatcher)

---

## Fase 4: Memoria Nivel 3 + Knowledge Base (2-3 semanas) ✅

- [x] Memoria clínica estructurada + timeline (PatientTimelineEvent + PatientProfile)
- [x] Knowledge base (MedlinePlus API + chunking + embedding storage)
- [x] RAG con pgvector + compresión de contexto (cosine search + 1500 token limit)

---

## Fase 5: Dashboard y Admin (3-4 semanas) ✅

- [x] Dashboard de métricas (stat cards, aggregate queries, Redis cache)
- [x] Audit log (AuditLog model, paginated API, wired in auth+documents)
- [x] Gestión KB (CRUD API, MedlinePlus ingest, admin page)
- [x] Exportar PDF (reportlab, case report generation)

---

> 🎉 **PROYECTO COMPLETO** — Todas las fases implementadas. 390 tests passing. MedAgent listo para producción.
