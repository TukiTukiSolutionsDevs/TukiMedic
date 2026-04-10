# 03 — Flujo de Orquestación y Loops Deliberativos

## 1. Concepto central

MedAgent no responde en una sola pasada. Utiliza **orquestación deliberativa en loop**: el sistema puede entrar en ciclos internos de análisis antes de generar una salida final. Esto es lo que lo diferencia de un chatbot lineal.

## 2. StateGraph de LangGraph

```python
from langgraph.graph import StateGraph, END

# Definición del grafo
workflow = StateGraph(ClinicalCaseState)

# Nodos principales
workflow.add_node("triage", triage_node)
workflow.add_node("anamnesis", anamnesis_node)
workflow.add_node("classification", classification_node)
workflow.add_node("specialists", specialist_dispatch_node)
workflow.add_node("medical_board", medical_board_node)      # NUEVO v2: reemplaza reviewer
workflow.add_node("devils_advocate", devils_advocate_node)   # NUEVO v2: desafía conclusiones
workflow.add_node("guardrail", guardrail_node)               # NUEVO v2: monitor paralelo en tiempo real
workflow.add_node("clarification", clarification_node)
workflow.add_node("synthesizer", synthesizer_node)
workflow.add_node("escalation", escalation_node)

# Entry point
workflow.set_entry_point("triage")

# Edges principales
workflow.add_conditional_edges("triage", triage_router)
workflow.add_edge("anamnesis", "classification")
workflow.add_conditional_edges("classification", classification_router)
workflow.add_edge("specialists", "medical_board")            # → Mesa Médica (no reviewer)
workflow.add_conditional_edges("medical_board", medical_board_router)  # consenso/desacuerdo/clarificación
workflow.add_edge("devils_advocate", "medical_board")        # Round 3: respuestas
workflow.add_edge("clarification", "specialists")            # LOOP BACK
workflow.add_edge("synthesizer", END)                        # Guardrail ya validó en paralelo

# Guardrail corre como proceso PARALELO — no es un edge secuencial.
# Se adjunta como callback/monitor al shared state.
# Ver sección "Guardrail Agent como monitor paralelo" más abajo.

# Compilar
app = workflow.compile(checkpointer=PostgresSaver(conn))
```

## 3. Flujo detallado paso a paso

### Paso 1: Recepción del mensaje

```
Usuario envía mensaje
    │
    ▼
API Gateway recibe y valida
    │
    ▼
Se recupera o crea ClinicalCaseState
    │
    ▼
El mensaje se agrega al estado
    │
    ▼
Se invoca el grafo de LangGraph
```

### Paso 2: Triage (siempre primero)

```
triage_node
    │
    ├── RED FLAG DETECTADO
    │       ▼
    │   escalation_node → Respuesta de urgencia → END
    │
    ├── CASO NUEVO (primera interacción)
    │       ▼
    │   anamnesis_node (necesita más info)
    │
    └── CASO EN PROGRESO (ya hay contexto)
            ▼
        classification_node (directo a clasificar)
```

**Router del triage:**
```python
def triage_router(state: ClinicalCaseState) -> str:
    if state["triage_level"] == "red" and state["safety_flags"]:
        return "escalation"
    if state["loop_count"] == 0 and state["completeness_score"] < 0.5:
        return "anamnesis"
    return "classification"
```

### Paso 3: Anamnesis (si falta info)

```
anamnesis_node
    │
    ▼
Genera preguntas clínicas dirigidas
    │
    ▼
PAUSA — Espera respuesta del usuario
    │
    ▼
Usuario responde
    │
    ▼
Se actualiza estado con nueva info
    │
    ▼
classification_node
```

**Nota importante:** La anamnesis es el único punto donde el sistema **pausa** y espera input del usuario. En todos los demás pasos, el flujo es interno.

### Paso 4: Clasificación

```
classification_node
    │
    ▼
Analiza síntomas + contexto + antecedentes
    │
    ▼
Genera lista ponderada de especialidades
    │
    ▼
specialist_dispatch_node
```

