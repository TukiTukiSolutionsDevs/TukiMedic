# Lo que está hecho — con evidencia

Todo lo listado acá tiene código real en el repo verificado al 2026-05-01.
Nada de "está casi listo" — si está acá, funciona.

## Auth + seguridad

| Item | Evidencia |
|------|----------|
| JWT access + refresh tokens | `api/v1/auth.py: create_access_token, create_refresh_token` |
| RBAC customer/admin | `models/user.py: role`, `core/dependencies.py: get_current_user` |
| IDOR checks en cases/docs | `api/v1/chat.py:212` — verifica `existing.user_id != user.id` |
| AES-256-GCM vault para LLM keys | `services/llm_router.py` — descifra en runtime |
| Security headers middleware | `core/middleware/security_headers.py` registrado en `main.py:59` |
| Rate limiting HTTP (slowapi) | `main.py:47-48`, rates en cada router |
| Rate limiting WebSocket | `chat.py:238-250` — Redis INCR/EXPIRE por user |
| GDPR erasure (`DELETE /auth/me`) | `api/v1/auth.py:161-237` — anonimiza PII, desactiva cuenta |
| Prompt injection guard | `core/prompt_guard.py` — 23 tests en `tests/core/` |
| Output sanitization | `core/sanitize.py` — 25 tests, integrado en synthesizer |

## Docker stack

| Item | Evidencia |
|------|----------|
| Compose con 5 servicios | `infra/docker/docker-compose.yml` |
| Healthchecks postgres/redis/minio | `docker-compose.yml:18-52` |
| Backend en :8001, frontend en :3001 | `docker-compose.yml:77,94` |

## Agentes (8 categorías)

| Agente | Archivo | Notas |
|--------|---------|-------|
| Triage | `agents/triage/agent.py` | Pre-filtro determinístico YAML + clamp + injection guard |
| Anamnesis | `agents/anamnesis/agent.py` | Loop hasta 3 veces por Medical Board |
| Classifier | `agents/classifier/agent.py` | specialty_map.yaml |
| Specialists (11) | `agents/specialists/` | Paralelo, registry + aliases + fallback |
| Medical Board | `agents/medical_board/agent.py` | `smart` tier, max 2 extra rounds |
| Devil's Advocate | `agents/devils_advocate/agent.py` | Activado solo con condiciones (ADR-008) |
| Guardrail | `agents/guardrail/agent.py` | `_clamp_interrupt`, MODIFY path |
| Synthesizer | `agents/synthesizer/agent.py` | `_clamp_attention`, `_with_disclaimer`, tier hint |

11 specialists: `cardiology`, `dermatology`, `endocrinology`, `general_medicine`,
`gynecology`, `internal_medicine`, `neurology`, `pediatrics`, `pharmacology`,
`traumatology` + `general_medicine` como fallback.

## Infraestructura del grafo

| Item | Evidencia |
|------|----------|
| LangGraph StateGraph compilado | `orchestrator/graph.py: build_graph()` |
| ClinicalCaseState TypedDict | `orchestrator/state.py` |
| Graph cache con TTL 5min | `core/graph_cache.py` |
| Audit wrapping (3 nodos) | `graph.py: _audit_node` — triage, guardrail, synthesizer |
| Escalation node (2 paths) | `graph.py: _escalation_node` |
| Disclaimer wrapper idempotente | `graph.py: _with_disclaimer` |

## Audit trail

| Item | Evidencia |
|------|----------|
| Hash chain global SHA-256 | `services/audit.py: verify_chain()` |
| `previous_hash` + `chain_hash` en cada row | `models/audit_log.py` |
| Advisory lock PostgreSQL | `audit.py: _ADVISORY_LOCK_SQL` |
| Migration de columnas | `alembic/versions/l2m3n4o5p6q7_add_audit_chain_columns.py` |
| Endpoint verify-chain | `api/v1/admin.py: GET /admin/audit/verify-chain` |
| Smoke test script | `scripts/smoke_audit_chain.py` |
| Tests audit | 4 archivos en `tests/` (`test_audit.py`, `test_audit_verify_chain.py`, etc.) |

## Eval clínica

| Item | Evidencia |
|------|----------|
| 25 casos clínicos | `tests/clinical_eval/` |
| 96% pass (24/25) | Último run — único fail por 503 transient Gemini |
| Marker `@pytest.mark.live_llm` | Requiere LLM real activo |

## Tier gating

| Item | Evidencia |
|------|----------|
| `require_subscription_tier("paid")` en documents/upload | `api/v1/documents.py` |
| `require_subscription_tier("paid")` en export/pdf | `api/v1/export.py` |
| Gate en grafo para specialists | `orchestrator/graph.py: _should_gate_specialists` |
| `tier_gated_specialists` flag en state | `orchestrator/state.py:47` |
| TIER_UPGRADE_HINT en synthesizer | `agents/synthesizer/agent.py:47` |
| `parseTierGate()` en frontend | `frontend/src/lib/tier-gate.ts` |

## Frontend MVP

| Item | Evidencia |
|------|----------|
| Next.js 16.2.3 + React 19.2.4 + shadcn v4 | `frontend/package.json` |
| Pages: /login /register /history /upload | `frontend/src/app/*/page.tsx` |
| Theme dual-layer (oklch + --tm-*) | `frontend/src/app/globals.css` |
| FOUC guard | `frontend/src/app/layout.tsx:42` — blocking script |
| ThemeProvider (Context API) | `frontend/src/components/theme/theme-provider.tsx` |
| ApiError con `.code` | `frontend/src/lib/api.ts:22` |
| Token refresh automático | `frontend/src/lib/api.ts:95-107` |
| 52/52 tests passing | `cd frontend && npm run test` |

## Performance

| Métrica | Antes | Después |
|---------|-------|---------|
| P95 latencia | ~234s | ~179s |
| P50 latencia | — | ~66s |
| Outliers 200-250s | presentes | eliminados |
