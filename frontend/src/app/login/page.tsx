'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useState, type FormEvent } from 'react'
import { Mail } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthLayout } from '@/components/auth/auth-layout'
import { PasswordField } from '@/components/auth/password-field'
import { api, ApiError } from '@/lib/api'
import { useAuthStore } from '@/store/auth-store'

interface LoginResponseUser {
  id: string
  email: string
  display_name: string | null
  is_verified: boolean
  role: string
  subscription_tier: string
}

interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user?: LoginResponseUser
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

function LoginForm() {
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

      // Prefer server-provided user payload; fall back to JWT decode if absent
      let role: string
      let subscriptionTier: string
      let userId: string
      let displayName: string | null

      if (data.user) {
        role = data.user.role
        subscriptionTier = data.user.subscription_tier
        userId = data.user.id
        displayName = data.user.display_name
      } else {
        const payload = decodeJwtPayload(data.access_token)
        role = typeof payload.role === 'string' ? payload.role : 'customer'
        subscriptionTier =
          typeof payload.subscription_tier === 'string' ? payload.subscription_tier : 'free'
        userId = typeof payload.sub === 'string' ? payload.sub : ''
        displayName = null
      }

      setAuth(
        { id: userId, email, displayName, role, subscriptionTier },
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
    <AuthLayout>
      <form onSubmit={handleSubmit} noValidate>
        <div style={{ marginBottom: 32 }}>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 600,
              margin: 0,
              letterSpacing: '-0.02em',
            }}
          >
            Bienvenido de vuelta
          </h1>
          <p className="text-sm" style={{ color: 'var(--tm-text-muted)', margin: '8px 0 0' }}>
            Inicia sesión para continuar tu consulta.
          </p>
        </div>

        <div className="space-y-4">
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

          {/* Password */}
          <PasswordField
            id="password"
            name="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading}
            autoComplete="current-password"
            minLength={8}
          />

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
            {loading ? 'Entrando…' : 'Entrar'}
          </Button>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px" style={{ background: 'var(--tm-border)' }} />
          <span className="text-xs" style={{ color: 'var(--tm-text-subtle)' }}>o</span>
          <div className="flex-1 h-px" style={{ background: 'var(--tm-border)' }} />
        </div>

        {/* Register link */}
        <p className="text-center text-sm" style={{ color: 'var(--tm-text-muted)' }}>
          ¿Es tu primera vez?{' '}
          <Link
            href="/register"
            className="font-medium underline-offset-4 hover:underline"
            style={{ color: 'var(--tm-blue-600)' }}
          >
            Crear cuenta
          </Link>
        </p>

        {/* Disclaimer */}
        <div
          className="mt-8 text-center text-xs leading-relaxed"
          style={{
            padding: 12,
            background: 'var(--tm-bg-soft)',
            borderRadius: 'var(--tm-radius-sm)',
            color: 'var(--tm-text-subtle)',
          }}
        >
          Al ingresar aceptás que TukiMedic{' '}
          <strong style={{ color: 'var(--tm-text-muted)' }}>no diagnostica ni receta</strong> —
          es orientación. En emergencia, llamá al{' '}
          <strong style={{ color: 'var(--tm-red-600)' }}>106 / SAMU</strong>.
        </div>
      </form>
    </AuthLayout>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
