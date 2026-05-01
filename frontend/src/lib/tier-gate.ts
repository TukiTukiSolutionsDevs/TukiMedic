/**
 * Tier-gating helpers.
 *
 * Backend contract for paid-tier endpoints (chat with specialists,
 * documents/upload, cases/{id}/export/pdf, history > 7 days):
 *
 *   HTTP 403 with body
 *   { "detail": {
 *       "code": "tier_required",
 *       "required_tier": "paid",
 *       "current_tier": "free"
 *   } }
 *
 * Treating this like any other 403 (e.g. "account disabled") is a UX
 * regression — the user is NOT blocked from the product, they are blocked
 * from one feature. Callers must detect the gate and render an upsell
 * instead of a generic error screen.
 *
 * Usage:
 *
 *   try {
 *     await api.post('/api/v1/documents/upload', formData)
 *   } catch (err) {
 *     const gate = parseTierGate(err)
 *     if (gate) showUpsellModal(gate)
 *     else showGenericError(err)
 *   }
 */
import { ApiError } from './api'

export const TIER_GATE_CODE = 'tier_required' as const

export interface TierGateInfo {
  /** The tier the user needs to access this feature (typically "paid"). */
  requiredTier: string
  /** The user's current tier (typically "free"). */
  currentTier: string
}

interface TierRequiredDetail {
  code: typeof TIER_GATE_CODE
  required_tier: string
  current_tier: string
}

function isTierRequiredDetail(detail: unknown): detail is TierRequiredDetail {
  if (typeof detail !== 'object' || detail === null) return false
  const d = detail as Record<string, unknown>
  return (
    d.code === TIER_GATE_CODE &&
    typeof d.required_tier === 'string' &&
    typeof d.current_tier === 'string'
  )
}

/**
 * Parse a thrown value and return tier-gate info if it is a 403 with the
 * tier_required contract. Returns null for anything else — including
 * non-403 errors, malformed bodies, and non-ApiError throwables.
 */
export function parseTierGate(err: unknown): TierGateInfo | null {
  if (!(err instanceof ApiError)) return null
  if (err.status !== 403) return null

  const body = err.body
  if (typeof body !== 'object' || body === null) return null
  const detail = (body as { detail?: unknown }).detail
  if (!isTierRequiredDetail(detail)) return null

  return {
    requiredTier: detail.required_tier,
    currentTier: detail.current_tier,
  }
}

/** Convenience predicate for callers that only need a yes/no. */
export function isTierGateError(err: unknown): boolean {
  return parseTierGate(err) !== null
}
