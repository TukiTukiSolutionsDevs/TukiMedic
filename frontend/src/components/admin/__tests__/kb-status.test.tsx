import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { KBStatus } from '@/components/admin/kb-status'

vi.mock('@/store/auth-store', () => ({
  useAuthStore: vi.fn(() => ({ accessToken: 'test-token' })),
}))

const mockStats = {
  total: 9234,
  by_source: [
    { source: 'pubmed',      count: 6480 },
    { source: 'medlineplus', count: 2754 },
  ],
}

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

describe('KBStatus', () => {
  it('renders the reindex button', () => {
    stubFetch([{ ok: true, body: mockStats }])
    render(<KBStatus />)
    expect(screen.getByTestId('reindex-btn')).toBeInTheDocument()
  })

  it('displays total chunk count from stats', async () => {
    stubFetch([{ ok: true, body: mockStats }])
    render(<KBStatus />)
    await waitFor(() =>
      expect(screen.getByText('9234')).toBeInTheDocument(),
    )
  })

  it('calls ingest endpoint on reindex button click', async () => {
    const mockFetch = stubFetch([
      { ok: true, body: mockStats },
      { ok: true, body: {} },
    ])
    render(<KBStatus />)
    fireEvent.click(screen.getByTestId('reindex-btn'))
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/admin/kb/ingest'),
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('shows success message after reindex', async () => {
    stubFetch([
      { ok: true, body: mockStats },
      { ok: true, body: {} },
    ])
    render(<KBStatus />)
    fireEvent.click(screen.getByTestId('reindex-btn'))
    await waitFor(() =>
      expect(screen.getByTestId('ingest-success')).toBeInTheDocument(),
    )
  })

  it('shows all source labels in the sources list', async () => {
    stubFetch([{ ok: true, body: mockStats }])
    render(<KBStatus />)
    // PubMed and WHO also appear in the stats row header, so use getAllByText
    expect(screen.getAllByText('PubMed').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('WHO').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('LiverTox')).toBeInTheDocument()
    expect(screen.getByText('MedlinePlus')).toBeInTheDocument()
  })
})