**Ejemplo de salida de clasificación:**
```json
{
  "specialties": [
    { "name": "medicina_general", "weight": 0.9, "reason": "Caso general con múltiples síntomas" },
    { "name": "medicina_interna", "weight": 0.7, "reason": "Fatiga crónica sugiere causa sistémica" },
    { "name": "laboratorio", "weight": 0.5, "reason": "Conviene revisar analítica básica" }
  ],
  "primary": "medicina_general",
  "threshold": 0.4
}
```

Solo se activan especialidades con weight >= threshold.

### Paso 5: Ejecución de especialistas (paralelo)

```
specialist_dispatch_node
    │
    ├──▶ medicina_general_agent ──┐
    │                              │
    ├──▶ medicina_interna_agent ──┤  (en paralelo)
    │                              │
    └──▶ laboratorio_agent ───────┘
                                   │
                                   ▼
                        Resultados consolidados en estado
                                   │
                                   ▼
                            reviewer_node
```

**Dispatch paralelo:**
```python
async def specialist_dispatch_node(state: ClinicalCaseState) -> ClinicalCaseState:
    active = [s for s in state["active_specialties"] if s["weight"] >= THRESHOLD]
    
    # Ejecutar en paralelo
    tasks = [run_specialist(s["name"], state) for s in active]
    results = await asyncio.gather(*tasks)
    
    # Consolidar resultados en el estado
    for name, result in zip([s["name"] for s in active], results):
        state["specialist_outputs"][name] = result
    
    return state
```

### Paso 6: Mesa Médica — el corazón deliberativo v2

La Mesa Médica reemplaza al Reviewer con un proceso de debate estructurado multi-ronda.

```
medical_board_node
    │
    ▼
Round 1: PRESENTACIÓN
    Cada especialista presenta su análisis (ya ejecutado).
    El moderador organiza y estructura los hallazgos.
    │
    ▼
Round 2: DEVIL'S ADVOCATE
    devils_advocate_node desafía cada conclusión.
    Busca suposiciones no examinadas, hipótesis alternativas.
    │
    ▼
Round 3: RESPUESTA Y AJUSTE
    Los especialistas responden a los challenges.
    Pueden ajustar, defender, o reconocer debilidades.
    │
    ▼
EVALUACIÓN DEL MODERADOR
    │
    ├── CONSENSO (full o partial)
    │       ▼
    │   synthesizer_node
    │
    ├── DESACUERDO PERSISTENTE
    │       ▼
    │   Ronda extra (máx. 2 extras) → medical_board_node (LOOP)
    │
    └── INFO FALTANTE CRÍTICA
            ▼
        clarification_node → LOOP BACK a specialists
```

**Router de la Mesa Médica:**
```python
def medical_board_router(state: ClinicalCaseState) -> str:
    board = state["medical_board_result"]
    
    # Safety: límite de rondas de debate
    if state["board_rounds"] >= state["max_board_rounds"]:
        return "synthesizer"  # Forzar cierre con lo que hay
    
    if board["resolution_path"] == "clarification":
        state["loop_count"] += 1
        return "clarification"
    
    if board["resolution_path"] == "extra_round":
        state["board_rounds"] += 1
        return "devils_advocate"  # Nueva ronda de challenge
    
    # Consenso alcanzado
    return "synthesizer"
```

### Paso 7: Clarificación (genera el loop)

```
clarification_node
    │
    ▼
Identifica qué info falta para resolver desacuerdos de la Mesa Médica
    │
    ▼
Genera preguntas dirigidas
    │
    ▼
PAUSA — Espera respuesta del usuario
    │
    ▼
Usuario responde
    │
    ▼
Se actualiza estado
    │
    ▼
specialist_dispatch_node (RE-EJECUTA con nueva info)
    │
    ▼
medical_board_node (RE-DEBATE)
    │
    ▼
[Puede loopear de nuevo o seguir a synthesis]
```

### Paso 8: Síntesis

