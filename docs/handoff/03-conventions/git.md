# Convenciones Git

## Identidad local

```bash
# Ya configurado en el repo:
git config user.name "soulkin"
git config user.email "soulkin@MacBook-Air-de-Andre.local"
```

No cambies la identidad. Los commits del proyecto tienen esta firma.

## Conventional Commits

**Formato obligatorio**:
```
<type>(<scope>): <descripción en imperativo, minúsculas>
```

**Types permitidos**:

| Type | Cuándo |
|------|--------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `test` | Agregar o modificar tests |
| `refactor` | Cambio de código sin fix ni feature |
| `chore` | Tooling, deps, config |
| `docs` | Solo documentación |
| `perf` | Mejora de performance |

**Scopes comunes**:

| Scope | Qué cubre |
|-------|----------|
| `auth` | Autenticación, JWT, RBAC |
| `chat` | WebSocket, grafo, orquestación |
| `agents` | Cualquier agente individual o el grafo |
| `triage` | Solo el agente de triage |
| `specialists` | Dispatcher, registry, agentes de especialidad |
| `audit` | Hash chain, audit service |
| `tier` | Tier gating, subscription |
| `frontend` | Cambios en `frontend/` |
| `infra` | Docker, compose, CI |
| `deps` | Actualización de dependencias |

**Ejemplos correctos**:
```
feat(tier): add require_subscription_tier dependency factory
fix(guardrail): clamp interrupt to critical violations only
test(audit): add verify_chain integration test
refactor(specialists): normalize specialty names with NFD decompose
docs(handoff): create session handoff structure
chore(deps): bump langchain-openai to latest
```

**Prohibido**:
```
# Nunca:
feat: add stuff
fix: fix bug
Co-Authored-By: Claude <claude@anthropic.com>
```

## Workflow de commits

El patrón estándar para TDD (ver [`tdd.md`](./tdd.md)):
1. `test(scope): red — <qué testea>`
2. `fix(scope): green — <implementación mínima>`
3. `refactor(scope): <qué se limpió>`

Para no-TDD (docs, config, chore):
- Un commit por cambio atómico y coherente.
- Si un PR tiene varios commits, que cada uno compile y pase tests.

## Regla crítica: nunca commitear desde sub-agents

Los sub-agents (delegados via SDD o tool) NO deben hacer `git commit`.
Solo escriben archivos al disco. El orchestrator (o el humano) commitea
desde el working tree real al final.

**Motivo**: sub-agents pueden reportar hashes de commit que no existen
en el git real. Ver [`../02-state/known-gotchas.md`](../02-state/known-gotchas.md) gotcha #1.

## Verificación post-tarea

Antes de reportar trabajo terminado:
```bash
git status                    # ¿hay archivos sin stagear?
git log --oneline -5          # ¿los commits son reales?
git diff --stat HEAD~1 HEAD   # ¿el diff es correcto?
```
