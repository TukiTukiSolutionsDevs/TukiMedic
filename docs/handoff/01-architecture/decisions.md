# Decisiones Arquitectónicas (ADRs)

Registro de decisiones no triviales. Cada entrada incluye qué se decidió,
por qué, y qué alternativas se descartaron. No repetir estas discusiones
sin leer esto primero.

---

## ADR-001: Extender scaffold Next.js 16, no migrar a Vite

**Decisión**: extender el scaffold existente de Next.js 16.2.3. No migrar a
Vite, no reemplazar con SPA standalone.

**Contexto**: el equipo evaluó empezar desde cero con Vite + React para
mayor control. El prototipo en `~/Downloads/TukiMedicfront/tukimedic.html`
es referencia visual, no código portable.

**Razones**:
- App Router de Next.js provee SSR/SSG + file-based routing sin configuración.
- API routes de Next.js servirán como BFF en el futuro.
- shadcn v4 está optimizado para Next.js App Router.
- Migrar introduce riesgo con cero ganancia en el estado actual del proyecto.

**Consecuencia**: el frontend vive en `frontend/` con Next.js convenciones.
`next build` SOLO dentro de Docker — no correr standalone en dev.

---

## ADR-002: Theme dual-token (shadcn oklch + TM hex)

**Decisión**: mantener dos familias de design tokens en `globals.css`:
tokens shadcn (`--background`, `--foreground`, etc. en `oklch`) y tokens
`--tm-*` (`--tm-primary`, `--tm-surface`, etc. en `hex`).

**Razones**:
- shadcn v4 usa oklch y espera sus tokens para funcionar correctamente.
- El prototipo usa una paleta específica en hex que debe preservarse.
- Forzar una sola familia hubiera requerido reescribir todos los componentes
  shadcn o todo el diseño custom.

**Regla derivada**: dark mode con clase `.dark` en `<html>`. NO `[data-theme]`
— shadcn v4 no lo soporta y rompe todos los componentes.

---

## ADR-003: ThemeProvider con Context API, no zustand

**Decisión**: el ThemeProvider usa React Context API puro. No usa zustand.

**Razones**:
- El estado de theme es trivial (string: "light"/"dark"/"system").
- Zustand para estado UI simple es over-engineering.
- Context API con `localStorage` es el patrón estándar de next-themes.

**FOUC guard**: blocking inline script en `<head>` que lee
`localStorage["tm-theme"]` y aplica `.dark` antes del primer paint.
`suppressHydrationWarning` en `<html>` silencia el mismatch esperado SSR/CSR.

---

## ADR-004: Instrument_Serif NO es variable font

**Decisión**: cargar `Instrument_Serif` con `weight: "400"` y
`style: ["normal", "italic"]` explícitos.

**Razones**: Instrument Serif no tiene variable font axis. Si se omite
`weight`, Next.js lanza error en build. Si se omite `style`, el italic
no se carga y cae al synthetic italic del browser.

**Regla**: NO copiar el patrón de Geist (que sí es variable) para esta fuente.

---

## ADR-005: Backend — Screaming Architecture, no Hexagonal pura

**Decisión**: Screaming Architecture con vertical slices pragmáticas.
Sin puertos/adaptadores, sin capa de repositorio explícita.

**Razones**:
- El equipo es pequeño. Hexagonal agrega capas de indirección que no aportan
  valor sin un equipo de 5+ desarrolladores.
- FastAPI Depends hace DI de forma nativa y limpia.
- SQLAlchemy con async ya provee suficiente abstracción sobre la DB.

**Consecuencia**: los servicios acceden directamente a `AsyncSession`.
No hay `UserRepository` — las queries SQLAlchemy viven en los servicios y
en los endpoints. Esto es intencional.

---

## ADR-006: Audit trail con hash chain global

**Decisión**: implementar un hash chain global (no por case, no por user)
en `audit_logs` con `previous_hash` + `chain_hash` (SHA-256).

**Razones**:
- Defensibilidad legal: cualquier reordenamiento o eliminación de rows es
  detectable end-to-end.
- Un lock PostgreSQL por transacción (`pg_advisory_xact_lock`) garantiza
  que el SELECT-prev / INSERT-chained es atómico.
- Chain global (no per-case) hace más difícil falsificar un subconjunto de rows.

**Consecuencia**: `audit_session` usa NullPool para evitar el
`asyncpg InterfaceError` cuando LangGraph interleaves coroutines sobre el
mismo event loop. `_write_audit` corre como `asyncio.ensure_future` task.

**Migration**: `alembic/versions/l2m3n4o5p6q7_add_audit_chain_columns.py`

---

## ADR-007: LLM credentials en vault AES-256-GCM, no env vars

**Decisión**: las API keys de LLM se almacenan cifradas en Postgres
(AES-256-GCM), no en variables de entorno. El LLM Router descifra en
tiempo de ejecución.

**Razones**:
- Multi-provider: el admin puede rotar credenciales sin reiniciar el servicio.
- Single-active credential: solo una credencial activa por proveedor,
  gestionada desde el panel admin.
- Seguridad: las keys no aparecen en `env` del proceso ni en logs.

**Limitación**: `OPENAI_API_BASE` todavía se propaga a `os.environ` para
servicios de embedding que no fueron migrados al vault.

---

## ADR-008: Redis L1 memory — efímera, sin persistencia en DB

**Decisión**: el historial de mensajes del turno se guarda solo en Redis
(RPUSH + LTRIM), no en Postgres.

**Razones**:
- Latencia: Redis es O(1) para RPUSH/LRANGE.
- Los mensajes intermedios (dentro de un turn) no necesitan persistencia a largo plazo.
- La timeline de L3 (en Postgres) captura los eventos clínicos relevantes.

**Consecuencia conocida**: si Redis se flushea, el historial del turno se pierde.
Los mensajes NO se recuperan de ningún otro lado. Es un trade-off aceptado.

---

## ADR-009: Grafo LangGraph en graph_cache — in-memory, sin distributed cache

**Decisión**: el grafo compilado se cachea in-memory por worker (asyncio.Lock
+ TTL 5 min), no en Redis ni en ningún distributed cache.

**Razones**:
- El grafo es un objeto Python no serializable fácilmente.
- TTL 5 min es suficiente para amortizar el costo de compilación.

**Limitación**: en multi-worker (Gunicorn), la rotación de credenciales LLM
no se propaga a todos los workers inmediatamente. Cada worker espera a que
su TTL expire. Documentado en [`../02-state/known-gotchas.md`](../02-state/known-gotchas.md).
