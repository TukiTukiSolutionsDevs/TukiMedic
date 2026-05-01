/**
 * Tests for the tier-gating helpers.
 *
 * Backend contract for paid-tier endpoints:
 *
 *   HTTP 403 with body
 *   { "detail": {
 *       "code": "tier_required",
 *       "required_tier": "paid",
 *       "current_tier": "free"
 *   } }
 *
 * The frontend MUST handle this without showing a generic error screen —
 * it should detect the gate and render an upgrade prompt instead.
 */
import { describe, it, expect } from 'vitest'
import { ApiError } from './api'
import { parseTierGate, isTierGateError, TIER_GATE_CODE } from './tier-gate'

describe('parseTierGate', () => {
  it('returns the gate info when the error matches the contract', () => {
    const err = new ApiError(403, 'Forbidden', {
      detail: {
        code: 'tier_required',
        required_tier: 'paid',
        current_tier: 'free',
      },
    })

    expect(parseTierGate(err)).toEqual({
      requiredTier: 'paid',
      currentTier: 'free',
    })
  })

  it('returns null for a 403 that is NOT a tier gate (e.g. account disabled)', () => {
    const err = new ApiError(403, 'Account disabled', {
      detail: 'Account disabled',
    })
    expect(parseTierGate(err)).toBeNull()
  })

  it('returns null for non-403 errors even if the body looks similar', () => {
    const err = new ApiError(500, 'Internal', {
      detail: {
        code: 'tier_required',
        required_tier: 'paid',
        current_tier: 'free',
      },
    })
    expect(parseTierGate(err)).toBeNull()
  })

  it('returns null when body is missing or malformed', () => {
    expect(parseTierGate(new ApiError(403, 'Forbidden', null))).toBeNull()
    expect(
      parseTierGate(new ApiError(403, 'Forbidden', { detail: {} })),
    ).toBeNull()
    expect(
      parseTierGate(
        new ApiError(403, 'Forbidden', {
          detail: { code: 'tier_required' },
        }),
      ),
    ).toBeNull()
  })

  it('returns null for non-ApiError values (e.g. TypeError from network)', () => {
    expect(parseTierGate(new TypeError('Failed to fetch'))).toBeNull()
    expect(parseTierGate(undefined)).toBeNull()
    expect(parseTierGate(null)).toBeNull()
  })
})

describe('isTierGateError', () => {
  it('is true for a real tier_required 403', () => {
    const err = new ApiError(403, 'Forbidden', {
      detail: {
        code: 'tier_required',
        required_tier: 'paid',
        current_tier: 'free',
      },
    })
    expect(isTierGateError(err)).toBe(true)
  })

  it('is false for any other error shape', () => {
    expect(
      isTierGateError(
        new ApiError(403, 'Forbidden', { detail: 'Account disabled' }),
      ),
    ).toBe(false)
    expect(isTierGateError(new TypeError('boom'))).toBe(false)
  })
})

describe('TIER_GATE_CODE', () => {
  it('is the exact string the backend emits', () => {
    expect(TIER_GATE_CODE).toBe('tier_required')
  })
})
