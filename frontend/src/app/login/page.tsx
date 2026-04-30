'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, ApiError } from '@/lib/api'
import { useAuthStore } from '@/store/auth-store'

interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

/** Decode the JWT payload (base64url → JSON). No verification — client-side role routing only. */
function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(b64))
  } catch {
    return {}
  }
}

const AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7 // 7 days

function setAuthCookie() {
  // Companion cookie read by proxy.ts — does NOT carry the token, just a flag.
  if (typeof document === 'undefined') return
  document.cookie = `tuki-auth=1; Path=/; Max-Age=${AUTH_COOKIE_MAX_AGE}; SameSite=Strict${
    location.protocol === 'https:' ? '; Secure' : ''
  }`
}

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const data = await api.post<LoginResponse>(
        '/api/v1/auth/login',
        { email, password },
        { authenticated: false, skipRefresh: true },
      )

      const payload = decodeJwtPayload(data.access_token)
      const role = typeof payload.role === 'string' ? payload.role : 'customer'
      const subscriptionTier =
        typeof payload.subscription_tier === 'string' ? payload.subscription_tier : 'free'
      const userId = typeof payload.sub === 'string' ? payload.sub : ''

      setAuth(
        { id: userId, email, displayName: null, role, subscriptionTier },
        data.access_token,
        data.refresh_token,
      )
      setAuthCookie()

      const next = searchParams.get('next')
      const safeNext = next && next.startsWith('/') && !next.startsWith('//') ? next : null
      router.push(safeNext ?? (role === 'admin' ? '/admin' : '/chat'))
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setError('Demasiados intentos. Esperá un minuto e intentá de nuevo.')
        } else if (err.status === 401) {
          setError('Email o contraseña incorrectos.')
        } else if (err.status === 403) {
          setError('Cuenta deshabilitada. Contactá al administrador.')
        } else {
          setError('No pudimos iniciar sesión. Intentá de nuevo.')
        }
      } else {
        console.error('login failed', err)
        setError('No pudimos contactar al servidor. Revisá tu conexión.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="w-full max-w-sm space-y-6 p-8">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold">Iniciar sesión</h1>
          <p className="text-sm text-muted-foreground">
            Ingresá tus credenciales para acceder
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="tu@email.com"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium">
              Contraseña
            </label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
            />
          </div>

          {error && (
            <div
              role="alert"
              aria-live="polite"
              className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </div>
          )}

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={loading || !email || !password}
          >
            {loading ? 'Entrando…' : 'Entrar'}
          </Button>
        </form>
      </div>
    </div>
  )
}
