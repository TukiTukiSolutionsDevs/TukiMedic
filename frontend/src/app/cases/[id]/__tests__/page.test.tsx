import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React, { Suspense } from 'react'

import CaseDetailPage from '../page'
import { api, ApiError } from '@/lib/api'

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
    },
  }
})

vi.mock('@/store/auth-store', () => ({
  useAuthStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ accessToken: 'mock-token', setAuth: vi.fn(), logout: vi.fn() }),
}))

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

/**
 * React 19's `use()` checks promise.status === 'fulfilled' to return
 * synchronously. A plain Promise.resolve() starts as 'pending' and suspends
 * on the first render even if already settled. Pre-annotating bypasses that.
 */
function makeReadyPromise<T>(value: T): Promise<T> {
  const p = Promise.resolve(value) as Promise<T> & { status?: string; value?: T }
  p.status = 'fulfilled'
  p.value = value
  return p
}

function renderPage(id = 'case-123') {
  return render(
    <Suspense fallback={<div>loading params</div>}>
      <CaseDetailPage params={makeReadyPromise({ id })} />
    </Suspense>,
  )
}

describe('CaseDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders Export PDF button', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      id: 'case-123',
      title: 'Caso de prueba',
      status: 'active',
      created_at: '2026-04-01T00:00:00Z',
      summary: null,
    })
    renderPage()
    expect(await screen.findByRole('button', { name: /exportar pdf/i })).toBeInTheDocument()
  })

  it('renders case title after data loads', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      id: 'case-123',
      title: 'Caso cardiovascular',
      status: 'resolved',
      created_at: '2026-04-01T00:00:00Z',
      summary: 'Paciente con hipertensión.',
    })
    renderPage()
    // Title appears in both h1 and CardTitle — assert on the heading specifically
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Caso cardiovascular'),
    )
  })

  it('shows TierUpgradeBanner when export returns tier_required 403', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      id: 'case-123',
      title: 'Caso',
      status: 'active',
      created_at: '2026-04-01T00:00:00Z',
      summary: null,
    })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({
          detail: {
            code: 'tier_required',
            required_tier: 'paid',
            current_tier: 'free',
          },
        }),
        blob: async () => new Blob(),
      }),
    )

    renderPage()

    const exportBtn = await screen.findByRole('button', { name: /exportar pdf/i })
    await userEvent.click(exportBtn)

    await waitFor(() =>
      expect(screen.getByText(/plan pagado/i)).toBeInTheDocument(),
    )
  })
})
