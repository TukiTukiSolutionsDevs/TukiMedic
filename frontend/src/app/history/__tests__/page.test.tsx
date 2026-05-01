import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'

import HistoryPage from '../page'
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

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders heading', async () => {
    vi.mocked(api.get).mockResolvedValueOnce([])
    render(<HistoryPage />)
    expect(screen.getByRole('heading', { name: /historial/i })).toBeInTheDocument()
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled())
  })

  it('renders skeletons while loading', () => {
    // Promise that never resolves — keeps the component in loading state
    vi.mocked(api.get).mockImplementation(() => new Promise(() => {}))
    render(<HistoryPage />)
    expect(document.querySelector('[data-slot="skeleton"]')).toBeInTheDocument()
  })

  it('shows TierUpgradeBanner on tier_required 403', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(
      new ApiError(403, 'tier_required', {
        detail: {
          code: 'tier_required',
          required_tier: 'paid',
          current_tier: 'free',
        },
      }),
    )
    render(<HistoryPage />)
    await waitFor(() =>
      expect(screen.getByText(/plan pagado/i)).toBeInTheDocument(),
    )
  })

  it('renders case cards after successful fetch', async () => {
    vi.mocked(api.get).mockResolvedValueOnce([
      {
        id: 'abc-123',
        title: 'Caso de prueba',
        status: 'active',
        created_at: '2026-04-01T00:00:00Z',
      },
    ])
    render(<HistoryPage />)
    expect(await screen.findByText('Caso de prueba')).toBeInTheDocument()
  })
})
