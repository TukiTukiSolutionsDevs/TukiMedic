# 04 — Sistema de Memoria de 3 Niveles

## 1. Por qué la memoria es crítica en contexto médico

En un chatbot normal, perder contexto es molesto. En medicina, perder contexto puede ser **peligroso**:

- El paciente reporta un síntoma en el turno 1 y el sistema lo olvida en el turno 5
- Se ignoran antecedentes mencionados anteriormente
- Se repiten preguntas ya respondidas
- Se pierden resultados de laboratorio ya cargados
- No se detectan patrones evolutivos del caso

MedAgent implementa un sistema de memoria de **3 niveles** que garantiza continuidad clínica real.

## 2. Arquitectura de memoria

```
┌─────────────────────────────────────────────────────────────┐
│                  NIVEL 1: MEMORIA INMEDIATA                  │
│                                                              │
│  Almacén: Redis (TTL de sesión)                             │
│  Contenido: Mensajes recientes, estado actual del grafo      │
│  Duración: Mientras dure la sesión activa                    │
│  Acceso: < 1ms                                               │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                  NIVEL 2: MEMORIA DE CASO                    │
│                                                              │
│  Almacén: PostgreSQL (structured) + pgvector (semantic)      │
│  Contenido: Hechos clínicos, documentos, especialidades,     │
│             preguntas respondidas, resúmenes parciales        │
│  Duración: Persistente por caso                              │
│  Acceso: < 50ms                                              │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                  NIVEL 3: MEMORIA CLÍNICA ESTRUCTURADA       │
│                                                              │
│  Almacén: PostgreSQL (JSONB) + pgvector                      │
│  Contenido: Antecedentes, condiciones, alertas, timeline,    │
│             evolución del caso, resumen clínico consolidado   │
│  Duración: Permanente                                        │
│  Acceso: < 100ms                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 3. Nivel 1 — Memoria Inmediata

### Qué almacena
- Los últimos N mensajes de la conversación actual (ventana deslizante)
- El estado actual del ClinicalCaseState
- Tokens de sesión y metadata temporal

### Implementación (Redis)

```python
class ImmediateMemory:
    """Memoria de corto plazo para la sesión activa"""
    
    def __init__(self, redis_client: Redis, session_ttl: int = 3600):
        self.redis = redis_client
        self.ttl = session_ttl  # 1 hora de inactividad
    
    async def store_message(self, case_id: str, message: Message):
        key = f"memory:immediate:{case_id}:messages"
        await self.redis.rpush(key, message.model_dump_json())
        await self.redis.expire(key, self.ttl)
    
    async def get_recent_messages(self, case_id: str, limit: int = 20) -> list[Message]:
        key = f"memory:immediate:{case_id}:messages"
        raw = await self.redis.lrange(key, -limit, -1)
        return [Message.model_validate_json(m) for m in raw]
    
    async def store_state(self, case_id: str, state: ClinicalCaseState):
        key = f"memory:immediate:{case_id}:state"
        await self.redis.set(key, json.dumps(state), ex=self.ttl)
    
    async def get_state(self, case_id: str) -> Optional[ClinicalCaseState]:
        key = f"memory:immediate:{case_id}:state"
        raw = await self.redis.get(key)
        return json.loads(raw) if raw else None
```

### Ventana deslizante
Para mantener costos bajo control, la memoria inmediata usa una ventana de los últimos **20 mensajes**. Si la conversación es más larga, los mensajes más viejos se "promueven" al Nivel 2 como hechos clínicos extraídos.

## 4. Nivel 2 — Memoria de Caso

### Qué almacena
Son los **datos clínicos estructurados** del caso específico:

```python
class CaseMemory:
    case_id: str
    patient_id: str
    created_at: datetime
    last_updated: datetime
    
    # Hechos clínicos extraídos
    clinical_facts: list[ClinicalFact]
    
    # Documentos asociados
    documents: list[DocumentReference]
    
    # Especialidades que ya intervinieron
    specialties_involved: list[SpecialtyInvolvement]
    
    # Preguntas de anamnesis
    questions_asked: list[QuestionRecord]
    questions_pending: list[QuestionRecord]
    
    # Hipótesis activas
    active_hypotheses: list[DiagnosisHypothesis]
    
    # Resúmenes parciales
    partial_summaries: list[PartialSummary]
    
    # Signos de alarma detectados
    alarm_signs: list[AlarmSign]
    
    # Medicación mencionada
    medications: list[MedicationMention]
