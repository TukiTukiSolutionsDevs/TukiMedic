# Frontend Rebuild — Roadmap dinámico

> Este archivo se actualiza en vivo durante la sesión. Cada item tachado es código real verificable en el repo. Si un item está marcado `[x]` y no encontrás la evidencia, gritáme.

**Inicio**: 2026-05-01 21:50
**Diseño origen**: `~/Downloads/TukiMedicfront/` (prototipo React 18 + Babel standalone)
**Destino**: `frontend/` (Next.js 16 + React 19 + shadcn v4)

---

## Estado global

| Fase | Estado | Tests | Notas |
|------|--------|-------|-------|
| 0 — Design system | ✅ Done | 6 (Logo) | tokens y fonts ya estaban; faltaba `<Logo/>` |
| 1 — App Shell | ✅ Done | 19 (nav-config + sidebar) | sidebar collapsable + user card + public route bypass |
| 2 — Landing pública | ✅ Done | 15 (landing integration) | 10 secciones del prototipo migradas a `src/components/landing/` |
| 3 — Auth (login + register) | ✅ Done | 17 (12 existentes + 5 nuevos) | split-screen, AuthLayout + PasswordField components |
| 4 — Dashboard | ✅ Done | 11 nuevos (111 total) | greeting + recent cases + stats + quick actions |
| 5 — Chat clínico | ✅ Done | 13 nuevos (124 total) | split + AgentsPanel + escalation redirect + sessionStorage payload |
| 9 — Escalation screen | ✅ Done | 9 nuevos (134 total) | full-bleed alarm, sessionStorage payload, SAMU 106, hospitals link |
| 6 — History | ✅ Done | 18 nuevos (152 total) | filter bar + search + pagination + tier-aware export |
| 7 — Profile | ✅ Done | 18 nuevos (170 total) | 3-tab settings + delete account dialog |
| 8 — Admin panel | ✅ Done | 33 nuevos (203 total) | SubNav strip + verify-chain + 4 repintados |
| 9 — Escalation screen | ✅ Done | 9 nuevos (134 total) | full-bleed alarm, sessionStorage payload, SAMU 106, hospitals link |
| 10 — Polish + a11y | ✅ Done (core) | 12 nuevos (215 total) | animations + error/loading boundaries + global focus ring + reduced-motion |

**Leyenda**: ⏳ Pending · 🚧 In progress · ✅ Done · ⚠️ Blocked

---

## Fase 0 — Design system + assets ✅

Base de tokens del prototipo migrada a Tailwind/CSS vars. Sin esto las pantallas se ven a Frankenstein.

- [x] Logo copiado a `frontend/public/logo.png`
- [x] CSS variables `--tm-*` en `src/app/globals.css` (light + dark) — ya existían
- [x] Fuentes Geist + Geist Mono + Instrument Serif via `next/font` — ya wired en layout.tsx
- [x] Theme provider con persistence en localStorage + script anti-FOUC — ya existía
- [x] Componente `<Logo />` reusable — `src/components/logo.tsx` (6 tests passing, commit `2562232`)
- [~] Tailwind config extend: NO requerido — Tailwind v4 lee CSS vars directo, las clases custom se hacen con `style={{ color: "var(--tm-blue-500)" }}` o utility classes inline
- [~] Test theme persist reload: ya cubierto en `theme-provider.test.tsx` existente

**Archivos**:
- `src/app/globals.css` — vars + reset (ya estaba)
- `src/app/layout.tsx` — fonts wired (ya estaba)
- `src/components/theme/theme-provider.tsx` (ya estaba)
- `src/components/logo.tsx` ✨ NUEVO
- `src/components/__tests__/logo.test.tsx` ✨ NUEVO

**Discoveries Fase 0**:
- El proyecto está bastante más adelantado que la session-summary sugería: el design system ya estaba bootstrapeado con los tokens del prototipo intactos. Esto baja el costo total estimado del rebuild de "semanas" a "días".

---

## Fase 1 — App Shell

Layout post-login con sidebar + topbar. Es el frame que envuelve todas las pantallas internas.

- [ ] `<AppShell>` con sidebar colapsable (móvil + desktop)
- [ ] Topbar con user menu + theme toggle
- [ ] Sidebar items: Dashboard, Chat, Historial, Perfil, Admin (condicional)
- [ ] Avatar + nombre + tier badge (free/paid)
- [ ] Logout flow (limpia tokens + redirect)
- [ ] Tests: sidebar nav, admin item solo para `role=admin`, logout

