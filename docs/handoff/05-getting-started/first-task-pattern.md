# Patrón para la Primera Tarea

Cómo estructurar el trabajo desde que recibís una instrucción hasta que
entregás algo verificado. Aplica tanto a tareas pequeñas como a features.

## El ciclo completo

```
1. Entender el pedido
2. Buscar contexto relevante
3. Explorar el código afectado
4. Proponer antes de implementar (si es > 30 min de trabajo)
5. Implementar (TDD si es código de runtime)
6. Verificar
7. Reportar
```

---

## 1. Entender el pedido

Antes de abrir un solo archivo:

- ¿Qué problema resuelve esto?
- ¿Qué no debería cambiar?
- ¿Hay algún gotcha conocido relacionado? (revisar `02-state/known-gotchas.md`)
- ¿Es código de runtime o configuración/docs?

Si el pedido es ambiguo, **hacer una sola pregunta** y esperar. No asumir.

---

## 2. Buscar contexto relevante

```
mem_search("<keywords del pedido>")
```

Si encontrás algo relevante en engram, leelo antes de continuar.

Revisar también si hay un ADR relacionado en
[`../01-architecture/decisions.md`](../01-architecture/decisions.md).

---

## 3. Explorar el código afectado

Leer los archivos específicos que vas a modificar, no el codebase entero.
Para entender la estructura general:

```bash
eza --tree --level=2 backend/app/
```

Para encontrar dónde está algo:
```bash
rg "require_subscription_tier" backend/app/    # buscar por texto
fd --type f "tier_gate" frontend/src/           # buscar por nombre
```

**Regla**: leer antes de escribir. Nunca asumir la estructura de un archivo
sin haberlo visto.

---

## 4. Proponer antes de implementar

Si la tarea tarda más de ~30 min o toca múltiples archivos, proponer el
enfoque primero:

- Qué archivos se modifican
- Qué patrón se sigue (ej: "sigo el mismo patrón que `test_audit.py`")
- Qué posibles efectos secundarios hay

Esperar confirmación del usuario antes de continuar.

Para tareas sustanciales, usar SDD:
```
/sdd-new <nombre-de-la-tarea>
```

---

## 5. Implementar

### Si es código de runtime → Strict TDD

```bash
# Ciclo obligatorio:
# RED: escribir el test que falla
poetry run pytest tests/test_mi_feature.py -v   # debe FALLAR
git add tests/test_mi_feature.py
git commit -m "test(scope): red — describe qué testea"

# GREEN: implementar lo mínimo necesario
poetry run pytest tests/test_mi_feature.py -v   # debe PASAR
git add app/...
git commit -m "fix(scope): green — describe qué implementa"

# REFACTOR: limpiar sin cambiar comportamiento
poetry run pytest tests/test_mi_feature.py -v   # debe seguir en verde
git commit -m "refactor(scope): describe qué se limpió"
```

### Si es docs, config, o tooling → sin TDD

```bash
# Hacer el cambio
# Verificar que no rompiste tests existentes
poetry run pytest -q

# Un commit por cambio atómico
git add ...
git commit -m "docs(handoff): describe el cambio"
```

### Convenciones obligatorias

- Conventional commits (`feat`, `fix`, `test`, `refactor`, `docs`, `chore`)
- Sin `Co-Authored-By` ni atribución AI
- Sin emojis en commits ni código (excepto los 6 del roadmap en docs de estado)
- Sin `git commit` desde sub-agents

---

## 6. Verificar

Antes de reportar trabajo terminado:

```bash
# 1. Tests en verde
cd backend && poetry run pytest -q
cd frontend && npm run test 2>&1 | tail -5

# 2. Commits reales
git log --oneline -5
git status   # working tree limpio

# 3. El comportamiento esperado funciona
# (verificar manualmente o con un test específico)
```

Si algo está roto → arreglarlo antes de reportar. No entregar trabajo con
tests rotos.

---

## 7. Reportar

Informe conciso al finalizar:

```
## Completado
- [qué se hizo con archivos afectados]

## Tests
- Backend: X/Y passing
- Frontend: Z/W passing

## Commits
- [hash corto] feat(scope): descripción
- [hash corto] test(scope): descripción

## Próximos pasos (si aplica)
- [qué quedó pendiente o qué conviene hacer después]
```

Si usaste engram: guardar un `mem_session_summary` antes de cerrar.

---

## Anti-patterns a evitar

- **Escribir código sin entender el problema**: produce soluciones que
  resuelven el síntoma, no la causa.
- **Modificar 5 archivos en un solo commit**: si algo se rompe, imposible
  de bisectar.
- **"Mejorar" cosas no pedidas**: sin contexto del trade-off original,
  las "mejoras" introducen regresiones.
- **Asumir que el test anterior pasaba**: correr siempre antes de modificar.
- **Reportar sin verificar**: un `git log` falso destruye la confianza.
