import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { UserTable } from '@/components/admin/user-table'

vi.mock('@/store/auth-store', () => ({
  useAuthStore: vi.fn(() => ({ accessToken: 'test-token' })),
}))

const mockUsers = [
  {
    id: 'user-1',
    email: 'admin@demo.pe',
    display_name: 'Admin Demo',
    role: 'admin',
    subscription_tier: 'paid',
    is_active: true,
    created_at: '2024-01-01',
  },
  {
    id: 'user-2',
    email: 'lucia@demo.pe',
    display_name: null,
    role: 'customer',
    subscription_tier: 'free',
    is_active: true,
    created_at: '2024-01-02',
  },
]

function stubFetch(responses: Array<{ ok: boolean; body: unknown }>) {
  let callCount = 0
  const mockFetch = vi.fn().mockImplementation(() => {
    const r = responses[callCount] ?? responses[responses.length - 1]
    callCount++
    return Promise.resolve({
      ok: r.ok,
      status: r.ok ? 200 : 500,
      json: () => Promise.resolve(r.body),
    })
  })
  vi.stubGlobal('fetch', mockFetch)
  return mockFetch
}

beforeEach(() => vi.unstubAllGlobals())
afterEach(() => vi.unstubAllGlobals())

describe('UserTable', () => {
  it('renders user rows after load', async () => {
    stubFetch([{ ok: true, body: { items: mockUsers, total: 2 } }])
    render(<UserTable />)
    await waitFor(() =>
      expect(screen.getByTestId('user-row-user-1')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('user-row-user-2')).toBeInTheDocument()
    expect(screen.getByText('admin@demo.pe')).toBeInTheDocument()
    expect(screen.getByText('lucia@demo.pe')).toBeInTheDocument()
  })

  it('shows empty state when no users', async () => {
    stubFetch([{ ok: true, body: { items: [], total: 0 } }])
    render(<UserTable />)
    await waitFor(() =>
      expect(screen.getByTestId('users-empty')).toBeInTheDocument(),
    )
  })

  it('renders search input', () => {
    stubFetch([{ ok: true, body: { items: [], total: 0 } }])
    render(<UserTable />)
    expect(screen.getByTestId('user-search')).toBeInTheDocument()
  })

  it('calls PATCH with new tier on tier select change', async () => {
    const mockFetch = stubFetch([
      { ok: true, body: { items: mockUsers, total: 2 } },
      { ok: true, body: { ...mockUsers[1], subscription_tier: 'paid' } },
    ])
    render(<UserTable />)
    await waitFor(() => screen.getByTestId('tier-select-user-2'))

    fireEvent.change(screen.getByTestId('tier-select-user-2'), {
      target: { value: 'paid' },
    })

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/admin/users/user-2'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ subscription_tier: 'paid' }),
        }),
      ),
    )
  })

  it('calls PATCH to toggle active status on status button click', async () => {
    const mockFetch = stubFetch([
      { ok: true, body: { items: mockUsers, total: 2 } },
      { ok: true, body: { ...mockUsers[1], is_active: false } },
    ])
    render(<UserTable />)
    await waitFor(() => screen.getByTestId('status-btn-user-2'))

    fireEvent.click(screen.getByTestId('status-btn-user-2'))

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/admin/users/user-2'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ is_active: false }),
        }),
      ),
    )
  })

  it('updates the row after a successful patch', async () => {
    stubFetch([
      { ok: true, body: { items: mockUsers, total: 2 } },
      { ok: true, body: { ...mockUsers[1], subscription_tier: 'paid' } },
    ])
    render(<UserTable />)
    await waitFor(() => screen.getByTestId('tier-select-user-2'))

    fireEvent.change(screen.getByTestId('tier-select-user-2'), {
      target: { value: 'paid' },
    })

    await waitFor(() => {
      const select = screen.getByTestId('tier-select-user-2') as HTMLSelectElement
      expect(select.value).toBe('paid')
    })
  })
})
