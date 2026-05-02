# Tier Model — Free vs Paid

Tuki-Medic tiene dos tiers de suscripción: `free` y `paid`. El enforcement es
**real** tanto en backend (dependency de FastAPI) como en el grafo LangGraph
(gating antes de despachar specialists).

## Tabla de contenidos

1. [Comparativa de tiers](#comparativa-de-tiers)
2. [Enforcement backend](#enforcement-backend)
3. [Enforcement en el grafo](#enforcement-en-el-grafo)
4. [Contrato frontend](#contrato-frontend)
5. [Lo que falta](#lo-que-falta)

## Comparativa de tiers

| Feature | Free | Paid |
|---------|------|------|
| Chat clínico (Triage + Classifier) | ✅ | ✅ |
| Análisis multi-especialista (Mesa de Especialistas) | ❌ | ✅ |
| Upload de documentos (`/documents/upload`) | ❌ | ✅ |
| Export PDF (`/export/pdf/{case_id}`) | ❌ | ✅ |
| Historial de casos | ✅ | ✅ |
| Upgrade hint en respuesta | Aparece | No aparece |

> Notas:
> - El chat free igual corre Triage + Anamnesis + Classifier + Synthesizer.
>   Solo saltea los specialists. El paciente recibe una respuesta de triaje básico.
> - El `TIER_UPGRADE_HINT` se concatena en la respuesta cuando `tier_gated_specialists=True`.

## Enforcement backend

### Dependency `require_subscription_tier`

Definido en `backend/app/core/dependencies.py`:

```python
def require_subscription_tier(min_tier: str):
    """FastAPI dependency factory. Levanta HTTP 403 si el tier del usuario
    está por debajo del mínimo requerido."""
```

**Shape del 403** (contrato estable con el frontend):
```json
{
  "detail": {
    "code": "tier_required",
    "required_tier": "paid",
    "current_tier": "free"
  }
}
```

Endpoints que usan esta dependency hoy:
- `POST /api/v1/documents/upload` → `require_subscription_tier("paid")`
- `GET /api/v1/export/pdf/{case_id}` → `require_subscription_tier("paid")`

### Modelo User

`subscription_tier` en `backend/app/models/user.py`:
- Columna `String(50)`, default `"free"`, `server_default="free"`.
- Valores válidos: `"free"`, `"paid"`.
- Valores desconocidos (legacy, edición manual de DB) → rank 0 (nunca pasan un gate de tier superior).

### TIER_RANK en dependencies.py

```python
TIER_RANK: dict[str, int] = {"free": 0, "paid": 1}
```

Valores desconocidos → rank 0 via `.get(tier, 0)`. Fail-safe.

## Enforcement en el grafo

Dentro del nodo `specialists` del grafo (`orchestrator/graph.py`):

```python
def _should_gate_specialists(state) -> bool:
    tier = state.get("subscription_tier") or "free"
    return tier != "paid"
```

Si gateado → `{"specialist_outputs": {}, "tier_gated_specialists": True}`.

El `subscription_tier` se inyecta al state desde `user.subscription_tier`
en el WebSocket handler (`chat.py:259`).

Beneficio: usuarios free NO consumen tokens LLM de specialists → costo 0.

## Contrato frontend

### `src/lib/tier-gate.ts`

Helper centralizado. Detecta el 403 tier_required y devuelve `TierGateInfo`:

```typescript
export function parseTierGate(err: unknown): TierGateInfo | null
export function isTierGateError(err: unknown): boolean
```

### `TierUpgradeBanner`

Componente en `frontend/src/components/theme/` (o similar) que se muestra
cuando el backend devuelve el 403 con `code: "tier_required"`.

Uso típico en pages:
```tsx
try {
  await api.post('/api/v1/documents/upload', formData)
} catch (err) {
  const gate = parseTierGate(err)
  if (gate) showTierBanner(gate)
  else showGenericError(err)
}
```

### `ApiError.code`

La clase `ApiError` (`src/lib/api.ts`) extrae `body.detail.code` a una
propiedad dedicada `.code`. Permite discriminar `tier_required` de otros 403
(ej: account disabled) sin parsear el body manualmente.

## Lo que falta

- **Stripe billing**: 0 imports de Stripe en `app/`. El tier se asigna
  manualmente en DB por ahora.
- **Más endpoints gateados**: solo 2 endpoints tienen `require_subscription_tier`.
  La expansión del gate a otras features está pendiente.
- **Upgrade flow en frontend**: el banner existe pero no hay flujo de
  checkout real (Stripe pendiente).
