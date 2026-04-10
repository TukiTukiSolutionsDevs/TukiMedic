# 11 — Fases de Implementación Detalladas

## Visión general de fases

```
Fase 0 ──▶ Fase 1 ──▶ Fase 2 ──▶ Fase 3 ──▶ Fase 4 ──▶ Fase 5
Setup     Core Chat   Documents  Specialties Memory L3   Dashboard
1-2 sem   4-6 sem    2-3 sem    3-4 sem     2-3 sem     3-4 sem
```

---

## Fase 0: Setup e infraestructura (1-2 semanas)

### Objetivo
Tener el proyecto configurado, la infra base levantada, y poder hacer deploy de una app vacía.

### Tareas

#### 0.1 Repositorio y estructura
- [ ] Crear monorepo con estructura de carpetas
- [ ] Configurar TypeScript para frontend
- [ ] Configurar Python + Poetry para backend
- [ ] Configurar ESLint, Prettier, Black, Ruff
- [ ] Configurar pre-commit hooks
- [ ] Crear README con instrucciones de setup

#### 0.2 Frontend base
- [ ] Inicializar Next.js 15 con App Router
- [ ] Configurar Tailwind CSS
- [ ] Instalar y configurar shadcn/ui
- [ ] Crear layout base (sidebar + main area)
- [ ] Configurar Zustand store
- [ ] Crear páginas placeholder (login, chat, settings)

#### 0.3 Backend base
- [ ] Inicializar FastAPI con estructura modular
- [ ] Configurar SQLAlchemy async + Alembic
- [ ] Configurar Redis client
- [ ] Configurar S3/MinIO client
- [ ] Crear modelos Pydantic base
- [ ] Health check endpoint

#### 0.4 Base de datos
- [ ] Docker compose con PostgreSQL + pgvector
- [ ] Docker compose con Redis
- [ ] Docker compose con MinIO
- [ ] Crear migración inicial (users, cases, messages)
- [ ] Seed data para desarrollo

#### 0.5 Auth
- [ ] Implementar registro de usuario
- [ ] Implementar login con JWT
- [ ] Implementar refresh token
- [ ] Middleware de autenticación en FastAPI
- [ ] Auth context en frontend

#### 0.6 Deploy pipeline
- [ ] Dockerfile para frontend
- [ ] Dockerfile para backend
- [ ] Docker Compose para dev local
- [ ] CI pipeline básico (lint + type check)

### Entregable
App desplegable que tiene login, una pantalla vacía de chat, y un backend que responde health check.

---

## Fase 1: Core — Chat + Orquestador + Agentes base (4-6 semanas)

### Objetivo
El flujo completo de una consulta médica funciona end-to-end: usuario escribe → sistema analiza → respuesta sintetizada.

### Tareas

#### 1.1 LangGraph setup
- [ ] Instalar LangGraph + LangChain
- [ ] Definir ClinicalCaseState (TypedDict)
- [ ] Crear StateGraph base con nodos placeholder
- [ ] Configurar checkpointer con PostgreSQL
- [ ] Test: grafo ejecuta de inicio a fin con estado mock

#### 1.2 Agente de Triage
- [ ] Crear system prompt para triage
- [ ] Implementar lógica de scoring de urgencia
- [ ] Cargar red flags desde YAML
- [ ] Implementar detector de red flags
- [ ] Test: red flags detectados correctamente (100%)
- [ ] Test: clasificación verde/amarillo/rojo

#### 1.3 Agente de Anamnesis
- [ ] Crear templates de preguntas por área clínica
- [ ] Implementar lógica de preguntas prioritarias
- [ ] Implementar tracking de preguntas respondidas/pendientes
- [ ] Test: genera preguntas relevantes
- [ ] Test: no repite preguntas ya respondidas

#### 1.4 Agente Clasificador
- [ ] Crear mapa de síntomas → especialidades (YAML)
- [ ] Implementar scoring de especialidades
- [ ] Test: clasificación correcta para 10 escenarios típicos

