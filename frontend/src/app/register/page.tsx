'use client'

import Link from 'next/link'
import { useState, useMemo, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { Mail } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthLayout } from '@/components/auth/auth-layout'
import { PasswordField } from '@/components/auth/password-field'
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

const PWD_STRENGTH_COLORS = [
  'var(--tm-red-500)',
  'var(--tm-red-500)',
  'var(--tm-amber-500)',
  'var(--tm-green-500)',
  'var(--tm-green-500)',
]

export default function RegisterPage() {
  const router = useRouter()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const pwdStrength = useMemo(() => {
    const p = password
    let s = 0
    if (p.length >= 8) s++
    if (/[A-Z]/.test(p)) s++
    if (/[0-9]/.test(p)) s++
    if (/[^A-Za-z0-9]/.test(p)) s++
    return s
  }, [password])

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
    <AuthLayout>
      <form onSubmit={handleSubmit} noValidate>
        <div style={{ marginBottom: 28 }}>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 600,
              margin: 0,
              letterSpacing: '-0.02em',
            }}
          >
            Crear cuenta
          </h1>
          <p className="text-sm" style={{ color: 'var(--tm-text-muted)', margin: '8px 0 0' }}>
            Tu salud, en buenas manos. Es gratis.
          </p>
        </div>

        <div className="space-y-4">
          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Nombre</Label>
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

          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <div className="relative">
              <Mail
                size={16}
                aria-hidden="true"
                className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                style={{ color: 'var(--tm-text-subtle)' }}
              />
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
                className="pl-9"
              />
            </div>
          </div>

          {/* Password + strength meter */}
          <div>
            <PasswordField
              id="password"
              name="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              autoComplete="new-password"
              minLength={8}
              placeholder="Mínimo 8 caracteres"
            />
            {password.length > 0 && (
              <div
                data-testid="pwd-strength"
                className="flex gap-1 mt-2"
                aria-label={`Fortaleza de contraseña: ${pwdStrength} de 4`}
              >
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    style={{
                      flex: 1,
                      height: 4,
                      borderRadius: 2,
                      background:
                        pwdStrength >= i
                          ? PWD_STRENGTH_COLORS[pwdStrength]
                          : 'var(--tm-border)',
                      transition: 'background 0.2s',
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Error */}
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
        </div>

        {/* Login link */}
        <p className="text-center text-sm mt-6" style={{ color: 'var(--tm-text-muted)' }}>
          ¿Ya tenés cuenta?{' '}
          <Link
            href="/login"
            className="font-medium underline-offset-4 hover:underline"
            style={{ color: 'var(--tm-blue-600)' }}
          >
            Iniciá sesión
          </Link>
        </p>
      </form>
    </AuthLayout>
  )
}
