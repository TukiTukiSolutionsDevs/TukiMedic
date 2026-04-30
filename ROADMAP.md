# Tuki-Medic / MedAgent — Roadmap

> Última actualización: 2026-04-30
> Estado del proyecto: **BETA-READY** — Sprints de hardening de producción completados

## Resumen ejecutivo

| Capa | Tests | Estado |
|------|------:|:-----:|
| Backend | 469 passed (+ 3 live_llm opt-in) | ✅ |
| Frontend | TS strict + tsc --noEmit limpio | ✅ |
| Docker | Backend + Frontend Dockerfiles | ✅ |
| CI | GitHub Actions (lint + test + build) | ✅ |
| Pre-commit | ruff + black + eslint | ✅ |

---

## Fases del producto (Sprint 0 — entregadas previo a este ciclo)

| Fase | Estado | Detalle |
|------|--------|---------|
| 0. Setup | ✅ | Monorepo, Next 16, FastAPI, Postgres+pgvector, Redis, MinIO |
| 1. Core (chat + agentes) | ✅ | LangGraph multi-agente, 9 agentes, dispatch paralelo |
| 2. Documentos | ✅ | OCR + clasificación + extracción de labs + integración chat |
| 3. Especialidades | ✅ | Pediatría, Ginecología, Med Interna, Farmacología, plugin system |
| 4. Memoria + KB | ✅ | 3 niveles (Redis L1, pg_facts L2, timeline+KB L3) |
| 5. Dashboard + Admin | ✅ | Métricas, audit log API, KB CRUD, PDF export |

---

## Sprints de hardening (este ciclo)

### Sprint 1 — Tier 1 blockers ✅
**Objetivo**: eliminar los 12 ítems CRITICAL que bloqueaban beta.

| ID | Item | Status |
|----|------|--------|
| A.1 | Disclaimer concatenado al patient_response | ✅ |
| A.2 | Severity "modify" del guardrail reescribe la respuesta | ✅ |
| A.3 | Red flags robustos contra negaciones y tildes | ✅ |
| A.4 | Audit trail clínico (`log_clinical_decision` + wrapper en graph) | ✅ |
| A.5 | Frame `done` post-guardrail (no más leak pre-validación) | ✅ |
| B.1 | SECRET_KEY validator | ✅ |
| B.2 | Rate limit /auth/* | ✅ |
| B.3 | python-jose → PyJWT (CVE-2024-33663, 33664) | ✅ |
| B.4 | Login frontend completo | ✅ |
| C.1 | `await db.delete()` | ✅ |
| C.2 | PDF export filtra por case_id | ✅ |
| C.3 | safe_ainvoke wrapper en 9 agentes | ✅ |
| C.4 | ivfflat indexes pgvector + ix_cases_user_id | ✅ |

### Sprint 2 — Tier 2 hardening ✅
**Objetivo**: cerrar gaps de seguridad, datos y tests para beta defendible.

| ID | Item | Status |
|----|------|--------|
| T2.1 | Auth persist + refresh tokens (zustand persist) | ✅ |
| T2.2 | Route guards (`src/proxy.ts` — Next 16) | ✅ |
| T2.3 | WebSocket case_id ownership validation | ✅ |
| T2.6 | Tests para `core/dependencies.py` (auth guard) | ✅ |
| T2.7 | Marker `@live_llm` opt-in para tests con LLM real | ✅ |
| T2.8 | Fix smoke fake `test_synthesizer.py:200` | ✅ |
| T2.10 | Security headers en `next.config.ts` (CSP, HSTS, etc) | ✅ |
| T2.11 | Cliente HTTP centralizado `src/lib/api.ts` con refresh | ✅ |
| T2.12 | OCR timeout + MAX_PDF_PAGES | ✅ |
| T2.13 | `sanitize_filename()` en upload | ✅ |
| T2.14 | DELETE /api/v1/auth/me — GDPR right-to-erasure | ✅ |

### Sprint 3 — Tier 3 infra ✅
**Objetivo**: stack deployable a producción.

| ID | Item | Status |
|----|------|--------|
| T3.1 | Dockerfiles producción (backend + frontend) | ✅ |
| T3.1 | docker-compose.yml production-style con healthchecks | ✅ |
| T3.2 | GitHub Actions CI (lint + test + docker build) | ✅ |
| T3.3 | Pre-commit hooks (ruff + black + eslint) | ✅ |
| T3.4 | chat.py no echoea str(exc) al cliente | ✅ |
| T3.5 | `BackgroundTasks` reemplaza `asyncio.create_task` orphan | ✅ |
| T3.7 | Quitado duplicado `is_admin` en user.py | ✅ |
| T3.9 | `/health/ready` con probes reales (PG, Redis, S3) | ✅ |
| T3.10 | Logs estructurados JSON en prod/staging | ✅ |
| T3.6 | LOOP_CONFIG dead fields | ⏭️ skip (cosmético, tests asertan valores) |
| T3.8 | lucide-react version | ⏭️ N/A (1.8.0 sí existe; auditor desactualizado) |

---

## Sprint 4 — backlog post-beta

Tracked para después del primer rollout:

1. **Meridian shim structured-output** — el shim no traduce function-calling de OpenAI a tool_use de Anthropic. Production risk si se usa este proxy. Decisión: validar con OpenAI/Anthropic directos O cambiar agentes a `method='json_mode'`.
2. **Integración con DB real** — toda la suite mockea AsyncSession; vale 1 sprint con testcontainers.
3. **Live LLM eval suite** — dataset de red flags y prompts de guardrail con `--live-llm`.
4. **Frontend testing** — vitest + React Testing Library no configurados.
5. **httpOnly refresh cookie** — hoy refresh token está en localStorage (XSS surface).
6. **Observabilidad** — Prometheus metrics, OpenTelemetry tracing, alertas on-call para `escalation` real.
7. **Hash-chain audit log** — append-only / inmutabilidad criptográfica.
8. **Documentación legal** — política de retención + GDPR / Ley 25.326 / HIPAA disclaimers versionados.

---

## Cómo correr el stack

### Dev local
```bash
# 1. Datastores
docker compose -f infra/docker/docker-compose.dev.yml up -d

# 2. Backend
cd backend && poetry install && poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload

# 3. Frontend
cd frontend && npm install && npm run dev
```

### Producción
```bash
# Build + run del stack completo
docker compose -f infra/docker/docker-compose.yml up --build
```

### Tests
```bash
cd backend
poetry run pytest -q                 # 469 mockeados
poetry run pytest --live-llm         # +3 con LLM real (Meridian shim por default)
```

### Pre-commit
```bash
pipx install pre-commit && pre-commit install
pre-commit run --all-files           # one-off run
```

---

## Métricas de calidad declaradas

| Métrica | Target | Estado actual |
|---------|--------|---------------|
| Triage accuracy vs eval manual | >90% | ⏳ pendiente eval suite |
| Coherencia multi-agente | <5% contradicciones | ⏳ pendiente live_llm dataset |
| Completitud de anamnesis | >80% datos relevantes | ⏳ pendiente |
| Red flags detectadas | 100% | ✅ regex + negaciones (Sprint 1 A.3) |
| Latencia respuesta sintetizada | <15s | ⏳ pendiente medir en stack real |
| Cobertura de tests críticos | auth/security/dependencies/audit | ✅ 100% |
