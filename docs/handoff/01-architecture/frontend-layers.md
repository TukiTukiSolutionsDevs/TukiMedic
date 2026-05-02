# Capas del Frontend

Next.js 16.2.3 + React 19. App Router. El scaffold existente fue extendido
(no reemplazado ni migrado a Vite). El prototipo HTML en
`~/Downloads/TukiMedicfront/tukimedic.html` es referencia VISUAL/UX, no
código portable.

## Tabla de contenidos

1. [Estructura de directorios](#estructura-de-directorios)
2. [Sistema de theme](#sistema-de-theme)
3. [API client](#api-client)
4. [Estado global](#estado-global)
5. [Páginas implementadas](#páginas-implementadas)
6. [Componentes shadcn](#componentes-shadcn)
7. [Testing](#testing)

## Estructura de directorios

```
frontend/src/
├── app/
│   ├── layout.tsx           # Root layout: fonts, ThemeProvider, sidebar scaffold
│   ├── globals.css          # Tailwind v4 + tokens shadcn (oklch) + tokens --tm-* (hex)
│   ├── page.tsx             # Página raíz (redirect o home)
│   ├── login/page.tsx
│   ├── register/page.tsx
│   ├── history/page.tsx
│   ├── upload/page.tsx
│   └── cases/[id]/page.tsx  # Scaffold — no funcional todavía
├── components/
│   ├── theme/
│   │   ├── theme-provider.tsx  # Context API + localStorage["tm-theme"] + FOUC guard
│   │   └── theme-toggle.tsx
│   └── ui/                  # shadcn v4 components (12 instalados)
├── lib/
│   ├── api.ts               # ApiError, rawRequest, token refresh automático
│   ├── tier-gate.ts         # parseTierGate(), isTierGateError()
│   └── utils.ts             # cn() helper
├── store/
│   └── auth-store.ts        # zustand: accessToken, refreshToken, user, setTokens, logout
└── __tests__/               # o co-located *.test.tsx
```

## Sistema de theme

### Dos familias de tokens que coexisten

`globals.css` mantiene dos familias de tokens para no romper shadcn ni
perder los colores del prototipo:

| Familia | Formato | Origen | Uso |
|---------|---------|--------|-----|
| shadcn tokens (`--background`, `--foreground`, etc.) | `oklch` | shadcn v4 scaffold | Componentes shadcn, Tailwind utilities |
| `--tm-*` (`--tm-primary`, `--tm-surface`, etc.) | `hex` | Prototipo TukiMedic | Brand colors, gradientes personalizados |

### Dark mode

Activado via clase `.dark` en `<html>` (NO `[data-theme]` — rompe shadcn v4).
El `@custom-variant dark (&:is(.dark *))` permite usar `dark:` utilities de Tailwind.

### ThemeProvider

- Context API (no zustand — demasiado para estado trivial de theme).
- Persiste en `localStorage["tm-theme"]`.
- Default: system preference (`prefers-color-scheme`).
- **FOUC guard**: blocking inline script en `<head>` (vía `dangerouslySetInnerHTML`)
  que lee `localStorage["tm-theme"]` y agrega `.dark` a `<html>` antes del
  primer paint. `suppressHydrationWarning` en `<html>` para silenciar el
  mismatch SSR/CSR.

### Gotcha: `--font-sans` recursivo

El scaffold de shadcn v4 viene con `--font-sans: var(--font-sans)` (referencia
circular). Al agregar `next/font`, hay que cambiar a `var(--font-geist)`.

## API client

`src/lib/api.ts` — cliente centralizado sobre `fetch`:

- **Base URL**: `NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'`.
- **Bearer automático**: lee `accessToken` del auth store.
- **Refresh transparente**: en 401, intenta `POST /auth/refresh` una vez.
  Si falla → `logout()` y deja que la próxima navegación redirija.
- **`ApiError`**: `{ status, message, body, code }`. El campo `code` extrae
  `body.detail.code` cuando `detail` es objeto (clave para tier-gate).
- **FormData**: si el body es `FormData`, NO setea `Content-Type` (el browser
  lo pone con boundary automáticamente).

## Estado global

`src/store/auth-store.ts` — zustand store:

```typescript
interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: UserResponse | null
  setTokens(access: string, refresh: string): void
  setUser(user: UserResponse): void
  logout(): void
}
```

Responsabilidades del auth store: solo tokens + user. Nada de UI state.

## Páginas implementadas

| Ruta | Estado | Notas |
|------|--------|-------|
| `/login` | ✅ funcional | Form + validación + ApiError |
| `/register` | ✅ funcional | Form + consent booleano |
| `/history` | ✅ funcional | Lista de casos del user |
| `/upload` | ✅ funcional | Upload de documentos (tier gate visible) |
| `/cases/[id]` | 🟡 scaffold | Armado de la página, no muestra datos reales |

**Sidebar** en `layout.tsx`: estructura HTML presente, lista de casos pendiente.

## Componentes shadcn

shadcn v4 usa `@base-ui/react` como primitivas (NO Radix). 12 componentes
instalados. Los componentes están en `src/components/ui/`.

Comandos shadcn v4:
```bash
npx shadcn@latest add button   # agregar un componente
```

**NO** usar `npx shadcn-ui` (versión v3, Radix-based, incompatible).

## Testing

- Runner: **Vitest 4.1.5** (NO Jest).
- Setup: `jsdom` environment + `@testing-library/react` + `@testing-library/jest-dom`.
- 52 tests, todos passing.

**Gotcha crítico en tests de theme**: el `classList` del `document.documentElement`
NO se limpia automáticamente entre tests. Cada `beforeEach` debe:

```typescript
beforeEach(() => {
  document.documentElement.classList.remove('dark')
})
```

Sin esto, tests que activan dark mode afectan a los siguientes.

**Correr tests**:
```bash
cd frontend && npm run test          # run una vez
npm run test:watch                   # modo watch
npm run test:ui                      # Vitest UI en browser
```