```

### Hechos clínicos (ClinicalFact)

Cada interacción se procesa para extraer hechos clínicos:

```python
class ClinicalFact:
    id: str
    fact_type: Literal[
        "symptom",        # "dolor de cabeza desde hace 3 días"
        "antecedent",     # "tengo diabetes tipo 2"
        "medication",     # "tomo metformina 850mg"
        "allergy",        # "soy alérgico a la penicilina"
        "vital_sign",     # "mi presión es 140/90"
        "lab_result",     # "glucosa en 200 mg/dl"
        "procedure",      # "me operaron de apendicitis en 2020"
        "family_history", # "mi padre tuvo infarto a los 50"
        "lifestyle",      # "fumo 1 paquete diario hace 10 años"
        "context",        # "estoy embarazada de 3 meses"
    ]
    value: str                    # El hecho en texto
    source: str                   # "user_message" | "document" | "inferred"
    source_turn: int              # En qué turno se mencionó
    confidence: float             # Confianza de la extracción
    clinical_relevance: float     # Relevancia clínica (0-1)
    embedding: list[float]        # Vector embedding para búsqueda semántica
    created_at: datetime
```

### Extracción automática de hechos

Después de cada mensaje del usuario, un proceso extrae hechos clínicos:

```python
async def extract_clinical_facts(message: str, existing_facts: list[ClinicalFact]) -> list[ClinicalFact]:
    """
    Usa el LLM para extraer hechos clínicos del mensaje.
    Evita duplicados comparando con hechos existentes.
    """
    prompt = f"""
    Mensaje del paciente: {message}
    
    Hechos ya conocidos: {[f.value for f in existing_facts]}
    
    Extrae SOLO hechos clínicos NUEVOS del mensaje.
    Clasifica cada uno por tipo y relevancia.
    No repitas hechos ya conocidos.
    """
    # ... LLM call + parsing
```

### Implementación (PostgreSQL + pgvector)

```sql
CREATE TABLE case_clinical_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id),
    fact_type VARCHAR(50) NOT NULL,
    value TEXT NOT NULL,
    source VARCHAR(50) NOT NULL,
    source_turn INTEGER,
    confidence FLOAT DEFAULT 1.0,
    clinical_relevance FLOAT DEFAULT 0.5,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT fk_case FOREIGN KEY (case_id) REFERENCES cases(id)
);

CREATE INDEX idx_facts_case_id ON case_clinical_facts(case_id);
CREATE INDEX idx_facts_type ON case_clinical_facts(fact_type);
CREATE INDEX idx_facts_embedding ON case_clinical_facts 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### Búsqueda semántica de hechos

Cuando un agente necesita contexto relevante:

```python
async def retrieve_relevant_facts(
    case_id: str, 
    query: str, 
    limit: int = 10,
    fact_types: list[str] = None
) -> list[ClinicalFact]:
    """Busca hechos clínicos relevantes por similitud semántica"""
    query_embedding = await embed(query)
    
    sql = """
        SELECT *, 1 - (embedding <=> $1) AS similarity
        FROM case_clinical_facts
        WHERE case_id = $2
        AND ($3::text[] IS NULL OR fact_type = ANY($3))
        ORDER BY similarity DESC
        LIMIT $4
    """
    return await db.fetch(sql, query_embedding, case_id, fact_types, limit)
```

## 5. Nivel 3 — Memoria Clínica Estructurada

### Qué almacena
Es la **visión consolidada** del caso. No son mensajes ni hechos aislados, sino un **resumen clínico evolutivo**.

```python
class StructuredClinicalMemory:
    case_id: str
    patient_id: str
    
    # Resumen clínico consolidado (se actualiza con cada interacción)
    clinical_summary: ClinicalSummary
    
    # Timeline del caso
    timeline: list[TimelineEvent]
    
    # Antecedentes consolidados
    medical_history: MedicalHistory
    
    # Estado actual del caso
    case_status: CaseStatus
    
    # Evolución
    evolution_notes: list[EvolutionNote]
```

### ClinicalSummary (se regenera periódicamente)

```python
class ClinicalSummary:
    """Resumen clínico que se regenera cada N interacciones"""
    
    chief_complaint: str              # Motivo de consulta principal
    history_of_present_illness: str   # Relato de la enfermedad actual
    
    active_problems: list[str]        # Problemas activos del caso
    resolved_problems: list[str]      # Problemas resueltos
    
    current_medications: list[Medication]
    known_allergies: list[str]
    
    relevant_history: str             # Antecedentes relevantes consolidados
    family_history: str               # Antecedentes familiares
    social_history: str               # Hábitos, ocupación, etc.
    
    active_hypotheses: list[str]      # Diagnósticos diferenciales activos
    pending_studies: list[str]        # Estudios sugeridos pendientes
    
    alarm_signs_active: list[str]     # Signos de alarma vigentes
    attention_level: str              # Nivel de atención recomendado
    
    last_updated: datetime
    version: int                      # Cada actualización incrementa versión
```

