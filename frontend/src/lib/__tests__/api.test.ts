/**
 * Tests for parseResponse / ApiError — specifically the object-detail bug.
 *
 * Bug: when body.detail is an object (e.g. tier_required 403), calling
 * String(detail) produces "[object Object]" instead of a useful message.
 *
 * Covered:
 * 1. object detail with code only   → message = code, never "[object Object]"
 * 2. object detail with message key → message = detail.message
 * 3. string detail                  → backwards compat unchanged
 * 4. non-JSON 500 body              → fallback message contains status code
 * 5. ApiError.code exposed          → set when detail.code exists
 * 6. ApiError.code absent           → undefined when detail has no code
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api, ApiError } from '../api'

vi.mock('@/store/auth-store', () => ({
  useAuthStore: {
    getState: vi.fn(() => ({
      accessToken: null,
      refreshToken: null,
      setTokens: vi.fn(),
      logout: vi.fn(),
    })),
  },
}))

function stubFetch(status: number, body: unknown, contentType = 'application/json') {
  const headers = new Headers()
  if (contentType) headers.set('Content-Type', contentType)
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      headers,
      json: () => Promise.resolve(body),
      text: () => Promise.resolve('Internal Server Error'),
    }),
  )
}

beforeEach(() => {
  vi.unstubAllGlobals()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ApiError — object detail parsing', () => {
  it('403 object detail: message is never "[object Object]"', async () => {
    stubFetch(403, {
      detail: { code: 'tier_required', required_tier: 'paid', current_tier: 'free' },
    })

    const err = await api.get('/test', { authenticated: false }).catch(e => e) as ApiError

    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).not.toBe('[object Object]')
  })

  it('403 object detail with code only: message contains the code', async () => {
    stubFetch(403, {
      detail: { code: 'tier_required', required_tier: 'paid', current_tier: 'free' },
    })

    const err = await api.get('/test', { authenticated: false }).catch(e => e) as ApiError

    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toContain('tier_required')
  })

  it('403 object detail with message field: uses detail.message', async () => {
    stubFetch(403, {
      detail: { code: 'tier_required', message: 'Premium required' },
    })

    const err = await api.get('/test', { authenticated: false }).catch(e => e) as ApiError

    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('Premium required')
    expect(err.message).not.toBe('[object Object]')
  })

  it('403 string detail: backwards compat — message equals the string', async () => {
    stubFetch(403, { detail: 'Account disabled' })

    const err = await api.get('/test', { authenticated: false }).catch(e => e) as ApiError

    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('Account disabled')
  })

  it('500 non-JSON body: fallback message contains status code', async () => {
    stubFetch(500, null, 'text/html')

    const err = await api.get('/test', { authenticated: false }).catch(e => e) as ApiError

    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toMatch(/500/)
    expect(err.message).not.toBe('[object Object]')
  })

  it('ApiError.code is set to detail.code when present', async () => {
    stubFetch(403, {
      detail: { code: 'tier_required', required_tier: 'paid', current_tier: 'free' },
    })

    const err = await api.get('/test', { authenticated: false }).catch(e => e) as ApiError

    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError & { code?: string }).code).toBe('tier_required')
  })

  it('ApiError.code is undefined when detail is a string (no code)', async () => {
    stubFetch(403, { detail: 'Account disabled' })

    const err = await api.get('/test', { authenticated: false }).catch(e => e) as ApiError

    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError & { code?: string }).code).toBeUndefined()
  })
})
