# 02 — Especificación Detallada de Agentes

## Convención general

Cada agente en MedAgent es un **nodo** dentro del StateGraph de LangGraph. Todos comparten el mismo estado (`ClinicalCaseState`) pero solo leen/escriben las partes que les competen.

### Estructura base de un agente:

```python
class BaseAgent:
    name: str                    # Nombre del agente
    role: str                    # Descripción de su rol
    model: str                   # Modelo LLM a usar
    temperature: float           # Temperatura del LLM
    tools: list[Tool]            # Herramientas disponibles
    system_prompt: str           # Prompt del sistema
    max_tokens: int              # Límite de tokens de respuesta
    
    async def execute(self, state: ClinicalCaseState) -> ClinicalCaseState:
        """Ejecuta el agente y retorna el estado actualizado"""
        ...
```

---

## Agente 1: Orquestador Clínico Central

### Propósito
No genera contenido clínico. **Coordina** qué agentes participan, en qué orden, cuándo loopear, y cuándo cerrar.

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `clinical_orchestrator` |
| **Modelo** | GPT-4o (necesita razonamiento complejo) |
| **Temperatura** | 0.1 (decisiones determinísticas) |
| **Herramientas** | route_to_agent, request_loop, close_case, escalate |

### Lógica de decisión

```
INPUT: ClinicalCaseState actualizado

DECIDE:
1. ¿Es primera iteración? → Enviar a Triage
2. ¿Triage = rojo? → Activar Safety + Escalamiento inmediato
3. ¿Hay info faltante crítica? → Activar Anamnesis
4. ¿Ya se clasificó? → Activar especialidades según clasificación
5. ¿Hay contradicciones? → Activar Reviewer
6. ¿Todo coherente + completo? → Enviar a Sintetizador
7. ¿Loop count > max_loops? → Forzar síntesis con lo que hay
```

### Output
No produce texto para el usuario. Produce **decisiones de ruteo**:
```python
class OrchestratorDecision:
    next_agents: list[str]       # Qué agentes ejecutar
    parallel: bool               # ¿En paralelo?
    reason: str                  # Por qué esta decisión
    loop_back: bool             # ¿Es un loop?
    force_close: bool           # ¿Cerrar aunque falte info?
```

---

## Agente 2: Triage

### Propósito
Clasificar la urgencia del caso en la primera interacción. Determina si es **verde** (orientación normal), **amarillo** (requiere atención pero no inmediata) o **rojo** (urgencia, posible emergencia).

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `triage_agent` |
| **Modelo** | GPT-4o-mini (rápido, scoring) |
| **Temperatura** | 0.0 (cero creatividad en triage) |
| **Herramientas** | symptom_scorer, red_flag_checker, age_risk_evaluator |

### Red Flags (escalamiento automático a ROJO):

```yaml
cardiovascular:
  - dolor torácico agudo + disnea
  - dolor torácico + irradiación a brazo/mandíbula
  - síncope inexplicado

neurológico:
  - debilidad unilateral súbita
  - pérdida de habla o visión
  - cefalea "la peor de mi vida"
  - convulsión activa

respiratorio:
  - dificultad respiratoria severa
  - cianosis
  - ahogo que no mejora en reposo

psiquiátrico:
  - ideación suicida activa
  - autolesión reciente
  - psicosis aguda

pediátrico:
  - fiebre >38°C en neonato (<3 meses)
  - letargia o irritabilidad extrema en lactante
  - dificultad respiratoria en pediátrico

obstétrico:
  - sangrado vaginal en embarazo
  - dolor abdominal severo en embarazo
  - pérdida de líquido amniótico

general:
  - sangrado activo no controlable
  - reacción alérgica con edema de vía aérea
  - trauma con deformidad o pérdida de conciencia
```

### Output
```python
class TriageResult:
    level: Literal["green", "yellow", "red"]
    confidence: float            # 0.0 - 1.0
    red_flags_detected: list[str]
    reasoning: str               # Explicación de la clasificación
    recommended_urgency: str     # "rutina", "24-48h", "inmediato"
```

---

## Agente 3: Anamnesis

