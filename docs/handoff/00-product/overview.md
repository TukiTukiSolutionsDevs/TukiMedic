# Tuki-Medic — Overview del Producto

Tuki-Medic es una plataforma SaaS de análisis clínico conversacional. Los
pacientes describen sus síntomas via chat; el sistema ejecuta un grafo
multi-agente que analiza el caso, consulta especialistas virtuales, somete el
output a debate médico y a un filtro de seguridad, y devuelve una respuesta
clínica consolidada con disclaimer.

## Tabla de contenidos

1. [Propósito](#propósito)
2. [Actores](#actores)
3. [Flujo de valor](#flujo-de-valor)
4. [Límites del sistema](#límites-del-sistema)
5. [Métricas de referencia](#métricas-de-referencia)

## Propósito

Proveer orientación clínica personalizada de alta calidad a usuarios que no
tienen acceso inmediato a un médico. El sistema **no reemplaza** la consulta
médica — lo declara explícitamente en cada respuesta.

Diferenciadores:
- **Multi-agente deliberativo**: 8 categorías de agentes, 11 especialidades
  implementadas, debate estructurado antes de sintetizar.
- **Seguridad como ciudadano de primera clase**: sin respuesta sin disclaimer,
  sin diagnóstico definitivo, sin prescripción con dosis.
- **Tier model real**: free vs paid con enforcement en backend
  (`require_subscription_tier`) y en frontend (`TierUpgradeBanner`).

## Actores

| Actor | Rol | Acceso |
|-------|-----|--------|
| Paciente (`customer`) | Chat, upload documentos, historial | Free o paid |
| Admin | Credenciales LLM, gestión de usuarios, audit | Panel RBAC |
| Sistema | Orquestación, audit trail, rate limiting | Interno |

## Flujo de valor

```
Paciente escribe síntomas
  → WebSocket /api/v1/chat/ws
  → Grafo LangGraph
      Triage → [Anamnesis] → Classifier → Specialists (paralelo)
      → Medical Board → [Devil's Advocate] → Synthesizer → Guardrail
  → Respuesta consolidada con disclaimer
  → Memoria persistida (Redis L1 + Postgres L2/L3)
```

Ver [`clinical-flow.md`](./clinical-flow.md) para el grafo detallado con
condiciones de ruteo.

## Límites del sistema

- **No diagnostica definitivamente**: el Guardrail bloquea `definitive_diagnosis_unsafe`.
- **No prescribe**: `prescription_with_dose` es violation crítica.
- **No atiende emergencias**: casos `red` redirigen a urgencias inmediatamente.
- **No reemplaza al médico**: `BASE_DISCLAIMER` hardcodeado en cada respuesta
  (`backend/app/agents/synthesizer/agent.py`).

## Métricas de referencia (2026-05-01)

| Métrica | Valor |
|---------|-------|
| Eval clínica (25 casos) | 96% pass (24/25) |
| P50 latencia | ~66s |
| P95 latencia | ~179s (era 234s pre-optimización) |
| Tests backend | 82 archivos, ~132 tests |
| Tests frontend | 52/52 passing |
| Specialists implementados | 11 |