#### 1.5 Agente de Medicina General
- [ ] Crear system prompt especializado
- [ ] Implementar output estructurado (SpecialistAnalysis)
- [ ] Test: genera análisis coherente para casos comunes

#### 1.6 Agente Revisor de Contradicciones
- [ ] Implementar comparador de outputs
- [ ] Implementar detector de vacíos
- [ ] Implementar lógica de "necesita más info"
- [ ] Test: detecta contradicción entre dos agentes

#### 1.7 Agente Sintetizador
- [ ] Crear template de respuesta final
- [ ] Implementar consolidación de outputs
- [ ] Implementar adaptación de nivel de lectura
- [ ] Test: respuesta coherente, priorizada, con disclaimer

#### 1.8 Agente de Seguridad
- [ ] Implementar checklist de validación
- [ ] Implementar modificación de respuesta si no pasa
- [ ] Implementar trigger de escalamiento
- [ ] Test: nunca deja pasar respuesta que diagnostica
- [ ] Test: siempre incluye disclaimer

#### 1.9 Orquestador (flujo completo)
- [ ] Implementar edges condicionales del grafo
- [ ] Implementar loop control (max_loops)
- [ ] Implementar dispatch paralelo de especialistas
- [ ] Test: flujo completo sin loops
- [ ] Test: flujo con 1 loop (info faltante)
- [ ] Test: flujo con escalamiento (red flag)
- [ ] Test: flujo con max_loops alcanzado

#### 1.10 WebSocket streaming
- [ ] Implementar WebSocket server en FastAPI
- [ ] Implementar streaming de eventos de progreso
- [ ] Implementar streaming de tokens de respuesta
- [ ] Frontend: componente de chat con streaming
- [ ] Frontend: indicador de agentes activos
- [ ] Test: conexión WebSocket estable

#### 1.11 Memoria Nivel 1 (Inmediata)
- [ ] Implementar almacenamiento en Redis
- [ ] Implementar ventana deslizante de mensajes
- [ ] Implementar recuperación de estado
- [ ] Test: contexto se mantiene en la conversación

#### 1.12 Memoria Nivel 2 (Caso)
- [ ] Implementar extracción de hechos clínicos
- [ ] Implementar almacenamiento en PostgreSQL
- [ ] Implementar embeddings de hechos
- [ ] Implementar búsqueda semántica de hechos
- [ ] Test: hechos se extraen correctamente
- [ ] Test: hechos se recuperan por relevancia

#### 1.13 Frontend del chat
- [ ] Componente de mensaje (user/assistant/system)
- [ ] Componente de input con envío
- [ ] Componente de indicador de progreso
- [ ] Componente de preguntas de seguimiento (botones)
- [ ] Componente de alerta de escalamiento
- [ ] Sidebar con lista de casos
- [ ] Crear/seleccionar caso
- [ ] Panel de contexto del caso

### Entregable
Una consulta médica completa funciona: el usuario describe síntomas, el sistema hace triage, pregunta si falta info, consulta especialidades, revisa coherencia, sintetiza y responde con streaming.

---

## Fase 2: Documentos — Upload + OCR + Extracción (2-3 semanas)

### Tareas

#### 2.1 Upload de archivos
- [ ] Endpoint de upload con validación
- [ ] Almacenamiento en S3/MinIO
- [ ] Frontend: drag & drop + selector de archivos
- [ ] Frontend: preview de archivo subido
- [ ] Frontend: indicador de procesamiento

#### 2.2 OCR
- [ ] Integrar Tesseract (local)
- [ ] Integrar Google Cloud Vision (fallback)
- [ ] Preprocessamiento de imágenes
- [ ] Test: OCR funciona con foto de lab típico

#### 2.3 Clasificación de documentos
- [ ] Implementar clasificador con LLM
- [ ] Test: clasifica correctamente lab, receta, informe