### Propósito
Formular preguntas clínicas relevantes para completar información faltante. No responde al paciente, **pregunta**.

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `anamnesis_agent` |
| **Modelo** | GPT-4o |
| **Temperatura** | 0.3 |
| **Herramientas** | question_template_selector, symptom_expander, pending_question_tracker |

### Áreas de indagación

```yaml
datos_basicos:
  - edad (si no se conoce)
  - sexo biológico
  - peso/talla (si relevante)

motivo_consulta:
  - localización exacta
  - duración
  - intensidad (escala 1-10)
  - carácter (punzante, opresivo, quemante, etc.)
  - irradiación
  - factores agravantes
  - factores atenuantes
  - evolución temporal

antecedentes:
  - enfermedades previas conocidas
  - cirugías previas
  - alergias conocidas
  - medicación actual
  - antecedentes familiares relevantes

contexto:
  - embarazo actual
  - viajes recientes
  - exposición a tóxicos o agentes
  - actividad física reciente
  - alimentación reciente (si GI)
  - estrés o cambios emocionales
```

### Comportamiento
- Prioriza preguntas por **relevancia clínica** (no pregunta todo de golpe)
- Máximo 3-4 preguntas por turno
- Marca preguntas como `respondida`, `pendiente`, o `no aplica`
- Si el paciente no sabe, lo registra como "desconocido" (no insiste)

### Output
```python
class AnamnesisResult:
    questions: list[ClinicalQuestion]     # Preguntas formuladas
    extracted_facts: list[ClinicalFact]   # Hechos extraídos de respuestas previas
    completeness_score: float             # 0.0 - 1.0 qué tan completa está la anamnesis
    critical_gaps: list[str]              # Info crítica que falta
```

---

## Agente 4: Clasificador

### Propósito
Determinar qué especialidades médicas deben activarse para este caso. No elige una sola — propone un **conjunto ponderado**.

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `classification_agent` |
| **Modelo** | GPT-4o |
| **Temperatura** | 0.2 |
| **Herramientas** | specialty_matcher, symptom_to_specialty_map, icd10_lookup |

### Mapa de síntomas → especialidades (ejemplo)

```yaml
dolor_abdominal:
  - gastroenterología: 0.8
  - medicina_interna: 0.6
  - ginecología: 0.4  # si mujer en edad fértil
  - cirugía: 0.3      # si signos de abdomen agudo
  - urología: 0.2     # si localización flanco

fatiga_cronica:
  - medicina_interna: 0.8
  - endocrinología: 0.7
  - hematología: 0.5
  - psiquiatría: 0.4
  - nutrición: 0.3

cefalea:
  - neurología: 0.7
  - medicina_general: 0.6
  - oftalmología: 0.3
  - otorrinolaringología: 0.2
```

### Output
```python
class ClassificationResult:
    specialties: list[SpecialtyScore]    # Especialidades con peso
    primary_specialty: str                # La de mayor peso
    reasoning: str                        # Por qué estas especialidades
    differential_considerations: list[str] # Diagnósticos diferenciales iniciales
```

---

## Agente 5: Medicina General

### Propósito
Análisis generalista del caso. Primera aproximación clínica, visión holística.

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `general_medicine_agent` |
| **Modelo** | GPT-4o |
| **Temperatura** | 0.3 |
| **Herramientas** | knowledge_search, clinical_guidelines_retriever, drug_interaction_checker |

### System Prompt (extracto)
```
Eres un médico general experimentado. Tu rol es:
1. Analizar el caso clínico completo presentado
2. Identificar los problemas principales
3. Proponer diagnósticos diferenciales probables
4. Sugerir qué estudios o evaluaciones serían relevantes
5. Identificar si hay aspectos que requieran otra especialidad

NUNCA:
- Diagnostiques de forma definitiva
- Recetes medicamentos específicos con dosis
- Minimices síntomas potencialmente graves
- Ignores factores de riesgo mencionados

SIEMPRE:
- Explica tu razonamiento clínico
- Menciona qué información adicional sería útil
- Señala si hay signos de alarma
- Recomienda seguimiento o evaluación presencial cuando aplique
```

