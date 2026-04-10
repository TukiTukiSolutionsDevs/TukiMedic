# 08 — Schemas de Base de Datos

## 1. Overview

Base de datos principal: **PostgreSQL 16** con extensión **pgvector** para embeddings.

```
PostgreSQL 16
├── pgvector (embeddings)
├── pg_trgm (búsqueda fuzzy)
└── uuid-ossp (UUIDs)
```

## 2. Diagrama ER (simplificado)

```
┌──────────┐     ┌──────────┐     ┌──────────────┐
│  users   │────▶│  cases   │────▶│   messages    │
└──────────┘     └────┬─────┘     └──────────────┘
                      │
                      ├──▶ case_clinical_facts
                      ├──▶ documents
                      ├──▶ specialist_invocations
                      ├──▶ case_summaries
                      └──▶ case_timeline
                      
┌───────────────────┐
│ knowledge_chunks  │  (base de conocimiento médico)
└───────────────────┘

┌───────────────────┐
│    audit_log      │  (inmutable)
└───────────────────┘
```

## 3. Schemas

### 3.1 Users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    -- Perfil básico (no obligatorio)
    display_name VARCHAR(100),
    birth_year INTEGER,           -- Solo año, no fecha completa (privacidad)
    biological_sex VARCHAR(20),   -- 'male', 'female', 'other', 'prefer_not_say'
    
    -- Control
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    
    -- Preferencias
    preferences JSONB DEFAULT '{}'::jsonb,
    -- Ejemplo: {"language": "es", "notification": true, "theme": "light"}
    
    -- Soft delete
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;
```

### 3.2 Cases (Casos clínicos / Conversaciones)

```sql
CREATE TABLE cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Identificación del caso
    title VARCHAR(255),                -- Auto-generado del motivo de consulta
    chief_complaint TEXT,              -- Motivo de consulta principal
    
    -- Estado
    status VARCHAR(20) DEFAULT 'active',
    -- 'active', 'paused', 'resolved', 'escalated', 'archived'
    
    -- Triage
    triage_level VARCHAR(10),          -- 'green', 'yellow', 'red'
    triage_confidence FLOAT,
    
    -- Contexto del paciente para este caso
    patient_context JSONB DEFAULT '{}'::jsonb,
    -- {
    --   "age": 35,
    --   "sex": "female",
    --   "known_conditions": ["diabetes tipo 2"],
    --   "current_medications": ["metformina 850mg"],
    --   "known_allergies": ["penicilina"],
    --   "pregnancy": false
    -- }
    
    -- Especialidades activadas
    active_specialties TEXT[] DEFAULT '{}',
    
    -- Métricas
    message_count INTEGER DEFAULT 0,
    loop_count INTEGER DEFAULT 0,
    total_agent_invocations INTEGER DEFAULT 0,
    
    -- Control
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    
    CONSTRAINT valid_status CHECK (status IN ('active', 'paused', 'resolved', 'escalated', 'archived')),
    CONSTRAINT valid_triage CHECK (triage_level IS NULL OR triage_level IN ('green', 'yellow', 'red'))
);

CREATE INDEX idx_cases_user ON cases(user_id);
CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_cases_created ON cases(created_at DESC);
```

### 3.3 Messages

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    
    -- Contenido
    role VARCHAR(20) NOT NULL,         -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    
    -- Metadata del mensaje
    message_type VARCHAR(30) DEFAULT 'text',
    -- 'text', 'question', 'synthesis', 'escalation', 'document_reference'
    
    -- Si es respuesta del sistema, qué agentes participaron
    agents_involved TEXT[] DEFAULT '{}',
    
    -- Si el mensaje referencia un documento
    document_id UUID REFERENCES documents(id),
    
    -- Turno en la conversación
    turn_number INTEGER NOT NULL,
    
    -- Control
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Para búsqueda de texto
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('spanish', content)) STORED
);

CREATE INDEX idx_messages_case ON messages(case_id, turn_number);
CREATE INDEX idx_messages_role ON messages(role);
CREATE INDEX idx_messages_tsv ON messages USING GIN(content_tsv);
```

### 3.4 Clinical Facts (Hechos clínicos extraídos)

```sql
CREATE TABLE case_clinical_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    
    -- Tipo de hecho
    fact_type VARCHAR(50) NOT NULL,
    -- 'symptom', 'antecedent', 'medication', 'allergy', 'vital_sign',
    -- 'lab_result', 'procedure', 'family_history', 'lifestyle', 'context'
    
    -- Contenido
    value TEXT NOT NULL,
    normalized_value TEXT,             -- Valor normalizado (SNOMED, ICD, RxNorm)
    
    -- Origen
    source VARCHAR(50) NOT NULL,       -- 'user_message', 'document', 'inferred'
    source_message_id UUID REFERENCES messages(id),
    source_document_id UUID REFERENCES documents(id),
    source_turn INTEGER,
    
    -- Calidad
    confidence FLOAT DEFAULT 1.0,
    clinical_relevance FLOAT DEFAULT 0.5,
    
    -- Estado
    is_active BOOLEAN DEFAULT true,    -- false si se contradijo o corrigió
    superseded_by UUID REFERENCES case_clinical_facts(id),
    
    -- Vector para búsqueda semántica
    embedding vector(1536),
    
    -- Control
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_fact_type CHECK (fact_type IN (
        'symptom', 'antecedent', 'medication', 'allergy', 'vital_sign',
        'lab_result', 'procedure', 'family_history', 'lifestyle', 'context'
    ))
);

CREATE INDEX idx_facts_case ON case_clinical_facts(case_id);
CREATE INDEX idx_facts_type ON case_clinical_facts(fact_type);
CREATE INDEX idx_facts_active ON case_clinical_facts(is_active) WHERE is_active = true;
CREATE INDEX idx_facts_embedding ON case_clinical_facts 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 3.5 Documents

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Archivo
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size INTEGER NOT NULL,
    
    -- Clasificación
    document_type VARCHAR(50),
    document_subtype VARCHAR(100),
    
    -- Texto extraído
    extracted_text TEXT,
    ocr_confidence FLOAT,
    ocr_method VARCHAR(50),
    
    -- Datos estructurados
    extracted_data JSONB,
    
    -- Vector
    embedding vector(1536),
    
    -- Estado de procesamiento
    processing_status VARCHAR(20) DEFAULT 'pending',
    processing_error TEXT,
    
    -- Control
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    
    CONSTRAINT valid_processing_status CHECK (
        processing_status IN ('pending', 'processing', 'done', 'failed')
    )
);

CREATE INDEX idx_docs_case ON documents(case_id);
CREATE INDEX idx_docs_status ON documents(processing_status);
```

