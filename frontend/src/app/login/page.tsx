'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/store/auth-store'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export default function LoginPage() {
  const router = useRouter()
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
      const res = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      if (res.status === 429) {
        setError('Demasiados intentos. Esperá un minuto e intentá de nuevo.')
        return
      }

      if (!res.ok) {
        // 401 invalid creds, 422 validation error, 403 disabled — all surface as
        // a single user-friendly message. Detail is logged for the dev console.
        if (res.status === 401) {
          setError('Email o contraseña incorrectos.')
        } else if (res.status === 403) {
          setError('Cuenta deshabilitada. Contactá al administrador.')
        } else {
          setError('No pudimos iniciar sesión. Intentá de nuevo.')
        }
        return
      }

      const data = (await res.json()) as LoginResponse

      // The backend doesn't yet return a user object on /login. Derive a
      // minimal placeholder from the email until /auth/me is wired in.
      setAuth(
        { id: '', email, displayName: null },
        data.access_token,
      )

      router.push('/chat')
    } catch (err) {
      console.error('login failed', err)
      setError('No pudimos contactar al servidor. Revisá tu conexión.')
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
