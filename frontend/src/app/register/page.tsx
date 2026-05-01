'use client'

import { useState, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, ApiError } from '@/lib/api'
import { useAuthStore } from '@/store/auth-store'

interface TokenResponse {
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

export default function RegisterPage() {
  const router = useRouter()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const data = await api.post<TokenResponse>(
        '/api/v1/auth/register',
        { email, password, display_name: displayName || null },
        { authenticated: false, skipRefresh: true },
      )

      const payload = decodeJwtPayload(data.access_token)
      const role = typeof payload.role === 'string' ? payload.role : 'customer'
      const subscriptionTier =
        typeof payload.subscription_tier === 'string' ? payload.subscription_tier : 'free'
      const userId = typeof payload.sub === 'string' ? payload.sub : ''

      setAuth(
        { id: userId, email, displayName: displayName || null, role, subscriptionTier },
        data.access_token,
        data.refresh_token,
      )

      router.push('/chat')
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 400) {
          setError('El email ya está registrado.')
        } else if (err.status === 429) {
          setError('Demasiados intentos. Esperá un momento e intentá de nuevo.')
        } else {
          setError('No pudimos crear la cuenta. Intentá de nuevo.')
        }
      } else {
        console.error('register failed', err)
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
          <h1 className="text-2xl font-bold">Crear cuenta</h1>
          <p className="text-sm text-muted-foreground">
            Completá los datos para registrarte
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="space-y-2">
            <label htmlFor="name" className="text-sm font-medium">
              Nombre
            </label>
            <Input
              id="name"
              name="name"
              type="text"
              autoComplete="name"
              placeholder="Tu nombre"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              disabled={loading}
            />
          </div>

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
              autoComplete="new-password"
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
            {loading ? 'Creando cuenta…' : 'Crear cuenta'}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          ¿Ya tenés cuenta?{' '}
          <a href="/login" className="underline underline-offset-4 hover:text-foreground">
            Iniciá sesión
          </a>
        </p>
      </div>
    </div>
  )
}
