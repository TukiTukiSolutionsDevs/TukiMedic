import { Logo } from '@/components/logo'
import { Check, Heart, Shield } from 'lucide-react'

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div
      className="min-h-screen md:grid md:grid-cols-[1fr_1.05fr]"
      style={{ background: 'var(--tm-bg)' }}
    >
      {/* Left panel — brand, visible only on md+ */}
      <div
        data-testid="auth-brand-panel"
        className="hidden md:flex flex-col justify-between relative overflow-hidden"
        style={{ padding: '48px 56px', color: '#fff' }}
      >
        {/* Blue gradient */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(160deg, var(--tm-blue-700) 0%, var(--tm-blue-900) 50%, var(--tm-blue-950) 100%)',
          }}
        />
        {/* Radial glows */}
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage:
              'radial-gradient(circle at 20% 30%, rgba(252,211,77,0.15), transparent 40%), ' +
              'radial-gradient(circle at 80% 80%, rgba(96,165,250,0.2), transparent 40%)',
            pointerEvents: 'none',
          }}
        />
        {/* Grid overlay */}
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), ' +
              'linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
            backgroundSize: '32px 32px',
            maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
            pointerEvents: 'none',
          }}
        />

        {/* Logo — links back to home */}
        <div className="relative">
          <Logo size={44} asLink />
        </div>

        {/* Headline */}
        <div className="relative" style={{ maxWidth: 460 }}>
          <p
            style={{
              fontFamily: 'var(--font-instrument-serif)',
              fontSize: 52,
              lineHeight: 1.05,
              letterSpacing: '-0.02em',
              fontWeight: 400,
              margin: 0,
            }}
          >
            Diez especialistas{' '}
            <em style={{ color: 'var(--tm-yellow-300)', fontStyle: 'italic' }}>escuchando</em>{' '}
            tu consulta.
          </p>
          <p style={{ fontSize: 15, lineHeight: 1.55, marginTop: 24, opacity: 0.85 }}>
            Cuéntanos qué te pasa. Cardiología, neurología, pediatría y siete especialidades más
            analizan tu caso, deliberan en mesa médica y te entregan una orientación clara.
          </p>
        </div>

        {/* Trust badges */}
        <div className="relative flex gap-8" style={{ fontSize: 12, opacity: 0.75 }}>
          <span className="flex items-center gap-1.5">
            <Shield size={13} aria-hidden="true" />
            Audit chain SHA-256
          </span>
          <span className="flex items-center gap-1.5">
            <Check size={13} aria-hidden="true" />
            96% eval clínica
          </span>
          <span className="flex items-center gap-1.5">
            <Heart size={13} aria-hidden="true" />
            Hecho en Perú
          </span>
        </div>
      </div>

      {/* Right panel — form content */}
      <div
        className="flex items-center justify-center"
        style={{ padding: '48px 56px' }}
      >
        <div style={{ width: '100%', maxWidth: 400 }}>{children}</div>
      </div>
    </div>
  )
}