```
synthesizer_node
    │
    ▼
Toma TODOS los outputs: triage, anamnesis, especialistas, Mesa Médica
    │
    ▼
Consolida en UNA respuesta coherente
(El Guardrail Agent ya validó en paralelo durante todo el proceso)
    │
    ▼
END — Respuesta se envía al usuario
```

> **Nota v2:** Ya no hay un paso separado de "Safety" al final. El Guardrail Agent
> monitorea en tiempo real durante TODOS los pasos. Si detecta un problema,
> interrumpe el flujo en ese momento — no espera al final.

## 4. Diagrama de flujo completo (v2)

```
 ┌─────────────────────────────────────────────────────────────────┐
 │  GUARDRAIL AGENT (proceso paralelo — monitorea TODO en tiempo  │
 │  real, puede INTERRUMPIR en cualquier punto si detecta riesgo) │
 ├─────────────────────────────────────────────────────────────────┤
 │                                                                 │
 │                      ┌──────────┐                               │
 │                      │  INICIO  │                               │
 │                      └────┬─────┘                               │
 │                           │                                     │
 │                      ┌────▼─────┐                               │
 │                      │  TRIAGE  │                               │
 │                      └────┬─────┘                               │
 │                           │                                     │
 │                ┌──────────┼──────────┐                          │
 │                ▼          ▼          ▼                           │
 │           [RED FLAG]  [NUEVO]    [EN PROG]                      │
 │                │          │          │                           │
 │                ▼          ▼          │                           │
 │           ESCALATION  ANAMNESIS     │                           │
 │                │          │          │                           │
 │                ▼          ▼          ▼                           │
 │               END    CLASSIFICATION ◄┘                          │
 │                           │                                     │
 │                      ┌────▼──────┐                              │
 │                      │SPECIALISTS│ (paralelo)                   │
 │                      └────┬──────┘                              │
 │                           │                                     │
 │                      ┌────▼──────────┐                          │
 │                      │  MESA MÉDICA  │                          │
 │                      └────┬──────────┘                          │
 │                           │                                     │
 │                  Round 1: Presentación                          │
 │                  Round 2: Devil's Advocate                      │
 │                  Round 3: Respuesta/Ajuste                      │
 │                  Moderador evalúa                                │
 │                           │                                     │
 │                ┌──────────┼──────────────┐                      │
 │                ▼          ▼              ▼                       │
 │           [CONSENSO] [DESACUERDO]  [MISSING INFO]               │
 │                │          │              │                       │
 │                │          ▼              ▼                       │
 │                │     RONDA EXTRA    CLARIFICATION                │
 │                │          │              │                       │
 │                │          ▼              ▼                       │
 │                │     MESA MÉDICA   SPECIALISTS (LOOP)           │
 │                │      (RE-DEBATE)       │                       │
 │                │                        ▼                       │
 │                │                   MESA MÉDICA                  │
 │                │                                                │
 │                ▼                                                │
 │           SYNTHESIZER                                           │
 │                │                                                │
 │                ▼                                                │
 │               END                                               │
 │                                                                 │
 └─────────────────────────────────────────────────────────────────┘
```

## 5. Control de loops

### Parámetros de control

```python
LOOP_CONFIG = {
    "max_loops": 3,                 # Máximo 3 iteraciones de loop completo (specialist → board → clarification)
    "max_board_rounds": 5,          # Máximo 5 rondas de debate en Mesa Médica (3 base + 2 extra)
    "max_specialists_per_loop": 4,  # Máximo 4 especialidades simultáneas
    "max_questions_per_turn": 4,    # Máximo 4 preguntas por turno de anamnesis/clarificación
    "min_completeness_for_synthesis": 0.6,  # Mínimo 60% de completitud
    "force_synthesis_after_loops": True,     # Forzar síntesis si se agotan loops
    "min_consensus_for_synthesis": "partial",  # "full" o "partial" — nivel mínimo para sintetizar
}
```

### ¿Por qué limitar loops?
1. **UX**: El usuario no quiere esperar 5 minutos
2. **Costos**: Cada loop multiplica llamadas a LLM
3. **Seguridad**: Un loop infinito en contexto médico es peligroso
4. **Suficiencia**: Después de 3 iteraciones, lo que falta probablemente requiere atención presencial

