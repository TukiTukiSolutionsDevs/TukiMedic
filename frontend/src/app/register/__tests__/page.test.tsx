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
    await user.type(screen.getByLabelText(/contraseña/i), 'password123')
    await user.click(screen.getByRole('button', { name: /crear cuenta/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/ya está registrado/i)
  })
})
