/**
 * LoginPage tests — characterize the current behavior so any future
 * refactor (e.g. moving to a hook, adding tier-aware error handling)
 * can be done safely.
 *
 * Covered:
 * 1. happy path: POST → tokens stored, cookie set, router.push to /chat
 * 2. admin role routes to /admin
 * 3. 401 maps to "Email o contraseña incorrectos"
 * 4. 403 maps to "Cuenta deshabilitada"
 * 5. 429 maps to rate limit message
 * 6. network error maps to connectivity message
 * 7. brand panel is rendered in the DOM
 * 8. eye toggle reveals password input
 * 9. link to register page is present
 * 10. link back to home is present
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import LoginPage from './page'
import { ApiError } from '@/lib/api'
import { useAuthStore } from '@/store/auth-store'

// Mock the api module — we don't want real network calls.
const mockPost = vi.fn()
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    api: { post: (...args: unknown[]) => mockPost(...args) },
  }
})

// Capture router.push calls.
const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))

// Reset zustand store between tests so state doesn't leak.
const initialAuth = useAuthStore.getState()
beforeEach(() => {
  mockPost.mockReset()
  mockPush.mockReset()
  useAuthStore.setState(initialAuth, true)
  document.cookie = 'tuki-auth=; Path=/; Max-Age=0'
})

afterEach(() => {
  document.cookie = 'tuki-auth=; Path=/; Max-Age=0'
})

const VALID_LOGIN_RESPONSE = {
  access_token: 'access-jwt-token',
  refresh_token: 'refresh-jwt-token',
  token_type: 'bearer',
  user: {
    id: 'usr_1',
    email: 'cliente@tuki.dev',
    display_name: 'Lucía Q.',
    is_verified: true,
    role: 'customer',
    subscription_tier: 'free',
  },
}

// { selector: 'input' } avoids ambiguity with the eye-toggle button whose
// aria-label also contains "contraseña".
async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText(/email/i), email)
  await user.type(screen.getByLabelText(/contraseña/i, { selector: 'input' }), password)
  await user.click(screen.getByRole('button', { name: /entrar/i }))
}

describe('LoginPage', () => {
  it('happy path: stores auth, sets cookie, routes customer to /chat', async () => {
    mockPost.mockResolvedValueOnce(VALID_LOGIN_RESPONSE)
    render(<LoginPage />)

    await fillAndSubmit('cliente@tuki.dev', 'Cliente1234!')

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/chat'))

    const auth = useAuthStore.getState()
    expect(auth.accessToken).toBe('access-jwt-token')
    expect(auth.refreshToken).toBe('refresh-jwt-token')
    expect(auth.user).toMatchObject({
      id: 'usr_1',
      email: 'cliente@tuki.dev',
      role: 'customer',
      subscriptionTier: 'free',
    })
    expect(document.cookie).toContain('tuki-auth=1')
  })

  it('routes admin role to /admin instead of /chat', async () => {
    mockPost.mockResolvedValueOnce({
      ...VALID_LOGIN_RESPONSE,
      user: { ...VALID_LOGIN_RESPONSE.user, role: 'admin' },
    })
    render(<LoginPage />)

    await fillAndSubmit('admin@tuki.dev', 'Admin1234!')

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/admin'))
  })

  it('401 shows "Email o contraseña incorrectos"', async () => {
    mockPost.mockRejectedValueOnce(
      new ApiError(401, 'Invalid credentials', { detail: 'Invalid credentials' }),
    )
    render(<LoginPage />)

    await fillAndSubmit('x@x.com', 'wrongpassword')

    expect(
      await screen.findByText(/email o contraseña incorrectos/i),
    ).toBeInTheDocument()
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('403 shows "Cuenta deshabilitada"', async () => {
    mockPost.mockRejectedValueOnce(
      new ApiError(403, 'Account disabled', { detail: 'Account disabled' }),
    )
    render(<LoginPage />)

    await fillAndSubmit('disabled@x.com', 'somepassword')

    expect(await screen.findByText(/cuenta deshabilitada/i)).toBeInTheDocument()
  })

  it('429 shows rate limit message', async () => {
    mockPost.mockRejectedValueOnce(
      new ApiError(429, 'Too many requests', { detail: 'rate limited' }),
    )
    render(<LoginPage />)

    await fillAndSubmit('x@x.com', 'somepassword')

    expect(await screen.findByText(/demasiados intentos/i)).toBeInTheDocument()
  })

  it('network failure shows connectivity message', async () => {
    mockPost.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    render(<LoginPage />)

    await fillAndSubmit('x@x.com', 'somepassword')

    expect(
      await screen.findByText(/no pudimos contactar al servidor/i),
    ).toBeInTheDocument()
  })

  it('brand panel is rendered in the DOM', () => {
    render(<LoginPage />)
    expect(screen.getByTestId('auth-brand-panel')).toBeInTheDocument()
  })

  it('eye toggle reveals password input', async () => {
    const user = userEvent.setup()
    render(<LoginPage />)

    const passwordInput = screen.getByLabelText(/contraseña/i, { selector: 'input' })
    expect(passwordInput).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: /mostrar contraseña/i }))
    expect(passwordInput).toHaveAttribute('type', 'text')

    await user.click(screen.getByRole('button', { name: /ocultar contraseña/i }))
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('link to register page is present', () => {
    render(<LoginPage />)
    expect(screen.getByRole('link', { name: /crear cuenta/i })).toBeInTheDocument()
  })

  it('link back to home is present via logo', () => {
    render(<LoginPage />)
    expect(screen.getByRole('link', { name: /tukimedic/i })).toBeInTheDocument()
  })
})
