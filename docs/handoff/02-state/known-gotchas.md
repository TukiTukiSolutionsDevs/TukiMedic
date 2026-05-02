# Gotchas conocidos

Problemas, comportamientos no obvios y trampas que ya costaron tiempo.
Leé esto antes de debuggear cualquier cosa rara.

---

## 1. Sub-agents alucinan commits

**Síntoma**: cuando delegás una tarea a un sub-agent (ej: `sdd-apply`), el
agent reporta hashes de commit que **no existen** en `git log` real.

**Causa**: los sub-agents tienen acceso a bash pero no al working tree real del
orchestrator. Pueden ejecutar `git commit`, crear un commit en su contexto de
ejecución, reportar el hash — pero ese commit puede no estar en el repo que vos
ves.

**Regla**: SIEMPRE verificar con `git log --oneline -5` después de cualquier
delegación. Si los hashes no coinciden, el orchestrator debe hacer los commits
desde el working tree real.

**Workaround establecido**: el orchestrator hace todos los `git add` + `git commit`
desde el working tree real al final de cada sesión de trabajo. Los sub-agents
solo escriben archivos al disco.

---

## 2. `docker cp` sin restart deja módulos cacheados

**Síntoma**: copiás código backend con `docker cp`, relanzás una request, y
el comportamiento no cambia. O peor, obtenés un error que el código nuevo
ya no debería tener (ej: `IntegrityError: null value in column "previous_hash"`
cuando el modelo en disco ya tiene la columna).

**Causa**: uvicorn cachea los módulos Python al arrancar. Si no reiniciás el
container, sigue ejecutando el código antiguo en memoria.

**Regla**: después de cualquier `docker cp` de código backend:
```bash
docker compose restart backend
```

**EXCEPCIÓN**: si hay una eval clínica corriendo, NO reiniciar. El restart
interrumpe todas las conexiones WebSocket activas.

---

## 3. shadcn v4 scaffold — `--font-sans` recursivo

**Síntoma**: al agregar `next/font/google` al layout, el texto del sitio
usa una fuente genérica del browser en vez de Geist.

**Causa**: el scaffold de shadcn v4 genera `globals.css` con:
```css
--font-sans: var(--font-sans);  /* referencia circular */
```

**Fix**: cambiar a:
```css
--font-sans: var(--font-geist);
```

---

## 4. Instrument_Serif no es variable font

**Síntoma**: build error de Next.js al intentar cargar Instrument Serif
sin especificar `weight`.

**Causa**: a diferencia de Geist, Instrument Serif no tiene variable font
axis. `next/font/google` requiere que se especifiquen los weights y styles
que se van a usar.

**Fix correcto**:
```typescript
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",              // obligatorio
  style: ["normal", "italic"], // obligatorio para tener italic
  variable: "--font-instrument-serif",
})
```

---

## 5. classList no se limpia entre tests RTL

**Síntoma**: un test que activa dark mode (`document.documentElement.classList.add('dark')`)
contamina el DOM global para todos los tests que corren después.

**Causa**: jsdom mantiene el mismo `document` entre tests del mismo archivo.
Las mutaciones al `documentElement.classList` persisten.

**Fix**: en cualquier suite que toque el theme:
```typescript
beforeEach(() => {
  document.documentElement.classList.remove('dark')
  localStorage.clear()
})
```

---

## 6. Shape del 403 tier_required — sin campo `message`

**Síntoma**: el frontend muestra "undefined" en el toast de error cuando
se intenta subir un documento con cuenta free.

**Causa**: el 403 de `require_subscription_tier` tiene este shape:
```json
{
  "detail": {
    "code": "tier_required",
    "required_tier": "paid",
    "current_tier": "free"
  }
}
```
No hay campo `message` en `detail`. El código de `parseResponse` en `api.ts`
no lo encuentra y fallback a `code` como mensaje.

**Regla**: usar `parseTierGate(err)` (en `lib/tier-gate.ts`) para detectar
este error. NO tratarlo como un 403 genérico.

---

## 7. graph_cache race condition en multi-worker

**Síntoma**: después de rotar la credencial LLM en el panel admin, algunos
requests siguen usando la credencial vieja por hasta 5 minutos.

**Causa**: el graph cache es in-memory con TTL 5 min. En multi-worker (Gunicorn),
cada worker tiene su propio cache. La rotación de credenciales no se propaga
a workers que todavía tienen el grafo en cache.

**No es un bug** — es el comportamiento esperado. El TTL mitiga la ventana.
Para propagación inmediata, el workaround es reiniciar los workers (o reducir
el TTL a costa de más compila-ciclos).

---

## 8. Memoria L1 es efímera — Redis flush borra el historial

**Síntoma**: el chat no recuerda mensajes anteriores después de un `redis-cli FLUSHALL`.

**Causa**: el historial de mensajes (L1) se guarda solo en Redis (RPUSH + LTRIM).
No se persiste en Postgres. Si Redis se flushea, el historial se pierde.

**Regla**: nunca hacer `FLUSHALL` en producción. En dev, es comportamiento esperado.

---

## 9. Refresh token sin role/tier en payload

**Causa técnica** (`auth.py:147`): el nuevo `access_token` emitido por
`POST /auth/refresh` no incluye `role` ni `subscription_tier` en el payload JWT.

```python
return TokenResponse(
    access_token=create_access_token({"sub": str(user.id)}),  # sin role/tier
    ...
)
```

**Es seguro hoy** porque `get_current_user` re-fetchea la DB en cada request.
Pero es inconsistente con el login (que sí incluye role/tier). Si alguna vez
se implementa autorización off-DB (ej: edge functions que validan el JWT sin DB),
esto se vuelve un bug de seguridad.

---

## 10. Frontend dev con `npm run dev` no funciona desde MCP bash

**Síntoma**: al intentar correr `npm run dev` desde la herramienta bash de IA,
el proceso muere con SIGHUP o no levanta correctamente.

**Causa**: el proceso hijo hereda la sesión del proceso MCP y muere cuando
el shell padre hace cleanup.

**Regla**: correr el dev server siempre desde una terminal real:
```bash
cd frontend && npm run dev
```
