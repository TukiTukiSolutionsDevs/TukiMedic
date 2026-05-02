# Pendientes reales

Todo lo listado acá está **verificado como ausente** en el código al
2026-05-01. No hay imports, no hay endpoints, no hay migraciones.

## ❌ Stripe billing

**Estado**: cero líneas de Stripe en `app/`. El `subscription_tier` se
asigna manualmente en DB hoy.

**Qué implica implementar**:
- Producto + precios en Stripe dashboard.
- Checkout session endpoint (`POST /api/v1/billing/checkout`).
- Webhook endpoint (`POST /api/v1/billing/webhook`) que actualiza
  `user.subscription_tier` al recibir `checkout.session.completed`.
- Frontend: botón "Upgrade" → checkout URL → redirect de vuelta.
- Migration: posiblemente tabla `subscriptions` con Stripe IDs.

**Bloqueante para**: todo el tier model es cosmético sin esto.

---

## ❌ Email verification + password reset

**Estado**: `user.is_verified` existe en el modelo pero siempre es `False`.
No hay endpoints `/auth/verify-email` ni `/auth/forgot-password`.

**Qué implica**:
- Email sending service (SendGrid, Resend, SES).
- Tabla o Redis cache para tokens temporales.
- Endpoints: `POST /auth/verify-email`, `POST /auth/forgot-password`,
  `POST /auth/reset-password`.
- Frontend: páginas `/verify-email` y `/reset-password`.

---

## ❌ Refresh token rotation + denylist

**Estado**: `POST /auth/refresh` emite nuevos tokens pero no invalida el
refresh token anterior. Un refresh token robado puede usarse indefinidamente.

**Gotcha adicional** (`auth.py:147`): el nuevo `access_token` emitido por
`/auth/refresh` NO incluye `role` ni `subscription_tier` en el payload. Hoy
es seguro porque `get_current_user` re-fetchea la DB, pero es inconsistente
con el login que sí los incluye.

**Qué implica**:
- Tabla `refresh_token_denylist` o set Redis `rt:denylist:{jti}`.
- Al rotar, invalidar el token anterior (insertar en denylist).
- `get_current_user` y `/auth/refresh` verifican que el refresh token
  no esté en denylist.
- Cleanup job para tokens expirados.

---

## ❌ Observabilidad: Prometheus + OTel + correlation IDs

**Estado**: cero imports de `prometheus_client`, `opentelemetry`, ni
`structlog` correlation IDs en `app/`.

**Qué implica**:
- `PrometheusMiddleware` (o Starlette Prometheus) para métricas HTTP.
- OTel SDK con exporter (Jaeger/Zipkin/OTLP) para traces distribuidos.
- Correlation ID middleware: genera `X-Request-ID` y lo propaga en logs.
- Dashboard Grafana/Prometheus básico.

---

## ❌ KB content: loaders PubMed/WHO/LiverTox

**Estado**: `app/services/kb_sources/` está vacío. El indexer `run_indexer()`
existe y funciona (bug previo de KB arreglado), pero no tiene fuentes que
procesar.

**Qué implica**:
- Loader PubMed (E-utilities API o bulk download).
- Loader WHO ICD-10/guidelines (PDF o XML).
- Loader LiverTox (base de datos de hepatotoxicidad).
- Chunking + embedding + upsert en pgvector.
- Programación de re-indexado (cron o endpoint admin).

**Consecuencia actual**: `state["kb_context"]` siempre llega vacío al grafo.
El RAG no aporta conocimiento médico.

---

## ❌ RAG re-ranking + citations

Depende del KB content. Sin fuentes cargadas no hay nada que re-rankear.
Las citas en respuestas (`[Fuente: ...]`) están planeadas pero no implementadas.

---

## 🟡 Tier gating: amplitud insuficiente

Solo 2 endpoints están gateados hoy (`documents/upload` y `export/pdf`).
La decisión de qué más gatear está pendiente de definir con producto.

---

## 🟡 Frontend pendiente

| Item | Estado |
|------|--------|
| `/cases/[id]` funcional | Scaffold presente, sin datos reales |
| Sidebar con lista de casos | HTML en layout, sin datos |
| Loading states + error boundaries | Parcialmente implementados |
| Mobile / responsive | No auditado |
| i18n | No planificado |

---

## 🔲 Multi-replica rate limit

`slowapi` usa in-memory store. En multi-worker (Gunicorn con N workers),
cada worker tiene su propio contador → un usuario puede enviar N × 10
requests/minuto antes de ser limitado.

**Fix**: migrar a `slowapi` con Redis backend, o usar `fastapi-limiter`
con Redis.

---

## 🔲 Security / Load / Chaos tests

No hay tests de:
- Penetration testing automatizado.
- Load testing (k6, Locust).
- Chaos engineering (fallas de Redis, DB, LLM provider).

El harness de eval clínica cubre funcionalidad pero no resiliencia.
