import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'

import RegisterPage from '../page'

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
    selector({ setAuth: vi.fn(), setTokens: vi.fn(), logout: vi.fn() }),
}))

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders heading and submit button', () => {
    render(<RegisterPage />)
    expect(screen.getByRole('heading', { name: /crear cuenta/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /crear cuenta/i })).toBeInTheDocument()
  })

  it('submit button is disabled when email or password is empty', () => {
    render(<RegisterPage />)
    expect(screen.getByRole('button', { name: /crear cuenta/i })).toBeDisabled()
  })

  it('shows email-already-registered error on 400', async () => {
    const { api: mockApi, ApiError } = await import('@/lib/api')
    vi.mocked(mockApi.post).mockRejectedValueOnce(
      new ApiError(400, 'Email already registered', { detail: 'Email already registered' }),
    )
    const user = userEvent.setup()
    render(<RegisterPage />)
    await user.type(screen.getByLabelText(/email/i), 'existing@test.com')
    // { selector: 'input' } avoids conflict with eye-toggle button aria-label
    await user.type(screen.getByLabelText(/contraseña/i, { selector: 'input' }), 'password123')
    await user.click(screen.getByRole('button', { name: /crear cuenta/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/ya está registrado/i)
  })

  it('brand panel is rendered in the DOM', () => {
    render(<RegisterPage />)
    expect(screen.getByTestId('auth-brand-panel')).toBeInTheDocument()
  })

  it('eye toggle reveals password input', async () => {
    const user = userEvent.setup()
    render(<RegisterPage />)

    const passwordInput = screen.getByLabelText(/contraseña/i, { selector: 'input' })
    expect(passwordInput).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: /mostrar contraseña/i }))
    expect(passwordInput).toHaveAttribute('type', 'text')

    await user.click(screen.getByRole('button', { name: /ocultar contraseña/i }))
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('password strength indicator appears when password is typed', async () => {
    const user = userEvent.setup()
    render(<RegisterPage />)

    expect(screen.queryByTestId('pwd-strength')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText(/contraseña/i, { selector: 'input' }), 'abc')
    expect(screen.getByTestId('pwd-strength')).toBeInTheDocument()
  })

  it('link to login page is present', () => {
    render(<RegisterPage />)
    expect(screen.getByRole('link', { name: /iniciá sesión/i })).toBeInTheDocument()
  })
})
