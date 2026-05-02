import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'

import DashboardPage from '@/app/dashboard/page'
import { useAuthStore } from '@/store/auth-store'
import { api } from '@/lib/api'

vi.mock('@/store/auth-store', () => ({
  useAuthStore: vi.fn(),
}))

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

const FREE_USER = {
  id: '1',
  email: 'ana@tuki.com',
  displayName: 'Ana García',
  role: 'user',
  subscriptionTier: 'free',
}

const PAID_USER = { ...FREE_USER, subscriptionTier: 'paid' }

function mockAuth(user = FREE_USER) {
  vi.mocked(useAuthStore).mockImplementation(
    (selector?: (s: unknown) => unknown) => {
      const state = {
        user,
        accessToken: 'tok',
        refreshToken: 'ref',
        isAuthenticated: true,
      }
      return typeof selector === 'function' ? selector(state) : state
    },
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
    // Default: API returns empty list (no mock fallback triggered)
    vi.mocked(api.get).mockResolvedValue([])
  })

  it('renders greeting with displayName', async () => {
    render(<DashboardPage />)
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled())
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent(/Ana/)
  })

  it('renders greeting using email prefix when displayName is null', async () => {
    mockAuth({ ...FREE_USER, displayName: null })
    render(<DashboardPage />)
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled())
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent(/ana/i)
  })

  it('"Nueva consulta" CTA links to /chat', () => {
    render(<DashboardPage />)
    const link = screen.getByRole('link', { name: /nueva consulta/i })
    expect(link).toHaveAttribute('href', '/chat')
  })

  it('renders skeletons while loading', () => {
    vi.mocked(api.get).mockImplementation(() => new Promise(() => {}))
    render(<DashboardPage />)
    expect(document.querySelector('[data-slot="skeleton"]')).toBeInTheDocument()
  })

  it('renders case cards after successful fetch', async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: 'c1',
        title: 'Dolor de rodilla',
        chief_complaint: 'Me duele la rodilla.',
        triage_level: 'yellow',
        created_at: '2026-04-20T10:00:00Z',
        status: 'resolved',
      },
    ])
    render(<DashboardPage />)
    expect(await screen.findByText('Dolor de rodilla')).toBeInTheDocument()
  })

  it('renders a triage dot for each case', async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: 'c1',
        title: 'Caso verde',
        triage_level: 'green',
        created_at: '2026-04-20T10:00:00Z',
        status: 'resolved',
      },
      {
        id: 'c2',
        title: 'Caso amarillo',
        triage_level: 'yellow',
        created_at: '2026-04-21T10:00:00Z',
        status: 'resolved',
      },
    ])
    render(<DashboardPage />)
    await waitFor(() =>
      expect(screen.getAllByTestId('triage-dot').length).toBe(2),
    )
  })

  it('renders empty state when API returns no cases', async () => {
    vi.mocked(api.get).mockResolvedValue([])
    render(<DashboardPage />)
    expect(await screen.findByTestId('empty-state')).toBeInTheDocument()
  })

  it('shows TierUpgradeBanner for free-tier user', async () => {
    mockAuth(FREE_USER)
    render(<DashboardPage />)
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled())
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('does not show TierUpgradeBanner for paid-tier user', async () => {
    mockAuth(PAID_USER)
    render(<DashboardPage />)
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('stats row renders total, routine and urgent counts', async () => {
    vi.mocked(api.get).mockResolvedValue([
      {
        id: 'c1',
        title: 'Caso 1',
        triage_level: 'green',
        created_at: '2026-04-01T00:00:00Z',
        status: 'resolved',
      },
      {
        id: 'c2',
        title: 'Caso 2',
        triage_level: 'yellow',
        created_at: '2026-04-02T00:00:00Z',
        status: 'resolved',
      },
      {
        id: 'c3',
        title: 'Caso 3',
        triage_level: 'red',
        created_at: '2026-04-03T00:00:00Z',
        status: 'resolved',
      },
    ])
    render(<DashboardPage />)
    const values = await screen.findAllByTestId('stat-value')
    const texts = values.map((v) => v.textContent)
    expect(texts).toContain('3') // total
    expect(texts).toContain('1') // routine (green only)
    expect(texts).toContain('2') // urgent (yellow + red)
  })

  it('quick actions link to /history, /upload and /settings', async () => {
    render(<DashboardPage />)
    await waitFor(() => expect(vi.mocked(api.get)).toHaveBeenCalled())
    expect(
      screen.getByRole('link', { name: /historial/i }),
    ).toHaveAttribute('href', '/history')
    expect(
      screen.getByRole('link', { name: /documentos/i }),
    ).toHaveAttribute('href', '/upload')
    expect(
      screen.getByRole('link', { name: /perfil/i }),
    ).toHaveAttribute('href', '/settings')
  })
})
