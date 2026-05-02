'use client'

import { useState } from 'react'
import { CheckCircle2, AlertCircle, RotateCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

interface AuditChainStatus {
  valid: boolean
  total: number
  broken_at?: number
}

export function VerifyChainButton() {
  const { accessToken } = useAuthStore()
  const [loading, setLoading]           = useState(false)
  const [result, setResult]             = useState<AuditChainStatus | null>(null)
  const [lastVerified, setLastVerified] = useState<Date | null>(null)
  const [fetchError, setFetchError]     = useState<string | null>(null)

  const verify = async () => {
    setLoading(true)
    setFetchError(null)
    try {
      const res = await fetch(`${API}/api/v1/admin/audit/verify-chain`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: AuditChainStatus = await res.json()
      setResult(data)
      setLastVerified(new Date())
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          data-testid="verify-chain-btn"
          onClick={verify}
          disabled={loading}
          size="sm"
        >
          <RotateCw size={14} className={loading ? 'animate-spin' : ''} />
          {loading ? 'Verificando…' : 'Verificar cadena ahora'}
        </Button>
        {lastVerified && (
          <span
            data-testid="last-verified"
            className="text-xs text-muted-foreground"
          >
            Ultima verificacion: {lastVerified.toLocaleTimeString('es-AR')}
          </span>
        )}
      </div>

      {fetchError && (
        <div
          data-testid="verify-chain-error"
          className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          <AlertCircle size={15} /> {fetchError}
        </div>
      )}

      {result && !fetchError && (
        result.valid ? (
          <div
            data-testid="verify-chain-valid"
            className="flex items-center gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3 dark:border-green-800 dark:bg-green-950"
          >
            <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
            <span className="text-sm font-medium text-green-700 dark:text-green-300">
              Cadena integra &middot; {result.total} registros
            </span>
          </div>
        ) : (
          <div
            data-testid="verify-chain-invalid"
            className="flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950"
          >
            <AlertCircle size={20} className="text-red-600 dark:text-red-400" />
            <span className="text-sm font-medium text-red-700 dark:text-red-300">
              Cadena rota en posicion {result.broken_at}
            </span>
          </div>
        )
      )}
    </div>
  )
}