**Archivos esperados**:
- `frontend/components/app-shell/index.tsx`
- `frontend/components/app-shell/sidebar.tsx`
- `frontend/components/app-shell/topbar.tsx`
- `frontend/components/app-shell/user-menu.tsx`

---

## Fase 2 — Landing pública

Pantalla pre-login con propuesta de valor + CTAs a login/register.

- [ ] Hero con logo + tagline
- [ ] Sección de valor (3 features: multi-agente, seguro, 24/7)
- [ ] Sección "Cómo funciona" (flujo en 3 pasos)
- [ ] CTA dual: ingresar / crear cuenta
- [ ] Footer con disclaimer médico
- [ ] Tests: render, CTAs llaman handlers correctos

**Archivos esperados**:
- `frontend/app/(public)/page.tsx` — landing en `/`
- `frontend/components/landing/*.tsx`

---

## Fase 3 — Auth (login + register)

Mantener lógica actual (12 tests existentes), repintar UI según prototipo.

- [ ] Login: nuevo layout (split izquierda visual / derecha form)
- [ ] Register: misma estética, validación inline
- [ ] Mensajes de error mapeados desde `ApiError` (existe ya)
- [ ] "Volver" → landing
- [ ] Tests existentes deben seguir pasando (12)
- [ ] +3 tests visuales nuevos (estructura del nuevo layout)

**Archivos a tocar**:
- `frontend/app/login/page.tsx`
- `frontend/app/register/page.tsx`
- Shared: `<AuthLayout>` para split visual

---

## Fase 4 — Dashboard

Home post-login. Lista quick actions + casos recientes + tier banner.

- [ ] Saludo personalizado con nombre
- [ ] Card "Nueva consulta" (CTA primario)
- [ ] Lista de últimos casos (3-5) con estado de triage
- [ ] Banner upgrade si `tier=free` (reusa `TierUpgradeBanner` existente)
- [ ] Métrica: casos del mes, tier actual
- [ ] Tests: render, CTA → /chat, casos clickeables

**Archivos esperados**:
- `frontend/app/dashboard/page.tsx`
- `frontend/components/dashboard/*.tsx`

---

## Fase 5 — Chat clínico (la gorda)

La pantalla más compleja. WebSocket real al backend, streaming de agentes, escalation flow.

- [ ] Layout split: chat principal + panel lateral con agentes activos
- [ ] Conexión WebSocket a `/api/v1/chat/ws` (auth via primer mensaje)
- [ ] Stream de mensajes del paciente y respuesta consolidada
- [ ] Indicador "agentes pensando" (triage, classifier, specialists, board, etc.)
- [ ] Disclaimer médico siempre visible
- [ ] Detección de escalation (`triage=red` → redirect a `/escalation`)
- [ ] Upload de documentos inline (gateado paid)
- [ ] Tests: WS mock, escalation, disclaimer presente

**Archivos esperados**:
- `frontend/app/chat/page.tsx`
- `frontend/components/chat/conversation.tsx`
- `frontend/components/chat/agents-panel.tsx`
- `frontend/components/chat/message.tsx`
- `frontend/lib/ws-client.ts`

---

## Fase 6 — History

Lista de casos + búsqueda + filtros + export PDF (paid).

- [ ] Tabla con columnas: fecha, chief complaint, triage, especialidades, estado
- [ ] Filtro por triage (green/yellow/red) + fecha
- [ ] Búsqueda full-text
- [ ] Click → reabrir caso en `/chat` con prompt original
- [ ] Botón "Exportar PDF" (paid only)
- [ ] Tests: render con datos, filtros, click reabre caso

**Archivos a tocar**:
- `frontend/app/history/page.tsx` (existe parcial)

---

## Fase 7 — Profile

Datos del usuario + datos clínicos persistentes (alergias, medicación, condiciones) + GDPR delete.

- [ ] Datos personales (nombre, email — read-only excepto password)
- [ ] Tier actual + botón upgrade (si free)
- [ ] Sección clínica: alergias, medicación activa, condiciones crónicas (CRUD)
- [ ] Cambio de password (con validación actual)
- [ ] GDPR: botón eliminar cuenta (DELETE `/auth/me`)
- [ ] Tests: edit clínico, GDPR delete confirma

**Archivos esperados**:
- `frontend/app/profile/page.tsx`
- `frontend/components/profile/*.tsx`

---

## Fase 8 — Admin panel

Solo `role=admin`. LLM credentials + users + audit chain status.