### Output
```python
class GeneralMedicineAnalysis:
    clinical_impression: str              # Impresión clínica general
    differential_diagnosis: list[DiagnosisHypothesis]  # Diferenciales ordenados
    suggested_studies: list[str]          # Estudios sugeridos
    risk_factors: list[str]              # Factores de riesgo identificados
    recommendations: list[str]           # Recomendaciones generales
    referral_suggestion: list[str]       # Derivaciones sugeridas
    alarm_signs: list[str]              # Signos de alarma a vigilar
    confidence: float                    # Confianza en el análisis
```

---

## Agente 6: Medicina Interna

### Propósito
Análisis sistémico. Busca causas no obvias, comorbilidades, complejidad multiorgánica.

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `internal_medicine_agent` |
| **Modelo** | GPT-4o |
| **Temperatura** | 0.3 |
| **Herramientas** | knowledge_search, lab_interpreter, comorbidity_analyzer |

### Cuándo se activa
- Cuando el caso tiene complejidad sistémica
- Cuando hay múltiples síntomas aparentemente no relacionados
- Cuando la clasificación lo pondera >0.5
- Cuando el caso incluye pacientes con múltiples comorbilidades

### Output
```python
class InternalMedicineAnalysis:
    systemic_assessment: str              # Evaluación sistémica
    organ_systems_involved: list[str]     # Sistemas orgánicos implicados
    differential_diagnosis: list[DiagnosisHypothesis]
    lab_interpretation: Optional[str]     # Si hay labs, su interpretación
    medication_review: Optional[str]      # Si hay medicación, revisión
    comorbidity_impact: str              # Cómo las comorbilidades afectan
    urgency_assessment: str              # Evaluación de urgencia desde interna
```

---

## Agente 7: Mesa Médica (Medical Board) — NUEVO v2

### Propósito
Debate estructurado multi-ronda entre especialistas. Reemplaza al Revisor de Contradicciones con un proceso deliberativo más robusto, inspirado en la arquitectura multi-agente de Google g-AMIE (2026).

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `medical_board` |
| **Modelo** | GPT-4o |
| **Temperatura** | 0.2 (decisiones deliberativas con algo de flexibilidad) |
| **Herramientas** | debate_moderator, consensus_evaluator, round_manager |

### Flujo de la Mesa Médica

```
Round 1: PRESENTACIÓN
  Cada especialista presenta su análisis (ya ejecutado en paralelo).
  El moderador organiza y estructura los hallazgos.

Round 2: DEVIL'S ADVOCATE
  El Agente Devil's Advocate desafía cada conclusión.
  Busca suposiciones no examinadas, hipótesis alternativas, sesgos.

Round 3: RESPUESTA Y AJUSTE
  Los especialistas responden a los challenges.
  Pueden ajustar, defender, o reconocer debilidades en su análisis.

EVALUACIÓN DEL MODERADOR:
  ├── Consenso → Síntesis
  ├── Desacuerdo → Ronda extra (máx. 2 extras)
  └── Info faltante → Clarificación al paciente
```

### Qué evalúa el moderador

```yaml
consenso:
  - ¿Los especialistas coinciden en los diagnósticos diferenciales principales?
  - ¿Las recomendaciones son compatibles entre sí?
  - ¿El Devil's Advocate fue respondido satisfactoriamente?

desacuerdo:
  - ¿Hay diagnósticos diferenciales mutuamente excluyentes?
  - ¿Los niveles de urgencia difieren significativamente?
  - ¿Persisten suposiciones no examinadas después del Round 3?

info_faltante:
  - ¿Hay preguntas clínicas críticas sin responder?
  - ¿Se necesitan datos adicionales para resolver el desacuerdo?
```

### Output
```python
class MedicalBoardResult:
    consensus_level: Literal["full", "partial", "disagreement"]
    debate_rounds: int                           # Rondas ejecutadas (mín. 3)
    specialist_analyses: dict[str, SpecialistAnalysis]  # Análisis originales
    adjusted_analyses: dict[str, SpecialistAnalysis]    # Post-debate
    challenges_addressed: list[ChallengeResponse]       # Respuestas a challenges
    resolution_path: Literal["synthesis", "extra_round", "clarification"]
    key_agreements: list[str]                    # Puntos de consenso
    key_disagreements: list[str]                 # Puntos de desacuerdo
    moderator_summary: str                       # Resumen del moderador
```