## 6. Checkpointing y recovery

LangGraph permite guardar el estado del grafo en cada nodo. Esto es crítico para:

1. **Recovery**: Si el sistema se cae, puede retomar desde el último checkpoint
2. **Debugging**: Se puede inspeccionar exactamente qué decidió cada agente
3. **Audit**: Log completo de decisiones clínicas
4. **Continuación**: Si el usuario se desconecta y vuelve, el caso sigue donde quedó

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver(connection_string=DB_URL)
app = workflow.compile(checkpointer=checkpointer)

# Cada invocación usa un thread_id (= case_id)
config = {"configurable": {"thread_id": case_id}}
result = await app.ainvoke(state, config=config)
```

## 7. Streaming durante deliberación

Mientras el sistema delibera internamente, el usuario ve indicadores de progreso:

```
[Analizando tu consulta...]              → Triage ejecutándose
[Evaluando áreas médicas relevantes...]  → Clasificación
[Consultando especialidades...]          → Especialistas en paralelo
[Especialistas debatiendo el caso...]    → Mesa Médica Round 1
[Revisando hipótesis alternativas...]    → Devil's Advocate (Round 2)
[Ajustando análisis...]                  → Round 3 — Respuesta/Ajuste
[Evaluando consenso...]                  → Moderador evalúa
[Preparando tu orientación...]           → Sintetizador
[Respuesta lista]                        → Stream de tokens
```

Esto se implementa con eventos de LangGraph que se transmiten por WebSocket:

```python
async for event in app.astream_events(state, config=config):
    if event["event"] == "on_chain_start":
        node_name = event["name"]
        await ws.send_json({
            "type": "progress",
            "stage": node_name,
            "message": STAGE_MESSAGES[node_name]
        })
    elif event["event"] == "on_chat_model_stream":
        token = event["data"]["chunk"].content
        await ws.send_json({
            "type": "token",
            "content": token
        })
```

## 8. Guardrail Agent como monitor paralelo

A diferencia del Safety Validator v1 que era un nodo secuencial al final, el Guardrail Agent v2 corre como un **proceso paralelo** que monitorea el shared state en tiempo real.

### Implementación

```python
from langgraph.pregel import RetryPolicy

async def guardrail_monitor(state: ClinicalCaseState) -> Optional[GuardrailCheck]:
    """
    Se ejecuta en PARALELO con cada nodo del grafo.
    Monitorea el shared state y puede interrumpir el flujo.
    """
    check = await guardrail_agent.evaluate(state)
    
    if check.interrupt_required:
        # Interrumpir el flujo inmediatamente
        state["guardrail_interrupt"] = True
        state["guardrail_reason"] = check.escalation_reason
        return check
    
    if check.modification_required:
        # Marcar el output actual para modificación
        state["pending_modifications"].extend(check.modifications)
    
    # Registrar el chequeo (audit trail)
    state["guardrail_checks"].append(check)
    return check

# Adjuntar guardrail como callback en cada nodo
for node_name in ["triage", "anamnesis", "specialists", "medical_board", "synthesizer"]:
    workflow.add_node(
        f"{node_name}_with_guardrail",
        RunnableParallel(
            main=node_functions[node_name],
            guardrail=guardrail_monitor,
        )
    )
```

### Cuándo interrumpe el Guardrail

```yaml
interrupciones_inmediatas:
  - Agente genera diagnóstico definitivo (ej: "usted tiene cáncer")
  - Agente prescribe medicamento con dosis
  - Se detecta red flag nuevo no capturado por triage
  - Contenido que podría causar daño si el usuario actúa en base a él

modificaciones_sin_interrupción:
  - Agregar disclaimers faltantes
  - Suavizar lenguaje diagnóstico (ej: "podría tratarse de" en vez de "es")
  - Agregar signos de alarma que el agente omitió
  - Ajustar nivel de urgencia si es inconsistente con hallazgos
```
