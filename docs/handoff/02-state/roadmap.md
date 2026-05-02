# Roadmap — Dónde estamos

Estado del proyecto al **2026-05-01**. Última auditoría de código confirmó
los ítems marcados como ✅. Los ❌ no tienen una sola línea de código en `app/`.

## Resumen ejecutivo

| Área | Estado |
|------|--------|
| Core backend (auth, chat, agentes, audit) | ✅ completo |
| Frontend MVP (login, register, history, upload) | ✅ funcional |
| Tier gating real (2 endpoints + grafo) | ✅ en producción |
| Multi-agente deliberativo (Mesa, Devil's Advocate, Guardrail) | ✅ en producción |
| Eval clínica 25 casos | ✅ 96% pass |
| Stripe / billing | ❌ sin implementar |
| Email verify / password reset | ❌ sin implementar |
| Observabilidad (Prometheus, OTel) | ❌ sin implementar |
| KB con fuentes reales | ❌ sin contenido |
| Refresh token denylist | ❌ sin implementar |

## Fases del roadmap

### Fase 1 — Core foundation ✅
Auth + JWT + RBAC, Docker stack, modelos de DB, migrations.

### Fase 2 — Agentes core ✅
Triage + Anamnesis + Classifier + Synthesizer. Grafo LangGraph básico.

### Fase 2.5 — Documentos + LLM vault ✅
Upload de documentos, AES-256-GCM vault, LLM Router multi-provider.

### Fase 3 — Mesa de Especialistas ✅
11 specialist agents, Medical Board, Devil's Advocate, Guardrail.
Eval clínica 25 casos.

### Fase 3.5 — Hardening + performance ✅
Prompt injection guard, output sanitization, security headers, audit chain,
tier gating real, QW3 latency optimization (P95 234s → 179s).

### Fase 4 — Frontend MVP ✅
Next.js 16 + React 19 + shadcn v4. Login, register, history, upload.
52/52 tests. Theme dual-layer. ApiError parser.

### Fase 5 — Billing + Email ❌ PENDIENTE
Stripe checkout, webhook, actualización de `subscription_tier`.
Email verification, password reset.

### Fase 6 — KB con fuentes reales ❌ PENDIENTE
Loaders PubMed/WHO/LiverTox en `app/services/kb_sources/`.
RAG re-ranking + citations en respuestas.

### Fase 7 — Observabilidad + escala ❌ PENDIENTE
Prometheus metrics, OpenTelemetry traces, correlation IDs.
Multi-replica rate limit (Redis en vez de slowapi in-process).

## Próximos ítems prioritarios

1. **Stripe billing** — desbloquea revenue. Sin esto, el tier model es cosmético.
2. **Email verify** — baseline de seguridad (cuentas sin verificar pueden usarse).
3. **`/cases/[id]` funcional** — el frontend tiene el scaffold, falta el contenido real.
4. **Sidebar con lista de casos** — navegación básica faltante en layout.
5. **KB content** — el indexer existe, las fuentes no. Sin contenido el RAG es vacío.

Ver [`done.md`](./done.md) para evidencia de lo completado y
[`pending.md`](./pending.md) para detalles de lo pendiente.
