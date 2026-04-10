# MedAgent — Roadmap Dinámico

> Este roadmap se actualiza conforme avanza el desarrollo.
> Última actualización: 2026-04-09

## Estado General

| Fase | Estado | Progreso |
|------|--------|----------|
| Fase 0: Setup | ✅ Completa | 6/6 |
| Fase 1: Core | ⚪ Pendiente | 0/13 |
| Fase 2: Documentos | ⚪ Pendiente | 0/5 |
| Fase 3: Especialidades | ⚪ Pendiente | 0/5 |
| Fase 4: Memoria + KB | ⚪ Pendiente | 0/3 |
| Fase 5: Dashboard | ⚪ Pendiente | 0/1 |

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

### 1.1 LangGraph setup
- [ ] Instalar LangGraph + LangChain
- [ ] Definir ClinicalCaseState (TypedDict)
- [ ] Crear StateGraph con nodos v2
- [ ] Configurar checkpointer PostgreSQL

### 1.2 Agente de Triage
- [ ] System prompt + scoring de urgencia
- [ ] Red flags desde YAML
- [ ] Tests: red flags 100% detectados

### 1.3 Agente de Anamnesis
- [ ] Templates de preguntas por área
- [ ] Tracking de preguntas respondidas/pendientes
- [ ] Tests: no repite preguntas

### 1.4 Agente Clasificador
- [ ] Mapa síntomas → especialidades (YAML)
- [ ] Scoring ponderado de especialidades

### 1.5 Agente de Medicina General
- [ ] System prompt especializado
- [ ] Output estructurado (SpecialistAnalysis)

### 1.6 Mesa Médica (Medical Board) — NUEVO v2
- [ ] Debate moderador multi-ronda
- [ ] Round 1: presentación de análisis
- [ ] Round 2: Devil's Advocate challenges
- [ ] Round 3: respuestas y ajustes
- [ ] Evaluador de consenso
- [ ] Tests: detecta desacuerdo genuino

### 1.7 Devil's Advocate Agent — NUEVO v2
- [ ] Generador de contra-argumentos
- [ ] Detector de suposiciones no examinadas
- [ ] Tests: genera challenges válidos

### 1.8 Guardrail Agent — NUEVO v2 (reemplaza Safety Validator)
- [ ] Monitor en tiempo real (paralelo)
- [ ] Checklist de validación continua
- [ ] Capacidad de interrupción del flujo
- [ ] Tests: nunca deja pasar diagnóstico definitivo

### 1.9 Agente Sintetizador
- [ ] Template de respuesta final
- [ ] Consolidación de outputs + Mesa Médica
- [ ] Adaptación de nivel de lectura

### 1.10 Orquestador (flujo completo v2)
- [ ] Edges condicionales del grafo v2
- [ ] Loop control con Mesa Médica
- [ ] Dispatch paralelo de especialistas
- [ ] Guardrail paralelo
- [ ] Tests: flujo completo sin loops
- [ ] Tests: flujo con Mesa Médica disagreement
- [ ] Tests: flujo con escalamiento

### 1.11 WebSocket streaming
- [ ] WebSocket server en FastAPI
- [ ] Streaming de eventos de Mesa Médica
- [ ] Frontend: chat con streaming + indicadores

### 1.12 Memoria Nivel 1 (Inmediata - Redis)
- [ ] Ventana deslizante de mensajes
- [ ] Recuperación de estado

### 1.13 Memoria Nivel 2 (Caso - PostgreSQL)
- [ ] Extracción de hechos clínicos
- [ ] Embeddings + búsqueda semántica

---

## Fase 2: Documentos (2-3 semanas)

- [ ] Upload + validación + S3/MinIO
- [ ] OCR (Tesseract + Cloud Vision fallback)
- [ ] Clasificación de documentos con LLM
- [ ] Extracción de valores de laboratorio
- [ ] Integración con el chat + agentes

---

## Fase 3: Especialidades adicionales (3-4 semanas)

- [ ] Medicina Interna
- [ ] Pediatría
- [ ] Ginecología
- [ ] Farmacología (interacciones)
- [ ] Plugin system para agregar especialidades

---

## Fase 4: Memoria Nivel 3 + Knowledge Base (2-3 semanas)

- [ ] Memoria clínica estructurada + timeline
- [ ] Knowledge base (scraping MedlinePlus, VADEMECUM)
- [ ] RAG con pgvector + compresión de contexto

---

## Fase 5: Dashboard y Admin (3-4 semanas)

- [ ] Dashboard de métricas, audit log, gestión KB, exportar PDF

---

> 🏗️ **Próximo paso**: Fase 0.1 — Crear estructura del monorepo