---

## Agente 8: Devil's Advocate — NUEVO v2

### Propósito
Desafiar explícitamente las conclusiones de cada especialista para prevenir el **falso consenso**. Basado en investigación que demuestra que LLMs tienden a concordar entre sí sin cuestionamiento genuino — asignar un rol explícito de Devil's Advocate produce **127x más desacuerdo genuino**.

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `devils_advocate` |
| **Modelo** | GPT-4o |
| **Temperatura** | 0.5 (necesita creatividad para desafiar) |
| **Herramientas** | counter_argument_generator, evidence_challenger, assumption_detector |

### Qué desafía

```yaml
por_especialista:
  - ¿Qué suposiciones está haciendo sin evidencia directa?
  - ¿Qué diagnósticos diferenciales NO consideró y debería?
  - ¿Hay sesgos de anclaje (fijarse en el primer síntoma)?
  - ¿La evidencia presentada realmente soporta la conclusión?

global:
  - ¿Todos los especialistas están de acuerdo demasiado rápido? (señal de falso consenso)
  - ¿Hay hipótesis alternativas que nadie mencionó?
  - ¿Se están ignorando datos del paciente que no encajan con las hipótesis?
  - ¿El nivel de urgencia es consistente con los hallazgos?
```

### System Prompt (extracto)
```
Tu rol es DESAFIAR, no confirmar. Eres el abogado del diablo en una mesa médica.

SIEMPRE:
- Cuestiona cada conclusión con argumentos clínicos válidos
- Propón al menos una hipótesis alternativa por especialista
- Identifica suposiciones implícitas que nadie verbalizó
- Señala si los especialistas están acordando sin evidencia suficiente

NUNCA:
- Inventes patologías sin base clínica
- Generes alarma innecesaria
- Contradigas por contradecir — tus challenges deben tener fundamento médico
```

### Output
```python
class ChallengeResult:
    challenges_per_specialist: dict[str, list[Challenge]]
    alternative_hypotheses: list[AlternativeHypothesis]
    unexamined_assumptions: list[str]
    false_consensus_risk: float          # 0.0-1.0 qué tan probable es falso consenso
    critical_questions: list[str]        # Preguntas que deberían haberse hecho
```

---

## Agente 9: Guardrail Agent — ACTUALIZADO v2 (reemplaza Safety Validator)

### Propósito
Monitor de seguridad en **tiempo real** inspirado en Google g-AMIE (2026). A diferencia del Safety Validator original que solo chequeaba la respuesta final, el Guardrail Agent **monitorea CADA mensaje** y puede **interrumpir el flujo** en cualquier punto.

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `guardrail_agent` |
| **Modelo** | GPT-4o |
| **Temperatura** | 0.0 (cero creatividad en seguridad) |
| **Herramientas** | red_flag_scanner, disclaimer_enforcer, escalation_trigger, flow_interruptor |

### Diferencia clave vs. Safety Validator v1

```
v1 (Safety Validator):
  Especialistas → Reviewer → Sintetizador → [Safety] → END
  Solo chequeaba la RESPUESTA FINAL.

v2 (Guardrail Agent):
  ┌─────────────────────────────────────────────────────┐
  │ GUARDRAIL AGENT (proceso paralelo)                  │
  │ Monitorea shared state en tiempo real               │
  │ Puede INTERRUMPIR en cualquier nodo                 │
  ├─────────────────────────────────────────────────────┤
  │ Triage │ Anamnesis │ Specialists │ Mesa │ Synthesis │
  └─────────────────────────────────────────────────────┘
```

### Checklist de validación continua

