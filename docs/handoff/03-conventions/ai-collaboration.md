# Convenciones de Colaboración con AI

Reglas para trabajar con Claude Code, sub-agents y el workflow SDD.
Leé esto ANTES de delegar cualquier tarea. Ignorar estas reglas produce
trabajo duplicado y horas de debugging fantasma.

## Reglas críticas (NUNCA ignorar)

### 1. Sub-agents NO commitean

Los sub-agents (lanzados via `delegate`, `sdd-apply`, etc.) **solo escriben
archivos al disco**. NO hacen `git add`, NO hacen `git commit`.

El orchestrator (o el humano) hace los commits desde el working tree real
al final.

**Por qué**: los sub-agents pueden ejecutar `git commit` en su contexto y
reportar un hash, pero ese hash puede no existir en el repo real. Este es
un bug sistémico observado en múltiples sesiones.

**Verificación obligatoria**:
```bash
git log --oneline -5    # después de cualquier delegación
git status              # ¿hay cambios sin commitear?
```

Si el sub-agent reportó un hash que no aparece en `git log`, los cambios
existen solo en disco — hacés el commit vos.

---

### 2. `docker cp` siempre seguido de restart

Después de copiar cualquier archivo Python al container backend:
```bash
docker cp path/file.py docker-backend-1:/app/path/file.py
docker compose restart backend
```

Sin el restart, uvicorn sigue con los módulos viejos en memoria.

**EXCEPCIÓN**: si hay una eval clínica corriendo (`pytest -m live_llm`),
NO reiniciar hasta que termine. El restart interrumpe WebSocket activos.

---

### 3. Verificar antes de reportar "listo"

Antes de decir que una tarea está terminada:
```bash
git status              # ¿working tree limpio?
git log --oneline -3    # ¿commits reales?
cd backend && poetry run pytest -q --co | tail -5  # ¿tests recolectan?
cd frontend && npm run test 2>&1 | tail -5           # ¿tests pasan?
```

Un agent que reporta "listo" sin verificar pasa a ser un agent que creó
deuda técnica.

---

## Workflow SDD (Spec-Driven Development)

Para tareas sustanciales, el orchestrator usa el flujo SDD:

```
/sdd-new <nombre>     → exploración + propuesta
/sdd-ff <nombre>      → fast-forward: proposal → specs → design → tasks
/sdd-apply            → implementación por batches (sub-agent sdd-apply)
/sdd-verify           → validación contra specs
/sdd-archive          → cerrar el change y persistir en engram
```

**Artifact store**: engram (default). Artifacts viven en memoria persistente
entre sesiones. Si engram no está disponible → none (inline).

**Modo de ejecución**: interactive por default — el orchestrator pausa entre
fases, muestra resultado y pregunta antes de continuar.

**TDD en sdd-apply**: el sub-agent sdd-apply tiene Strict TDD Mode activado.
Cada tarea del task list sigue RED → GREEN → REFACTOR con commits separados.

---

## Memoria entre sesiones (Engram)

Al inicio de cada sesión, el agent DEBE:
```
mem_search("tuki-medic session summary")
```

Esto recupera el contexto de sesiones anteriores. Sin esto, el agent empieza
ciego y puede repetir trabajo ya hecho o reintroducir bugs ya resueltos.

Al final de cada sesión, el agent DEBE:
```
mem_session_summary(...)
```

Con: Goal, Discoveries, Accomplished, Next Steps, Relevant Files.

**Sin mem_session_summary al final, la próxima sesión empieza sin contexto.**

---

## Delegación de lectura de código

Para tareas que requieren leer 4+ archivos para entender el codebase, o
escribir cambios en múltiples archivos, delegar a un sub-agent.

Para verificaciones rápidas (1-3 archivos, bash de estado), hacer inline.

Regla: **¿Esto infla mi contexto sin necesidad? → delegar**.

---

## Idioma de los docs

- Docs de producto y técnicos: **español Rioplatense (voseo natural)**.
- Nombres técnicos y del producto en su forma original: FastAPI, LangGraph,
  Mesa de Especialistas, Triage Level, etc.
- Términos en inglés del código (endpoint, request, deploy) se dejan en inglés.
- NO overload de slang. Rioplatense natural, no performance de jerga.

---

## Qué hacer cuando algo falla de forma inesperada

1. Antes de asumir que es un bug del código, verificar que el container
   tiene el código correcto (`docker exec` + `bat` el archivo).
2. Revisar `known-gotchas.md` — el síntoma probablemente ya está documentado.
3. Verificar que los tests corren en verde antes del cambio.
4. Introducir el cambio mínimo necesario para reproducir el problema.
5. Documentar el root cause en `known-gotchas.md` si no estaba.
