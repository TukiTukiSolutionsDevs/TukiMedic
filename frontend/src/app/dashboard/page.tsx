'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

interface Metrics {
  total_cases: number
  total_users: number
  total_documents: number
  kb_chunks: number
  cases_by_status: Record<string, number>
  triage_distribution: Record<string, number>
}

const TRIAGE_COLOR: Record<string, string> = {
  GREEN: 'bg-green-500',
  YELLOW: 'bg-yellow-500',
  RED: 'bg-red-500',
}

function StatCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-3xl font-bold">{value.toLocaleString()}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  )
}

function BarChart({
  data,
  colorMap,
}: {
  data: Record<string, number>
  colorMap?: Record<string, string>
}) {
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1
  return (
    <div className="space-y-2">
      {Object.entries(data).map(([key, val]) => (
        <div key={key} className="flex items-center gap-3">
          <span className="w-24 text-xs text-right text-muted-foreground capitalize">{key}</span>
          <div className="flex-1 h-5 bg-muted rounded overflow-hidden">
            <div
              className={`h-full rounded ${colorMap?.[key] ?? 'bg-primary'} transition-all`}
              style={{ width: `${(val / total) * 100}%` }}
            />
          </div>
          <span className="w-8 text-xs text-muted-foreground">{val}</span>
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { accessToken } = useAuthStore()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!accessToken) return
    fetch(`${API}/api/v1/admin/metrics`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => {
        if (r.status === 403) throw new Error('Sin acceso de administrador')
        if (!r.ok) throw new Error('Error al cargar métricas')
        return r.json()
      })
      .then(setMetrics)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [accessToken])

  if (loading)
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Cargando métricas…
      </div>
    )

  if (error)
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-destructive">{error}</p>
      </div>
    )

  if (!metrics) return null

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Métricas del sistema en tiempo real</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Casos totales" value={metrics.total_cases} />
        <StatCard label="Usuarios" value={metrics.total_users} />
        <StatCard label="Documentos" value={metrics.total_documents} />
        <StatCard label="Chunks KB" value={metrics.kb_chunks} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Cases by status */}
        {Object.keys(metrics.cases_by_status).length > 0 && (
          <div className="rounded-xl border bg-card p-5 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold">Casos por estado</h2>
            <BarChart data={metrics.cases_by_status} />
          </div>
        )}

        {/* Triage distribution */}
        {Object.keys(metrics.triage_distribution).length > 0 && (
          <div className="rounded-xl border bg-card p-5 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold">Distribución de triage</h2>
            <BarChart data={metrics.triage_distribution} colorMap={TRIAGE_COLOR} />
          </div>
        )}
      </div>
    </div>
  )
}
