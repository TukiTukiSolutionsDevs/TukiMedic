'use client'

import { useEffect, useState } from 'react'
import { RotateCw, FileText, AlertCircle } from 'lucide-react'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

interface KBStats {
  by_source: { source: string; count: number }[]
  total: number
}

const SOURCES = [
  { id: 'pubmed',      label: 'PubMed'      },
  { id: 'who',         label: 'WHO'         },
  { id: 'livertox',    label: 'LiverTox'    },
  { id: 'medlineplus', label: 'MedlinePlus' },
]

export function KBStatus() {
  const { accessToken } = useAuthStore()
  const [stats, setStats]         = useState<KBStats | null>(null)
  const [ingesting, setIngesting] = useState(false)
  const [success, setSuccess]     = useState(false)
  const [error, setError]         = useState<string | null>(null)

  const authHeaders = {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  }

  const loadStats = async () => {
    try {
      const r = await fetch(`${API}/api/v1/admin/kb/stats`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      if (r.ok) setStats(await r.json())
    } catch {
      // stats are non-critical; fail silently
    }
  }

  useEffect(() => { if (accessToken) loadStats() }, [accessToken])

  const handleIngest = async () => {
    setIngesting(true)
    setError(null)
    setSuccess(false)
    try {
      const r = await fetch(`${API}/api/v1/admin/kb/ingest`, {
        method: 'POST',
        headers: authHeaders,
      })
      if (!r.ok) { setError(`Error al iniciar ingestión (HTTP ${r.status})`); return }
      setSuccess(true)
      setTimeout(() => setSuccess(false), 5000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido')
    } finally {
      setIngesting(false)
    }
  }

  const countFor = (source: string) =>
    stats?.by_source.find((s) => s.source === source)?.count ?? null

  return (
    <div className="flex flex-col gap-6">
      {/* Stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border bg-card px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Total chunks
          </p>
          <p className="mt-2 text-3xl font-semibold tabular-nums">
            {stats?.total ?? '—'}
          </p>
        </div>
        {SOURCES.slice(0, 2).map((s) => (
          <div key={s.id} className="rounded-xl border bg-card px-5 py-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {s.label}
            </p>
            <p className="mt-2 text-3xl font-semibold tabular-nums">
              {countFor(s.id) ?? '—'}
            </p>
          </div>
        ))}
      </div>

      {/* Reindex card */}
      <div className="overflow-hidden rounded-xl border bg-card">
        <div className="flex items-start justify-between border-b px-5 py-4">
          <div>
            <h3 className="text-sm font-semibold">Reindexar Knowledge Base</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Dispara la ingestión completa desde las fuentes configuradas.
            </p>
          </div>
          <button
            onClick={handleIngest}
            disabled={ingesting}
            data-testid="reindex-btn"
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            <RotateCw size={14} className={ingesting ? 'animate-spin' : ''} />
            {ingesting ? 'Iniciando…' : 'Reindexar ahora'}
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 border-b bg-destructive/5 px-4 py-2 text-sm text-destructive">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {success && (
          <div
            data-testid="ingest-success"
            className="border-b bg-emerald-50 px-4 py-2 text-sm text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
          >
            Ingestión iniciada en background.
          </div>
        )}

        {/* Sources list */}
        <div className="divide-y">
          {SOURCES.map((s) => (
            <div key={s.id} className="flex items-center gap-3 px-5 py-3">
              <FileText size={15} className="text-muted-foreground" />
              <span className="flex-1 text-sm font-medium">{s.label}</span>
              <span className="tabular-nums text-xs text-muted-foreground">
                {countFor(s.id) !== null ? `${countFor(s.id)} chunks` : 'Sin datos'}
              </span>
            </div>
          ))}
        </div>

        {/* Placeholder drag-drop */}
        <div className="m-4 flex items-center justify-center rounded-xl border border-dashed py-8 text-sm text-muted-foreground">
          Carga de archivos — proximamente
        </div>
      </div>
    </div>
  )
}