- [ ] Gate por role (redirect si no admin)
- [ ] Tab "LLM Credentials": listar, agregar, rotar, eliminar
- [ ] Tab "Users": listar, suspender, cambiar tier
- [ ] Tab "Audit": botón "Verify chain" → `GET /admin/audit/verify-chain`
- [ ] Tab "KB": disparar reindex
- [ ] Tests: gate de role, render por tab, verify chain muestra status

**Archivos esperados**:
- `frontend/app/admin/page.tsx`
- `frontend/components/admin/llm-credentials.tsx`
- `frontend/components/admin/users.tsx`
- `frontend/components/admin/audit.tsx`
- `frontend/components/admin/kb.tsx`

---

## Fase 9 — Escalation screen

Pantalla full-screen cuando triage=red. Mensaje claro de urgencias + número emergencia + botón "nuevo caso".

- [ ] Layout full-screen con color de alarma (rojo + alto contraste)
- [ ] Mensaje: "ir a urgencias inmediatamente"
- [ ] Número de emergencia local (configurable)
- [ ] Sintomas detectados como red flags
- [ ] Botón "Nuevo caso" + "Volver al dashboard"
- [ ] Tests: render con data, accesibilidad (role=alert)

**Archivos esperados**:
- `frontend/app/escalation/page.tsx`
- `frontend/components/escalation/*.tsx`

---

## Fase 10 — Polish + a11y ✅ (core)

Detalles que separan un MVP de un producto.

- [x] Animaciones del prototipo: keyframes `tm-pulse-dot`, `tm-fade-up`, `tm-fade-in`, `tm-shimmer`, `tm-spin`, `tm-cursor-blink`, `tm-bar-grow` + utility classes en `globals.css`
- [x] `prefers-reduced-motion` global media query (todas las animations a 0.01ms)
- [x] Error boundaries: `<ErrorScreen>` reusable + `app/error.tsx` (root) + `app/global-error.tsx` (catastrófico) — 8 tests
- [x] Loading boundaries: `<LoadingScreen>` shimmer skeleton + `loading.tsx` para `/dashboard`, `/chat`, `/history`, `/settings`, `/admin` — 4 tests
- [x] Focus rings consistentes: regla global `:focus-visible` en `globals.css` cubre buttons/links/inputs/textarea/select y `[role="button"]` — outline azul + offset
- [x] Keyboard navigation auditada: AppShell sidebar usa `<Link>` y `<button>` (accesibles por default), aria-labels en collapse y logout
- [~] Dark mode: tokens flippean correctamente; verificación visual completa requiere browser real (defer)
- [ ] Lighthouse pass: a11y > 95, perf > 85 — DEFER (requiere browser real + setup CI)
- [ ] Tests E2E con Playwright (3 flows: login → chat → escalation) — DEFER (requiere instalación + config + nuevo workflow)

**Discoveries Fase 10**:
- `tm-pulse-dot` se usaba en `escalation/page.tsx` SIN tener el `@keyframes` definido — bug latente que sólo se vería en browser, no en jsdom. Las animations ahora están todas definidas globalmente.
- Tailwind v4 NO permite `@layer base { @keyframes ... }` — los keyframes deben vivir fuera del @layer porque son global rules CSS, no Tailwind tokens.
- `:focus-visible` global rule cubre futuro código automáticamente; preferible a parchar 19 archivos manualmente.

**Files Fase 10**:
- `frontend/src/app/globals.css` — animations + reduced-motion + global focus-visible
- `frontend/src/components/error-screen.tsx` ✨
- `frontend/src/components/__tests__/error-screen.test.tsx` ✨
- `frontend/src/app/error.tsx` ✨ + `frontend/src/app/global-error.tsx` ✨
- `frontend/src/components/loading-screen.tsx` ✨
- `frontend/src/components/__tests__/loading-screen.test.tsx` ✨
- `frontend/src/app/{dashboard,chat,history,settings,admin}/loading.tsx` ✨

---

## Discoveries (se llena durante el trabajo)

(vacío — se va llenando con cosas no obvias que aparecen)

---

## Decisiones tomadas (architectural log)

- **2026-05-01 21:50** — Reusar Next.js 16 actual en vez de empezar de cero. El backend wiring (auth, WebSocket, tier gating, ApiError parser) ya está listo y la pérdida sería de semanas.
- **2026-05-01 21:50** — Tokens del prototipo (`--tm-*`) se mapean a Tailwind extend, NO se mantienen como CSS vars sueltas. Razón: shadcn v4 necesita los colores en `tailwind.config` para `bg-tm-blue-500` funcionar.
- **2026-05-01 21:50** — Fonts Geist via `next/font/google` (no `<link>` tags), porque Next 16 optimiza FOUT y el fallback es chequeado en build.
