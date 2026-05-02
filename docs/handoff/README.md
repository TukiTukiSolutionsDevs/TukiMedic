# Tuki-Medic — Handoff Hub

Plataforma SaaS de análisis clínico conversacional multi-agente. Un paciente
interactúa via chat (WebSocket), el sistema corre un grafo LangGraph que
orquesta 8 categorías de agentes especializados, y devuelve una respuesta
clínica consolidada con disclaimer médico.

## Estructura del directorio

```
docs/handoff/
├── README.md                       ← estás acá
├── 00-product/                     ← qué hace el producto
│   ├── overview.md
│   ├── glossary.md
│   ├── clinical-flow.md
│   └── tier-model.md
├── 01-architecture/                ← cómo está construido
│   ├── stack.md
│   ├── backend-layers.md
│   ├── frontend-layers.md
│   ├── orchestration.md
│   └── decisions.md
├── 02-state/                       ← dónde estamos hoy
│   ├── roadmap.md
│   ├── done.md
│   ├── pending.md
│   └── known-gotchas.md
├── 03-conventions/                 ← cómo trabajamos
│   ├── git.md
│   ├── tdd.md
│   ├── tooling.md
│   └── ai-collaboration.md
├── 04-runbook/                     ← cómo operamos el stack
│   ├── setup.md
│   ├── testing.md
│   ├── debugging.md
│   └── secrets.md
└── 05-getting-started/             ← punto de entrada para agent nuevo
    ├── new-agent-checklist.md
    └── first-task-pattern.md
```

## Orden de lectura recomendado (agent nuevo)

1. **`05-getting-started/new-agent-checklist.md`** — empezá siempre acá
2. **`00-product/overview.md`** + **`00-product/glossary.md`** — dominio del problema
3. **`03-conventions/ai-collaboration.md`** — reglas críticas antes de tocar código
4. **`02-state/roadmap.md`** — en qué fase estamos y qué sigue
5. **`01-architecture/orchestration.md`** — el grafo LangGraph, corazón del sistema
6. **`04-runbook/setup.md`** + **`04-runbook/testing.md`** — levantá el stack, corré los tests

## Principios de organización

Cada carpeta responde a un **concern** (producto, arquitectura, estado,
convenciones, operaciones), no a una fase temporal. Esto permite encontrar
lo necesario sin saber cuándo se escribió algo.

Cada archivo es **self-contained**: puede leerse sin requerir el orden de
otros archivos del mismo directorio. Los cross-links son opcionales y usan
paths relativos.
