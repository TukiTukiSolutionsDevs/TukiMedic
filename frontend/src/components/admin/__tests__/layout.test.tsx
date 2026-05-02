import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AdminLayout from '@/app/admin/layout'
import { useAuthStore } from '@/store/auth-store'

const replaceMock = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
  usePathname: () => '/admin/audit',
}))

vi.mock('@/components/admin/sub-nav', () => ({
  AdminSubNav: () => <nav data-testid="admin-sub-nav" />,
}))

function seedUser(role = 'admin') {
  useAuthStore.setState({
    user: {
      id: 'u1',
      email: 'admin@test.com',
      displayName: null,
      role,
      subscriptionTier: 'paid',
    },
    accessToken: 'tok',
    refreshToken: 'ref',
    isAuthenticated: true,
  })
}

beforeEach(() => {
  replaceMock.mockReset()
  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
  })
})

describe('AdminLayout — role gate', () => {
  it('renders children for admin users', async () => {
    seedUser('admin')
    render(
      <AdminLayout>
        <div data-testid="page-content">content</div>
      </AdminLayout>,
    )
    await waitFor(() =>
      expect(screen.getByTestId('page-content')).toBeInTheDocument(),
    )
  })

  it('renders sub-nav for admin users', async () => {
    seedUser('admin')
    render(<AdminLayout><div /></AdminLayout>)
    await waitFor(() =>
      expect(screen.getByTestId('admin-sub-nav')).toBeInTheDocument(),
    )
  })

  it('redirects to /chat for authenticated non-admin', async () => {
    seedUser('customer')
    render(
      <AdminLayout>
        <div data-testid="page-content" />
      </AdminLayout>,
    )
    await waitFor(() =>
      expect(replaceMock).toHaveBeenCalledWith('/chat'),
    )
    expect(screen.queryByTestId('page-content')).not.toBeInTheDocument()
  })

  it('redirects to /login when unauthenticated', async () => {
    render(<AdminLayout><div /></AdminLayout>)
    await waitFor(() =>
      expect(replaceMock).toHaveBeenCalledWith('/login'),
    )
  })
})
