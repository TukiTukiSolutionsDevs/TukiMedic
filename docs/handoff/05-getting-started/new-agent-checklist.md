# Checklist para Agent Nuevo

Ejecutá estos pasos **en orden** al inicio de cada sesión nueva o cuando
retomás el proyecto después de tiempo. No saltees pasos — cada uno existe
porque alguien lo aprendió de la peor manera.

---

## Paso 1 — Recuperar contexto de sesiones anteriores

Si tenés acceso a engram (memoria persistente entre sesiones):

```
mem_search("tuki-medic session summary")
```

Si encontrás resultados, leerlos antes de continuar. Contienen decisiones,
bugs arreglados y próximos pasos de sesiones anteriores.

Si engram no está disponible, continuá al paso 2.

---

## Paso 2 — Leer este hub

```
docs/handoff/README.md
```

Ya lo estás leyendo, pero el índice te va a orientar si necesitás profundizar
en algún área específica.

---

## Paso 3 — Entender el dominio

Leer en este orden:

1. [`../00-product/overview.md`](../00-product/overview.md) — qué hace el producto y sus límites
2. [`../00-product/glossary.md`](../00-product/glossary.md) — vocabulario canónico (Mesa de Especialistas, Triage Level, etc.)

Si vas a tocar el flujo clínico:
3. [`../00-product/clinical-flow.md`](../00-product/clinical-flow.md) — el grafo LangGraph con condiciones de ruteo

---

## Paso 4 — Leer las reglas de colaboración con AI (CRÍTICO)

```
docs/handoff/03-conventions/ai-collaboration.md
```

Especialmente los gotchas:
- Sub-agents NO commitean (los hashes reportados pueden ser inventados)
- `docker cp` siempre seguido de `docker compose restart backend`
- Verificar con `git log` antes de reportar trabajo terminado

Si no leés esto, vas a perder tiempo con falsos commits y módulos cacheados.

---

## Paso 5 — Verificar en qué punto está el proyecto

```
docs/handoff/02-state/roadmap.md
```

Identificá:
- ¿En qué fase estamos?
- ¿Qué está completado con evidencia?
- ¿Cuáles son los próximos ítems prioritarios?

---

## Paso 6 — Verificar working tree limpio

```bash
cd /Users/soulkin/Documents/Tuki-Medic
git status
```

**Si hay cambios sin commitear**: no empezar a trabajar sin entender qué son.
Preguntar al usuario antes de continuar.

**Si hay cambios sin stagear que deberían haberse commiteado**: podría ser
evidencia del gotcha #1 (sub-agent que escribió pero no commiteó correctamente).
Verificar con `git diff` y commitear si corresponde.

---

## Paso 7 — Verificar tests en verde

```bash
# Backend
cd /Users/soulkin/Documents/Tuki-Medic/backend
poetry run pytest -q --co 2>&1 | tail -5

# Frontend
cd /Users/soulkin/Documents/Tuki-Medic/frontend
npm run test 2>&1 | tail -5
```

Si algo está roto antes de tu intervención → informar al usuario ANTES de
hacer cualquier cambio. No intentar arreglar silenciosamente.

---

## Paso 8 — Verificar el stack levantado (si vas a testear manualmente)

```bash
cd /Users/soulkin/Documents/Tuki-Medic/infra/docker
docker compose ps
```

Si no está levantado:
```bash
docker compose up -d
```

Esperar a que todos los servicios estén `running`, luego:
```bash
curl http://localhost:8001/health/ready
```

---

## Paso 9 — Esperar instrucción del usuario

Con todo verificado, reportar al usuario:
- Contexto recuperado de engram (si aplica): X sesiones anteriores encontradas
- Estado del working tree: limpio / hay N archivos modificados
- Tests: backend ✅/❌, frontend ✅/❌
- Stack: up/down

Luego **esperar** la instrucción. No empezar a "mejorar cosas" por iniciativa.

---

## Referencia rápida de comandos

```bash
# Tests backend
cd backend && poetry run pytest -q

# Tests frontend
cd frontend && npm run test

# Stack up
cd infra/docker && docker compose up -d

# Logs backend
docker logs -f docker-backend-1

# Smoke audit chain
cd backend && poetry run python scripts/smoke_audit_chain.py

# Eval clínica (requiere LLM activo, tarda varios minutos)
cd backend && poetry run pytest tests/clinical_eval/ -m live_llm -v
```
