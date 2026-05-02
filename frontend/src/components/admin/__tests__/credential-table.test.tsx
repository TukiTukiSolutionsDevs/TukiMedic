import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { CredentialTable } from '@/components/admin/credential-table'

vi.mock('@/store/auth-store', () => ({
  useAuthStore: vi.fn(() => ({ accessToken: 'test-token' })),
}))

// Avoid base-ui portal issues in jsdom by providing simple pass-through mocks
vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({
    open,
    children,
  }: {
    open: boolean
    children: React.ReactNode
  }) => (open ? <div>{children}</div> : null),
  DialogContent: ({
    children,
    ...props
  }: { children: React.ReactNode } & Record<string, unknown>) => (
    <div {...props}>{children}</div>
  ),
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  DialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  DialogClose: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/components/ui/input', () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}))

vi.mock('@/components/ui/label', () => ({
  Label: ({
    children,
    ...props
  }: React.LabelHTMLAttributes<HTMLLabelElement> & { children: React.ReactNode }) => (
    <label {...props}>{children}</label>
  ),
}))

vi.mock('@/components/ui/button', () => ({
  Button: ({
    children,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: React.ReactNode }) => (
    <button {...props}>{children}</button>
  ),
}))

const mockCreds = [
  {
    id: 'cred-1',
    provider: 'gemini',
    label: 'Gemini Pro',
    is_active: true,
    created_at: '2024-01-01',
    rotated_at: null,
  },
  {
    id: 'cred-2',
    provider: 'openai',
    label: 'OpenAI GPT-4o',
    is_active: false,
    created_at: '2024-01-02',
    rotated_at: null,
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

describe('CredentialTable', () => {
  it('renders credentials list after load', async () => {
    stubFetch([{ ok: true, body: { items: mockCreds } }])
    render(<CredentialTable />)
    await waitFor(() =>
      expect(screen.getByTestId('credential-row-cred-1')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('credential-row-cred-2')).toBeInTheDocument()
    expect(screen.getByText('Gemini Pro')).toBeInTheDocument()
    expect(screen.getByText('OpenAI GPT-4o')).toBeInTheDocument()
  })

  it('shows empty state when no credentials', async () => {
    stubFetch([{ ok: true, body: { items: [] } }])
    render(<CredentialTable />)
    await waitFor(() =>
      expect(screen.getByTestId('credentials-empty')).toBeInTheDocument(),
    )
  })

  it('opens add dialog on button click', async () => {
    stubFetch([{ ok: true, body: { items: mockCreds } }])
    render(<CredentialTable />)
    await waitFor(() => screen.getByTestId('add-credential-btn'))
    fireEvent.click(screen.getByTestId('add-credential-btn'))
    expect(screen.getByTestId('add-credential-dialog')).toBeInTheDocument()
  })

  it('shows delete confirmation dialog before calling the API', async () => {
    stubFetch([{ ok: true, body: { items: mockCreds } }])
    render(<CredentialTable />)
    await waitFor(() => screen.getByTestId('delete-btn-cred-1'))

    fireEvent.click(screen.getByTestId('delete-btn-cred-1'))

    // Dialog should be visible, DELETE not yet called
    expect(screen.getByTestId('delete-credential-dialog')).toBeInTheDocument()
    expect(screen.getByTestId('confirm-delete-btn')).toBeInTheDocument()
  })

  it('calls DELETE only after confirmation', async () => {
    const mockFetch = stubFetch([
      { ok: true, body: { items: mockCreds } }, // initial load
      { ok: true, body: null },                  // DELETE
    ])
    render(<CredentialTable />)
    await waitFor(() => screen.getByTestId('delete-btn-cred-1'))

    // Click delete — dialog appears, API NOT called yet
    fireEvent.click(screen.getByTestId('delete-btn-cred-1'))
    expect(mockFetch).toHaveBeenCalledTimes(1)

    // Confirm delete
    fireEvent.click(screen.getByTestId('confirm-delete-btn'))
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/admin/credentials/cred-1'),
        expect.objectContaining({ method: 'DELETE' }),
      ),
    )
  })

  it('calls rotate endpoint on rotate button click', async () => {
    const mockFetch = stubFetch([
      { ok: true, body: { items: mockCreds } }, // initial load
      { ok: true, body: null },                  // rotate
      { ok: true, body: { items: mockCreds } }, // reload
    ])
    render(<CredentialTable />)
    await waitFor(() => screen.getByTestId('rotate-btn-cred-1'))

    fireEvent.click(screen.getByTestId('rotate-btn-cred-1'))
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/admin/credentials/cred-1/rotate'),
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })
})
