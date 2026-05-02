import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { VerifyChainButton } from '@/components/admin/verify-chain-button'

vi.mock('@/store/auth-store', () => ({
  useAuthStore: vi.fn(() => ({ accessToken: 'test-token' })),
}))

vi.mock('@/components/ui/button', () => ({
  Button: ({
    children,
    onClick,
    disabled,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: React.ReactNode }) => (
    <button onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}))

function stubFetch(ok: boolean, body: unknown) {
  const mockFetch = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(body),
  })
  vi.stubGlobal('fetch', mockFetch)
  return mockFetch
}

beforeEach(() => vi.unstubAllGlobals())
afterEach(() => vi.unstubAllGlobals())

describe('VerifyChainButton', () => {
  it('renders the verify button', () => {
    render(<VerifyChainButton />)
    expect(screen.getByTestId('verify-chain-btn')).toBeInTheDocument()
  })

  it('calls verify-chain endpoint on click', async () => {
    const mockFetch = stubFetch(true, { valid: true, total: 100 })
    render(<VerifyChainButton />)
    fireEvent.click(screen.getByTestId('verify-chain-btn'))
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/admin/audit/verify-chain'),
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        }),
      ),
    )
  })

  it('shows valid result when chain is intact', async () => {
    stubFetch(true, { valid: true, total: 9847 })
    render(<VerifyChainButton />)
    fireEvent.click(screen.getByTestId('verify-chain-btn'))
    await waitFor(() =>
      expect(screen.getByTestId('verify-chain-valid')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('verify-chain-valid')).toHaveTextContent('9847')
  })

  it('shows invalid result with broken_at when chain is broken', async () => {
    stubFetch(true, { valid: false, total: 500, broken_at: 42 })
    render(<VerifyChainButton />)
    fireEvent.click(screen.getByTestId('verify-chain-btn'))
    await waitFor(() =>
      expect(screen.getByTestId('verify-chain-invalid')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('verify-chain-invalid')).toHaveTextContent('42')
  })

  it('shows last-verified timestamp after successful verification', async () => {
    stubFetch(true, { valid: true, total: 100 })
    render(<VerifyChainButton />)
    fireEvent.click(screen.getByTestId('verify-chain-btn'))
    await waitFor(() =>
      expect(screen.getByTestId('last-verified')).toBeInTheDocument(),
    )
  })

  it('shows error message on non-ok response', async () => {
    stubFetch(false, null)
    render(<VerifyChainButton />)
    fireEvent.click(screen.getByTestId('verify-chain-btn'))
    await waitFor(() =>
      expect(screen.getByTestId('verify-chain-error')).toBeInTheDocument(),
    )
  })
})