#### 2.4 Extracción de datos
- [ ] Extractor de valores de laboratorio
- [ ] Extractor de medicamentos de recetas
- [ ] Cargar valores de referencia (YAML)
- [ ] Comparación automática contra rangos normales
- [ ] Test: extrae valores de hemograma correctamente

#### 2.5 Integración con el chat
- [ ] Documentos disponibles para agentes en el grafo
- [ ] Agente de laboratorio (simplificado)
- [ ] Creación automática de hechos clínicos desde docs
- [ ] Frontend: visualización de datos extraídos

### Entregable
El usuario puede subir un PDF de laboratorio, el sistema lo procesa, extrae valores, los compara contra rangos normales, y los incorpora al análisis del caso.

---

## Fase 3: Especialidades adicionales (3-4 semanas)

### Tareas

#### 3.1 Medicina Interna
- [ ] System prompt especializado
- [ ] Knowledge scope definido
- [ ] Tests con escenarios de complejidad sistémica

#### 3.2 Pediatría
- [ ] System prompt con enfoque pediátrico
- [ ] Rangos de referencia ajustados por edad
- [ ] Red flags pediátricos específicos

#### 3.3 Ginecología
- [ ] System prompt especializado
- [ ] Integración de contexto de embarazo
- [ ] Red flags obstétricos

#### 3.4 Farmacología
- [ ] Verificación de interacciones medicamentosas
- [ ] Integración con datos de OpenFDA/VADEMECUM
- [ ] Alertas de contraindicaciones

#### 3.5 Plugin system
- [ ] Interfaz base para agregar especialidades
- [ ] Registro dinámico de triggers
- [ ] Documentación para agregar nuevas especialidades

### Entregable
4 nuevas especialidades funcionando como agentes en el grafo, activándose automáticamente cuando el caso lo requiere.

---

## Fase 4: Memoria Nivel 3 + Knowledge Base (2-3 semanas)

### Tareas

#### 4.1 Memoria clínica estructurada
- [ ] Implementar generación de resumen clínico
- [ ] Implementar timeline del caso
- [ ] Implementar actualización evolutiva
- [ ] Frontend: vista de resumen clínico

#### 4.2 Knowledge base (scraping)
- [ ] Scraper de MedlinePlus (condiciones en español)
- [ ] Scraper de VADEMECUM (medicamentos)
- [ ] Pipeline de chunking + embedding
- [ ] Indexación en pgvector
- [ ] Integración RAG con agentes

#### 4.3 Compresión de contexto
- [ ] Implementar ventana de contexto priorizada
- [ ] Test: contexto se mantiene en conversaciones largas

### Entregable
El sistema tiene una base de conocimiento médico indexada, la memoria se mantiene y evoluciona a lo largo del caso, y hay un resumen clínico visual.

---

## Fase 5: Dashboard y administración (3-4 semanas)

### Tareas
- [ ] Dashboard de métricas (# casos, triage distribution, etc.)
- [ ] Admin: ver audit log
- [ ] Admin: gestionar knowledge base
- [ ] Admin: monitorear scrapers
- [ ] Exportar caso como PDF
- [ ] Configuración avanzada del usuario
- [ ] Onboarding flow para nuevos usuarios

### Entregable
Panel de administración funcional con métricas y gestión de la base de conocimiento.

---

## Timeline total estimada

| Fase | Semanas | Acumulado |
|------|---------|-----------|
| Fase 0: Setup | 1-2 | 1-2 |
| Fase 1: Core | 4-6 | 5-8 |
| Fase 2: Documents | 2-3 | 7-11 |
| Fase 3: Specialties | 3-4 | 10-15 |
| Fase 4: Memory + KB | 2-3 | 12-18 |
| Fase 5: Dashboard | 3-4 | 15-22 |

**Estimación total: 15-22 semanas (4-5 meses) para el producto completo.**
**MVP funcional (Fases 0-1): 5-8 semanas (1-2 meses).**
