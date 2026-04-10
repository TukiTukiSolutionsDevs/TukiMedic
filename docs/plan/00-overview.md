# MedAgent — Visión General del Proyecto

## Nombre del Proyecto
**MedAgent** — Plataforma Conversacional Clínica Orquestada

## Versión del Documento
v1.0 — Abril 2026

---

## 1. Qué es MedAgent

MedAgent es una plataforma conversacional médica basada en una arquitectura multiagente deliberativa. No es un chatbot médico. Es un **sistema de análisis clínico coordinado** que simula el comportamiento de una mesa médica multidisciplinaria.

Cuando un paciente presenta una consulta, el sistema no responde con una lógica lineal ni con una sola especialidad. En su lugar:

1. Analiza el motivo de consulta
2. Detecta síntomas, antecedentes y señales relevantes
3. Identifica una o varias especialidades implicadas
4. Activa agentes especializados de forma coordinada
5. Compara sus aportes y detecta contradicciones
6. Solicita aclaraciones si falta contexto
7. Arma una salida unificada, priorizada y coherente
8. Valida seguridad clínica antes de entregar la respuesta

## 2. Qué problema resuelve

### Problemas de los chatbots médicos actuales:
- Responden con una sola lógica (genérica)
- No conservan contexto entre turnos
- No coordinan especialidades
- No detectan contradicciones
- No profundizan cuando hay ambigüedad
- No escalan cuando deberían

### Lo que MedAgent propone:
- **Continuidad clínica real**: el sistema recuerda todo el caso
- **Multi-especialidad coordinada**: un caso activa múltiples agentes
- **Loops deliberativos**: el sistema re-evalúa antes de responder
- **Integración documental**: acepta labs, recetas, informes
- **Escalamiento inteligente**: sabe cuándo decir "andá al médico"

## 3. Qué NO es MedAgent

- **No es un sistema de diagnóstico**. No reemplaza al médico.
- **No es un sistema de prescripción**. No receta medicamentos.
- **No es un sistema de emergencias**. Detecta urgencias y escala.
- **No es una historia clínica electrónica (HCE)**. No almacena datos médicos oficiales.

MedAgent es un **sistema de apoyo, orientación, preanálisis y coordinación clínica conversacional**.

## 4. Público objetivo

### MVP (Fase 1):
- Pacientes que buscan orientación médica inicial
- Personas que quieren entender síntomas antes de ir al médico
- Usuarios que necesitan interpretar resultados de laboratorio

### Futuro (Fase 2+):
- Profesionales de salud que necesitan un co-piloto clínico
- Clínicas que quieren un triage conversacional previo a la consulta
- Sistemas de salud que buscan descongestionar atención primaria

## 5. Diferencial competitivo

| Característica | Chatbot médico típico | MedAgent |
|---|---|---|
| Lógica de respuesta | Lineal, una pasada | Deliberativa, multi-loop |
| Especialidades | Una por consulta | Múltiples coordinadas |
| Contradicciones | No las detecta | Agente revisor dedicado |
| Memoria | Ninguna o muy básica | 3 niveles de memoria clínica |
| Documentos | No acepta o no procesa | Pipeline completo de ingestión |
| Seguridad | Disclaimer genérico | Validación activa + escalamiento |
| Transparencia | Caja negra | Muestra qué agentes participaron |

## 6. Principios de diseño

1. **Safety First** — Toda decisión de diseño prioriza seguridad clínica
2. **No diagnosticar** — Orientar, sugerir, priorizar. Nunca diagnosticar.
3. **Transparencia** — El paciente sabe qué áreas analizaron su caso
4. **Humildad epistémica** — El sistema dice "no sé" cuando no sabe
5. **Escalamiento proactivo** — Mejor escalar de más que de menos
6. **Memoria real** — El paciente nunca debe repetir información
7. **Modular** — Cada especialidad es un módulo independiente
8. **Incremental** — El MVP es pequeño pero la arquitectura soporta todo

## 7. Estructura del Plan

Este plan está compuesto por los siguientes documentos:

| # | Documento | Contenido |
|---|-----------|-----------|
| 00 | Overview (este) | Visión general, problema, diferencial |
| 01 | Architecture | Arquitectura del sistema completa |
| 02 | Agents | Especificación detallada de cada agente |
| 03 | Orchestration Flow | Flujo de orquestación, loops, state machine |
| 04 | Memory System | Sistema de memoria de 3 niveles |
| 05 | Knowledge Base | Base de conocimiento médico y estrategia RAG |
| 06 | Document Processing | Pipeline de procesamiento de documentos |
| 07 | Safety & Compliance | Seguridad clínica, legal, disclaimers |
| 08 | Database Schema | Schemas de PostgreSQL completos |
| 09 | API Contracts | Endpoints REST, WebSocket events |
| 10 | Frontend Design | UI/UX del chat, upload, historial |
| 11 | Implementation Phases | Fases detalladas con tareas |
| 12 | Tech Stack | Stack tecnológico con reasoning |
| 13 | Deployment | Infraestructura, CI/CD, monitoring |
| 14 | Data Sources | Fuentes de datos médicos, scraping, ingesta |

## 8. Métricas de éxito del MVP

- **Triage accuracy**: >90% de clasificación correcta de urgencia vs evaluación manual
- **Coherencia multi-agente**: <5% de respuestas con contradicciones no resueltas
- **Completitud de anamnesis**: el sistema captura >80% de datos relevantes del caso
- **Escalamiento correcto**: 100% de red flags detectadas correctamente (no se puede fallar acá)
- **Satisfacción de usuario**: >4/5 en claridad y utilidad de respuesta
- **Latencia percibida**: respuesta sintetizada en <15 segundos (con streaming)