### Timeline del caso

```python
class TimelineEvent:
    timestamp: datetime
    event_type: str      # "symptom_reported", "document_uploaded", 
                         # "specialty_consulted", "alarm_detected",
                         # "question_answered", "summary_updated"
    description: str
    metadata: dict       # Datos adicionales del evento
```

### Regeneración del resumen

El resumen clínico NO se guarda crudo. Se **regenera** periódicamente:

```python
async def update_clinical_summary(case_id: str):
    """
    Se ejecuta después de cada ciclo completo de deliberación.
    Toma todos los hechos clínicos y genera un resumen actualizado.
    """
    facts = await get_all_facts(case_id)
    previous_summary = await get_current_summary(case_id)
    timeline = await get_timeline(case_id)
    
    new_summary = await llm.generate(
        system="Eres un médico que actualiza un resumen clínico...",
        prompt=f"""
        Hechos clínicos del caso: {facts}
        Resumen anterior: {previous_summary}
        Timeline: {timeline}
        
        Genera un resumen clínico actualizado que incorpore toda la nueva información.
        Mantén la estructura estándar (motivo de consulta, enfermedad actual, etc.)
        """
    )
    
    await save_summary(case_id, new_summary, version=previous_summary.version + 1)
```

## 6. Flujo de memoria durante una interacción

```
Usuario envía mensaje
    │
    ▼
1. Se guarda en Nivel 1 (Redis - inmediato)
    │
    ▼
2. Se extraen hechos clínicos del mensaje
    │
    ▼
3. Hechos nuevos se guardan en Nivel 2 (PostgreSQL)
    │
    ▼
4. Se genera embedding de cada hecho nuevo
    │
    ▼
5. El orquestador pide contexto relevante al Memory Manager
    │
    ▼
6. Memory Manager busca en Nivel 2 (hechos por caso) y Nivel 3 (resumen)
    │
    ▼
7. Contexto se inyecta en el estado compartido
    │
    ▼
8. Agentes ejecutan con contexto completo
    │
    ▼
9. Después del ciclo, se actualiza Nivel 3 (resumen clínico)
    │
    ▼
10. Timeline se actualiza con los eventos del ciclo
```

## 7. Compresión y priorización

### Problema
Si un caso tiene 100+ interacciones, no podemos meter todo en el contexto del LLM.

### Solución: Priorización por relevancia

```python
async def build_context_window(case_id: str, current_query: str, max_tokens: int = 8000) -> str:
    """
    Construye la ventana de contexto óptima para el LLM.
    Prioriza información clínicamente relevante.
    """
    context_parts = []
    remaining_tokens = max_tokens
    
    # 1. Siempre incluir: resumen clínico actual (Nivel 3)
    summary = await get_current_summary(case_id)
    context_parts.append(f"## Resumen clínico\n{summary}")
    remaining_tokens -= count_tokens(summary)
    
    # 2. Siempre incluir: alarmas activas
    alarms = await get_active_alarms(case_id)
    if alarms:
        context_parts.append(f"## Alarmas activas\n{alarms}")
        remaining_tokens -= count_tokens(alarms)
    
    # 3. Siempre incluir: medicación actual
    meds = await get_current_medications(case_id)
    if meds:
        context_parts.append(f"## Medicación actual\n{meds}")
        remaining_tokens -= count_tokens(meds)
    
    # 4. Hechos más relevantes al query actual (búsqueda semántica)
    relevant_facts = await retrieve_relevant_facts(case_id, current_query, limit=20)
    for fact in relevant_facts:
        fact_text = f"- [{fact.fact_type}] {fact.value}"
        if count_tokens(fact_text) <= remaining_tokens:
            context_parts.append(fact_text)
            remaining_tokens -= count_tokens(fact_text)
        else:
            break
    
    # 5. Últimos N mensajes (Nivel 1)
    recent = await get_recent_messages(case_id, limit=10)
    for msg in recent:
        if count_tokens(msg.content) <= remaining_tokens:
            context_parts.append(f"[{msg.role}]: {msg.content}")
            remaining_tokens -= count_tokens(msg.content)
        else:
            break
    
    return "\n\n".join(context_parts)
```

## 8. Cleanup y retención

```yaml
retention_policy:
  nivel_1:
    ttl: 1 hora de inactividad
    cleanup: automático por Redis TTL
    
  nivel_2:
    retention: indefinida mientras el caso exista
    cleanup: cuando el usuario elimina el caso
    
  nivel_3:
    retention: permanente (incluso si el caso se archiva)
    cleanup: solo por solicitud explícita del usuario (GDPR)
    versioning: se mantienen las últimas 5 versiones del resumen
```