```yaml
en_cada_nodo:
  - ¿Algún agente está usando lenguaje diagnóstico definitivo?
  - ¿Se está minimizando un síntoma potencialmente grave?
  - ¿Hay prescripción de medicamentos con dosis específicas?
  - ¿Se detectaron red flags nuevos que no pasaron por triage?

en_respuesta_final:
  - ¿Incluye disclaimer de "no reemplaza al médico"?
  - ¿Los signos de alarma están claramente mencionados?
  - ¿Se recomienda atención presencial cuando corresponde?
  - ¿El tono es empático pero no condescendiente?
  - ¿El nivel de lectura es apropiado para el público?
```

### Capacidades de interrupción

```python
class InterruptionLevel(Enum):
    OBSERVE = "observe"        # Solo registra, no interrumpe
    FLAG = "flag"              # Marca para revisión pero no frena
    MODIFY = "modify"          # Modifica el output del nodo actual
    INTERRUPT = "interrupt"    # Frena el flujo y escala
```

### Output
```python
class GuardrailCheck:
    approved: bool                       # ¿El contenido actual es seguro?
    violations: list[SafetyViolation]    # Violaciones detectadas
    interrupt_required: bool             # ¿Hay que frenar el flujo?
    modification_required: bool          # ¿Hay que modificar el output?
    modifications: list[str]            # Modificaciones sugeridas
    escalation_required: bool           # ¿Escalar a humano?
    escalation_reason: Optional[str]
    node_monitored: str                 # Qué nodo se estaba ejecutando
    timestamp: datetime                 # Cuándo se detectó
```

---

## Agente 10: Sintetizador

### Propósito
Tomar todos los outputs de los agentes y consolidar UNA respuesta clara, priorizada y entendible para el paciente.

### Especificación

| Campo | Valor |
|-------|-------|
| **Nombre** | `synthesizer_agent` |
| **Modelo** | GPT-4o |
| **Temperatura** | 0.4 (algo de naturalidad en la redacción) |
| **Herramientas** | response_formatter, readability_scorer |

### Estructura de la respuesta sintetizada

```markdown
## Análisis de tu consulta

[Resumen empático de lo que entendió el sistema]

## Áreas que evaluamos

- Medicina General: [resumen breve]
- Medicina Interna: [resumen breve]
- [otras que apliquen]

## Lo que encontramos

[Explicación clara y priorizada de hallazgos]

## Aspectos importantes a vigilar

- [Signo de alarma 1]
- [Signo de alarma 2]

## Próximos pasos sugeridos

1. [Acción concreta 1]
2. [Acción concreta 2]

## Nivel de atención recomendado

[Rutina / Consultar en 24-48h / Buscar atención hoy / Urgencia]

---
⚠️ Esta orientación no reemplaza la consulta médica presencial.
Especialidades que analizaron tu caso: [lista]
```

### Output
```python
class SynthesizedResponse:
    patient_response: str                # Texto para el paciente
    clinical_summary: str                # Resumen técnico (para logs)
    specialties_involved: list[str]      # Qué especialidades participaron
    attention_level: str                 # Nivel de atención recomendado
    follow_up_questions: list[str]       # Preguntas de seguimiento opcionales
    alarm_signs: list[str]              # Signos de alarma mencionados
```

---

## Agentes de Especialidad (Post-MVP)

Estos siguen la misma estructura base pero con knowledge base y prompts especializados:

| Agente | Activación | Knowledge Scope |
|--------|-----------|-----------------|
| Pediatría | Paciente <18 años | Guías pediátricas, desarrollo, vacunación |
| Ginecología | Síntomas gineco/obstétricos | Salud reproductiva, embarazo, ciclo menstrual |
| Dermatología | Lesiones cutáneas, erupciones | Dermatología clínica, imágenes de referencia |
| Traumatología | Trauma, dolor musculoesquelético | Ortopedia, fracturas, lesiones deportivas |
| Psiquiatría | Síntomas emocionales/conductuales | Salud mental, crisis, terapéutica |
| Nutrición | Alimentación, peso, metabolismo | Nutrición clínica, dietas terapéuticas |
| Laboratorio | Resultados de análisis subidos | Valores de referencia, interpretación |
| Farmacología | Medicación mencionada | Interacciones, contraindicaciones, dosis |

Cada uno se implementa como un **plugin** que registra sus triggers y se integra al grafo sin modificar el core.
