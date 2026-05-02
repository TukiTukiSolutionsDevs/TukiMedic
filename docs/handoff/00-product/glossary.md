# Glosario de Tuki-Medic

Definiciones canónicas del dominio y del sistema. Cuando un doc dice
"Mesa de Especialistas" o "Triage Level", esta es la fuente de verdad.

## Términos clínicos del sistema

| Término | Definición |
|---------|-----------|
| **Triage Level** | Clasificación de urgencia: `green` (leve, autocuidado posible), `yellow` (consulta no urgente), `red` (emergencia inmediata) |
| **Red Flag** | Señal clínica de alarma detectada determinísticamente desde `data/red_flags.yaml` antes de invocar el LLM. Si hay match → RED automático, sin tokens. |
| **Attention Level** | Recomendación de urgencia en la respuesta final: `rutina`, `24-48h`, `hoy`, `urgencia`. Siempre clampeado por el Triage ceiling. |
| **Escalation** | Flujo de emergencia: mensaje "ir a urgencias ahora", `attention_level=urgencia`. Hay dos paths: red flags reales y guardrail interrupt en caso no emergente. |
| **Mesa de Especialistas** | Etapa del grafo donde 5 specialists corren en paralelo (`asyncio.gather`) y el Medical Board consolida + puede pedir clarification. |
| **Completeness Score** | 0.0–1.0: qué tan completa es la info clínica recibida. Si < 0.5 en el primer turno y el mensaje no es "rico", el grafo activa Anamnesis. |
| **Anamnesis Loop** | Medical Board puede solicitar más datos al paciente hasta 3 veces antes de forzar síntesis (`max_loops: 3` en `LOOP_CONFIG`). |
| **False Consensus Risk** | 0.0–1.0: riesgo de consenso ficticio en la Mesa. Si ≥ 0.5 con `resolution_path=extra_round` y `consensus_level=disagreement`, se activa Devil's Advocate. |
| **Disclaimer** | Texto fijo concatenado a toda respuesta: `"MedAgent es una herramienta de orientación; no reemplaza la consulta médica profesional."` |
| **KB / Knowledge Base** | Base de conocimiento médico indexada en pgvector. Contexto RAG inyectado al grafo antes de correr. Las fuentes (PubMed/WHO) aún no están cargadas. |

## Términos de arquitectura

| Término | Definición |
|---------|-----------|
| **ClinicalCaseState** | TypedDict compartido por todos los nodos del grafo LangGraph. Definido en `backend/app/orchestrator/state.py`. |
| **LLM Router** | `app/services/llm_router.py`: resuelve credenciales del vault y crea modelos `fast`/`smart` por proveedor. `fast` → alto throughput (triage, specialists). `smart` → razonamiento profundo (medical_board). |
| **Vault** | Almacén AES-256-GCM de credenciales LLM en Postgres. No se usan variables de entorno para la API key del LLM — la clave se descifra en tiempo de ejecución. |
| **Graph Cache** | `asyncio.Lock` in-memory por worker que cachea el grafo LangGraph compilado (TTL 5 min). En multi-worker, cada proceso tiene su propio cache. |
| **Audit Chain** | Hash chain global SHA-256 en tabla `audit_logs` con `previous_hash` + `chain_hash`. Verifiable via `GET /admin/audit/verify-chain`. |
| **Tier Gating** | Bloqueo de features según `subscription_tier` del usuario (`free` vs `paid`). Enforcement en `core/dependencies.py: require_subscription_tier()`. |
| **L1 Memory** | Redis: historial de mensajes del turno actual (RPUSH + LTRIM). Efímero — si Redis se flushea, el historial se pierde. |
| **L2 Memory** | PostgreSQL + pgvector: hechos clínicos extraídos por Anamnesis, con embeddings semánticos para retrieval relevante. |
| **L3 Memory** | PostgreSQL: patient timeline + profile. Persiste entre sesiones. Incluye alergias, medicación activa, condiciones crónicas. |
| **`_clamp_*`** | Patrón de funciones defensivas que anclan outputs de LLMs a evidencia estructurada. Ej: `_clamp_triage`, `_clamp_attention`, `_clamp_interrupt`. |

## Agentes (8 categorías)

| Agente | Temperatura | Responsabilidad |
|--------|-------------|----------------|
| **Triage** | 0.0 | Clasifica urgencia, detecta red flags, filtra prompt injection |
| **Anamnesis** | 0.3 | Extrae hechos clínicos, pregunta datos faltantes |
| **Classifier** | 0.2 | Mapea síntomas → lista de especialidades activas |
| **Specialists** | 0.3 | Análisis clínico por especialidad en paralelo (11 implementados) |
| **Medical Board** | 0.2 | Consolida debate de specialists, decide si seguir o pedir más info (`smart` tier) |
| **Devil's Advocate** | 0.5 | Cuestiona hipótesis dominante, reduce confirmation bias |
| **Guardrail** | 0.0 | Safety monitor: detecta violations clínicas en la respuesta final |
| **Synthesizer** | 0.4 | Genera respuesta final para el paciente desde todos los outputs |

## Endpoints clave

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Registro, devuelve access + refresh JWT |
| `/api/v1/auth/login` | POST | Login, devuelve tokens + UserResponse |
| `/api/v1/auth/refresh` | POST | Rota tokens. Gotcha: refresh token no incluye role/tier en payload. |
| `/api/v1/auth/me` | GET | Perfil del usuario autenticado |
| `/api/v1/auth/me` | DELETE | GDPR erasure: anonimiza PII, desactiva cuenta |
| `/api/v1/chat/ws` | WS | Chat clínico. Auth via primer mensaje JSON con token. |
| `/api/v1/documents/upload` | POST | Gateado `paid` |
| `/api/v1/export/pdf/{case_id}` | GET | Gateado `paid` |
| `/api/v1/admin/users` | GET | RBAC admin |
| `/api/v1/admin/kb/ingest` | POST | Dispara indexador KB |
| `/api/v1/admin/audit/verify-chain` | GET | Valida integridad del audit log |
| `/health` | GET | Liveness: proceso up, sin dependencias |
| `/health/ready` | GET | Readiness: postgres + redis + storage |
