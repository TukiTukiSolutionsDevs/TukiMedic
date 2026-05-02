import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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

vi.mock('@/store/auth-store', () => ({
  useAuthStore: vi.fn((selector?: (s: unknown) => unknown) => {
    const state = { user: { subscriptionTier: 'free' } }
    return typeof selector === 'function' ? selector(state) : state
  }),
}))

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
    expect(screen.getByRole('heading', { name: /mis casos/i })).toBeInTheDocument()
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled())
  })

  it('renders skeletons while loading', () => {
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

  it('shows empty state when no cases', async () => {
    vi.mocked(api.get).mockResolvedValueOnce([])
    render(<HistoryPage />)
    expect(await screen.findByText(/aún no tenés consultas/i)).toBeInTheDocument()
  })

  it('search filters the case list', async () => {
    vi.mocked(api.get).mockResolvedValueOnce([
      { id: '1', title: 'Fiebre alta', status: 'active', created_at: '2026-04-01T00:00:00Z' },
      { id: '2', title: 'Dolor de rodilla', status: 'resolved', created_at: '2026-04-01T00:00:00Z' },
    ])
    render(<HistoryPage />)
    await screen.findByText('Fiebre alta')
    fireEvent.change(screen.getByPlaceholderText(/buscar por motivo/i), {
      target: { value: 'rodilla' },
    })
    expect(screen.queryByText('Fiebre alta')).not.toBeInTheDocument()
    expect(screen.getByText('Dolor de rodilla')).toBeInTheDocument()
  })

  it('triage chip filters the case list', async () => {
    vi.mocked(api.get).mockResolvedValueOnce([
      { id: '1', title: 'Caso verde', triage_level: 'green', status: 'active', created_at: '2026-04-01T00:00:00Z' },
      { id: '2', title: 'Caso rojo', triage_level: 'red', status: 'active', created_at: '2026-04-01T00:00:00Z' },
    ])
    render(<HistoryPage />)
    await screen.findByText('Caso verde')
    fireEvent.click(screen.getByRole('button', { name: /rojo/i }))
    expect(screen.queryByText('Caso verde')).not.toBeInTheDocument()
    expect(screen.getByText('Caso rojo')).toBeInTheDocument()
  })

  it('pagination renders when case count exceeds page size', async () => {
    const manyCases = Array.from({ length: 11 }, (_, i) => ({
      id: `case-${i}`,
      title: `Caso ${i + 1}`,
      status: 'active',
      created_at: '2026-04-01T00:00:00Z',
    }))
    vi.mocked(api.get).mockResolvedValueOnce(manyCases)
    render(<HistoryPage />)
    await screen.findByText('Caso 1')
    expect(screen.getByLabelText('Página siguiente')).toBeInTheDocument()
    expect(screen.getByText(/mostrando 1.10 de 11/i)).toBeInTheDocument()
  })
})
