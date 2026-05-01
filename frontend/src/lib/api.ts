/**
 * Centralized API client.
 *
 * Responsibilities:
 * - Single source of truth for the base URL
 * - Automatic Bearer header injection from the auth store
 * - One-shot transparent token refresh on 401
 * - Consistent error type for callers (so each page doesn't reinvent it)
 *
 * Usage:
 *   const docs = await api.get<Document[]>('/api/v1/documents/')
 *   await api.delete(`/api/v1/documents/${id}`)
 */
import { useAuthStore } from '@/store/auth-store'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  body: unknown
  /** Extracted from body.detail.code when the detail is an object. */
  code: string | undefined
  constructor(status: number, message: string, body: unknown, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.code = code
  }
}

interface RequestOptions extends RequestInit {
  /** If true, do not attempt token refresh on 401 (used by the refresh call itself). */
  skipRefresh?: boolean
  /** If false, do not send the Authorization header even when a token is in the store. */
  authenticated?: boolean
}

let inflightRefresh: Promise<boolean> | null = null

/** Refresh the access/refresh tokens. Returns true on success. */
async function refreshTokens(): Promise<boolean> {
  if (inflightRefresh) return inflightRefresh

  const refreshToken = useAuthStore.getState().refreshToken
  if (!refreshToken) return false

  inflightRefresh = (async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) return false
      const data = (await res.json()) as {
        access_token: string
        refresh_token: string
      }
      useAuthStore.getState().setTokens(data.access_token, data.refresh_token)
      return true
    } catch {
      return false
    } finally {
      inflightRefresh = null
    }
  })()

  return inflightRefresh
}

async function rawRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { skipRefresh, authenticated = true, ...init } = options

  const headers = new Headers(init.headers)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json')
  }
  if (authenticated) {
    const token = useAuthStore.getState().accessToken
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }

  const url = path.startsWith('http') ? path : `${API_URL}${path}`
  const res = await fetch(url, { ...init, headers })

  if (res.status === 401 && authenticated && !skipRefresh) {
    const refreshed = await refreshTokens()
    if (refreshed) {
      // Retry once with the new token.
      const retryHeaders = new Headers(headers)
      const newToken = useAuthStore.getState().accessToken
      if (newToken) retryHeaders.set('Authorization', `Bearer ${newToken}`)
      const retryRes = await fetch(url, { ...init, headers: retryHeaders })
      return parseResponse<T>(retryRes)
    }
    // Refresh failed — log out and let the proxy redirect on next nav.
    useAuthStore.getState().logout()
  }

  return parseResponse<T>(res)
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as unknown as T

  const ct = res.headers.get('content-type') ?? ''
  const body = ct.includes('application/json')
    ? await res.json().catch(() => null)
    : await res.text()

  if (!res.ok) {
    let message: string
    let code: string | undefined
    if (typeof body === 'object' && body !== null && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'object' && detail !== null) {
        const d = detail as Record<string, unknown>
        code = typeof d.code === 'string' ? d.code : undefined
        message =
          typeof d.message === 'string'
            ? d.message
            : code ?? JSON.stringify(detail)
      } else {
        message = String(detail)
      }
    } else {
      message = `Request failed: ${res.status}`
    }
    throw new ApiError(res.status, message, body, code)
  }

  return body as T
}

export const api = {
  get<T>(path: string, options?: RequestOptions) {
    return rawRequest<T>(path, { ...options, method: 'GET' })
  },
  post<T>(path: string, body?: unknown, options?: RequestOptions) {
    return rawRequest<T>(path, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
    })
  },
  put<T>(path: string, body?: unknown, options?: RequestOptions) {
    return rawRequest<T>(path, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(body ?? {}),
    })
  },
  delete<T = void>(path: string, options?: RequestOptions) {
    return rawRequest<T>(path, { ...options, method: 'DELETE' })
  },
}

export const API_BASE_URL = API_URL