### 3.6 Specialist Invocations (Log de agentes)

```sql
CREATE TABLE specialist_invocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id),
    
    -- Agente
    agent_name VARCHAR(100) NOT NULL,
    agent_model VARCHAR(100),
    
    -- Input/Output
    input_state_snapshot JSONB,        -- Estado al momento de invocación
    output_analysis JSONB NOT NULL,     -- Resultado del agente
    
    -- Métricas
    execution_time_ms INTEGER,
    tokens_used INTEGER,
    model_temperature FLOAT,
    
    -- En qué loop se ejecutó
    loop_iteration INTEGER DEFAULT 0,
    turn_number INTEGER,
    
    -- Control
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_invocations_case ON specialist_invocations(case_id);
CREATE INDEX idx_invocations_agent ON specialist_invocations(agent_name);
```

### 3.7 Case Summaries (Resúmenes clínicos — Nivel 3 de memoria)

```sql
CREATE TABLE case_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id),
    
    -- Resumen
    summary_type VARCHAR(30) DEFAULT 'clinical',
    -- 'clinical' (resumen completo), 'evolution' (nota de evolución)
    
    content JSONB NOT NULL,
    -- Para clinical:
    -- {
    --   "chief_complaint": "...",
    --   "history_present_illness": "...",
    --   "active_problems": [...],
    --   "current_medications": [...],
    --   "known_allergies": [...],
    --   "active_hypotheses": [...],
    --   "pending_studies": [...],
    --   "alarm_signs": [...],
    --   "attention_level": "..."
    -- }
    
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Vector del resumen completo
    embedding vector(1536),
    
    -- Control
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Solo un resumen 'clinical' activo por caso
    is_current BOOLEAN DEFAULT true
);

CREATE INDEX idx_summaries_case ON case_summaries(case_id);
CREATE INDEX idx_summaries_current ON case_summaries(case_id, is_current) WHERE is_current = true;
```

### 3.8 Case Timeline

```sql
CREATE TABLE case_timeline (
    id BIGSERIAL PRIMARY KEY,
    case_id UUID NOT NULL REFERENCES cases(id),
    
    -- Evento
    event_type VARCHAR(50) NOT NULL,
    -- 'case_created', 'message_sent', 'message_received',
    -- 'triage_completed', 'specialty_activated', 'document_uploaded',
    -- 'document_processed', 'red_flag_detected', 'escalation_triggered',
    -- 'loop_started', 'synthesis_completed', 'case_resolved'
    
    description TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Control
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_timeline_case ON case_timeline(case_id, timestamp);
CREATE INDEX idx_timeline_type ON case_timeline(event_type);
```

### 3.9 Knowledge Base (ya definido en 05, resumen)

```sql
-- Ver 05-knowledge-base.md para detalle completo
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(100) NOT NULL,
    source_url TEXT,
    document_title TEXT NOT NULL,
    section_title TEXT,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    specialty TEXT[] NOT NULL,
    language VARCHAR(10) DEFAULT 'es',
    evidence_level VARCHAR(20),
    embedding vector(1536) NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL,
    indexed_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1
);
```

### 3.10 Audit Log (ya definido en 07, resumen)

```sql
-- Ver 07-safety-compliance.md para detalle completo
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    case_id UUID NOT NULL,
    user_id UUID,
    action_type VARCHAR(50) NOT NULL,
    agent_name VARCHAR(100),
    action_detail JSONB NOT NULL,
    result_summary TEXT,
    safety_flags JSONB
);
```

## 4. Migrations

Usamos **Alembic** para migraciones:

```
migrations/
├── env.py
├── versions/
│   ├── 001_initial_schema.py
│   ├── 002_add_pgvector.py
│   ├── 003_add_knowledge_base.py
│   └── ...
└── alembic.ini
```

## 5. Índices de rendimiento

```sql
-- Búsqueda de mensajes por texto (full-text search en español)
CREATE INDEX idx_messages_fts ON messages USING GIN(content_tsv);

-- Búsqueda semántica de hechos clínicos
CREATE INDEX idx_facts_vector ON case_clinical_facts 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Búsqueda semántica de knowledge base
CREATE INDEX idx_knowledge_vector ON knowledge_chunks 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 200);

-- Casos activos por usuario (consulta frecuente)
CREATE INDEX idx_cases_user_active ON cases(user_id, status) 
    WHERE status = 'active';

-- Hechos activos por caso (consulta frecuente)
CREATE INDEX idx_facts_case_active ON case_clinical_facts(case_id, fact_type) 
    WHERE is_active = true;
```
