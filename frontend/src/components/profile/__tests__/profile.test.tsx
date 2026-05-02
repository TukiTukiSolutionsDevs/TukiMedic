import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'

import SettingsPage from '@/app/settings/page'
import { AccountTab } from '@/components/profile/account-tab'
import { HealthTab } from '@/components/profile/health-tab'
import { PrivacyTab } from '@/components/profile/privacy-tab'
import { DeleteAccountDialog } from '@/components/profile/delete-account-dialog'
import { useAuthStore } from '@/store/auth-store'
import { api } from '@/lib/api'

// Bypass portal / animation complexity — test behaviour, not base-ui internals.
vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open?: boolean }) =>
    open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
  DialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  DialogClose: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  DialogOverlay: () => null,
  DialogPortal: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

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

const mockLogout = vi.fn()

function mockAuth(user = FREE_USER) {
  vi.mocked(useAuthStore).mockImplementation(
    (selector?: (s: unknown) => unknown) => {
      const state = {
        user,
        accessToken: 'tok',
        refreshToken: 'ref',
        isAuthenticated: true,
        logout: mockLogout,
      }
      return typeof selector === 'function' ? selector(state) : state
    },
  )
}

// ---------------------------------------------------------------------------
// SettingsPage
// ---------------------------------------------------------------------------

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
  })

  it('renders three tab triggers', () => {
    render(<SettingsPage />)
    expect(screen.getByText('Mi cuenta')).toBeInTheDocument()
    expect(screen.getByText('Mi salud')).toBeInTheDocument()
    expect(screen.getByText('Privacidad y datos')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// AccountTab
// ---------------------------------------------------------------------------

describe('AccountTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
  })

  it('shows the email as a read-only input', () => {
    render(<AccountTab />)
    const emailInput = screen.getByLabelText(/email/i)
    expect(emailInput).toHaveValue('ana@tuki.com')
    expect(emailInput).toHaveAttribute('readonly')
  })

  it('shows displayName pre-filled in the name input', () => {
    render(<AccountTab />)
    expect(screen.getByDisplayValue('Ana García')).toBeInTheDocument()
  })

  it('shows "Plan Gratuito" badge for free-tier user', () => {
    render(<AccountTab />)
    expect(screen.getByTestId('tier-badge')).toHaveTextContent('Plan Gratuito')
  })

  it('shows "Tuki Pro" badge for paid-tier user', () => {
    mockAuth(PAID_USER)
    render(<AccountTab />)
    expect(screen.getByTestId('tier-badge')).toHaveTextContent('Tuki Pro')
  })

  it('shows upgrade CTA for free user and hides it for paid user', () => {
    const { unmount } = render(<AccountTab />)
    expect(screen.getByRole('button', { name: /mejorar a pro/i })).toBeInTheDocument()
    unmount()

    mockAuth(PAID_USER)
    render(<AccountTab />)
    expect(screen.queryByRole('button', { name: /mejorar a pro/i })).not.toBeInTheDocument()
  })

  it('calls authStore.logout when logout button is clicked', () => {
    render(<AccountTab />)
    fireEvent.click(screen.getByRole('button', { name: /cerrar sesión/i }))
    expect(mockLogout).toHaveBeenCalledOnce()
  })
})

// ---------------------------------------------------------------------------
// HealthTab
// ---------------------------------------------------------------------------

describe('HealthTab', () => {
  it('can add an allergy chip', () => {
    render(<HealthTab />)
    const input = screen.getByRole('textbox', { name: /nueva entrada de alergias/i })
    fireEvent.change(input, { target: { value: 'Penicilina' } })
    fireEvent.click(screen.getByRole('button', { name: /agregar alergias/i }))
    expect(screen.getByText('Penicilina')).toBeInTheDocument()
  })

  it('renders chips with an X remove button', () => {
    render(<HealthTab />)
    const input = screen.getByRole('textbox', { name: /nueva entrada de alergias/i })
    fireEvent.change(input, { target: { value: 'Polen' } })
    fireEvent.click(screen.getByRole('button', { name: /agregar alergias/i }))
    expect(screen.getByRole('button', { name: /quitar Polen/i })).toBeInTheDocument()
  })

  it('can remove an allergy chip', () => {
    render(<HealthTab />)
    const input = screen.getByRole('textbox', { name: /nueva entrada de alergias/i })
    fireEvent.change(input, { target: { value: 'Mariscos' } })
    fireEvent.click(screen.getByRole('button', { name: /agregar alergias/i }))
    fireEvent.click(screen.getByRole('button', { name: /quitar Mariscos/i }))
    expect(screen.queryByText('Mariscos')).not.toBeInTheDocument()
  })

  it('renders the medication and conditions sections', () => {
    render(<HealthTab />)
    expect(screen.getByText(/medicación activa/i)).toBeInTheDocument()
    expect(screen.getByText(/condiciones crónicas/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// PrivacyTab
// ---------------------------------------------------------------------------

describe('PrivacyTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
  })

  it('shows the GDPR data export section', () => {
    render(<PrivacyTab />)
    expect(screen.getByRole('button', { name: /descargar mis datos/i })).toBeInTheDocument()
  })

  it('shows the delete account trigger button', () => {
    render(<PrivacyTab />)
    expect(screen.getByRole('button', { name: /eliminar mi cuenta/i })).toBeInTheDocument()
  })

  it('describes what data is stored', () => {
    render(<PrivacyTab />)
    expect(document.body).toHaveTextContent(/guardamos/i)
  })
})

// ---------------------------------------------------------------------------
// DeleteAccountDialog
// ---------------------------------------------------------------------------

describe('DeleteAccountDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth()
    vi.mocked(api.delete).mockResolvedValue(undefined)
  })

  it('confirm button is disabled when the input is empty', () => {
    render(<DeleteAccountDialog open={true} onOpenChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: /confirmar eliminación/i })).toBeDisabled()
  })

  it('confirm button is disabled when the typed text does not match (case-sensitive)', () => {
    render(<DeleteAccountDialog open={true} onOpenChange={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText('ELIMINAR'), {
      target: { value: 'eliminar' },
    })
    expect(screen.getByRole('button', { name: /confirmar eliminación/i })).toBeDisabled()
  })

  it('confirm button is enabled after typing ELIMINAR exactly', () => {
    render(<DeleteAccountDialog open={true} onOpenChange={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText('ELIMINAR'), {
      target: { value: 'ELIMINAR' },
    })
    expect(screen.getByRole('button', { name: /confirmar eliminación/i })).toBeEnabled()
  })

  it('calls api.delete and logout when confirmed', async () => {
    render(<DeleteAccountDialog open={true} onOpenChange={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText('ELIMINAR'), {
      target: { value: 'ELIMINAR' },
    })
    fireEvent.click(screen.getByRole('button', { name: /confirmar eliminación/i }))
    await waitFor(() => {
      expect(vi.mocked(api.delete)).toHaveBeenCalledWith('/api/v1/auth/me')
      expect(mockLogout).toHaveBeenCalledOnce()
    })
  })
})
