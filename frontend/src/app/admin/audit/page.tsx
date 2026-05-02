'use client'

import { useEffect, useState } from 'react'
import { Shield } from 'lucide-react'
import { VerifyChainButton } from '@/components/admin/verify-chain-button'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const PAGE_SIZE = 20

interface AuditEntry {
  id: string
  user_id: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  ip_address: string | null
  created_at: string
}

const ACTION_TONE: Record<string, string> = {
  login:                'bg-blue-500/15 text-blue-700',
  register:             'bg-green-500/15 text-green-700',
  document_upload:      'bg-purple-500/15 text-purple-700',
  export_pdf:           'bg-orange-500/15 text-orange-700',
  kb_ingest:            'bg-yellow-500/15 text-yellow-700',
  kb_add_chunk:         'bg-teal-500/15 text-teal-700',
  kb_delete_chunk:      'bg-red-500/15 text-red-700',
  triage_decision:      'bg-amber-500/15 text-amber-700',
  response_synthesized: 'bg-blue-500/15 text-blue-700',
  guardrail_violation:  'bg-red-500/15 text-red-700',
  api_key_rotate:       'bg-amber-500/15 text-amber-700',
}

export default function AuditPage() {
  const { accessToken } = useAuthStore()
  const [items, setItems]               = useState<AuditEntry[]>([])
  const [total, setTotal]               = useState(0)
  const [page, setPage]                 = useState(1)
  const [filterAction, setFilterAction] = useState('')

  const load = async (p = 1, action = filterAction) => {
    const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) })
    if (action) params.set('action', action)
    const r = await fetch(`${API}/api/v1/admin/audit-log?${params}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    const data = await r.json()
    setItems(data.items)
    setTotal(data.total)
    setPage(p)
  }

  useEffect(() => { if (accessToken) load() }, [accessToken])

  const handleFilter = (action: string) => {
    setFilterAction(action)
    load(1, action)
  }

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto p-6">
      <div>
        <h1 className="text-xl font-semibold">Audit Log</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Verifica integridad del audit log con la cadena hash SHA-256
        </p>
      </div>

      {/* Verify chain card */}
      <div className="rounded-xl border bg-card px-5 py-4">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-50 dark:bg-green-950">
            <Shield size={20} className="text-green-600 dark:text-green-400" />
          </div>
          <div>
            <p className="text-sm font-semibold">Integridad de cadena</p>
            <p className="text-xs text-muted-foreground">
              SHA-256 &middot; {total} entradas totales
            </p>
          </div>
        </div>
        <VerifyChainButton />
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => handleFilter('')}
          className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
            filterAction === '' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
          }`}
        >
          Todas
        </button>
        {Object.keys(ACTION_TONE).map((a) => (
          <button
            key={a}
            onClick={() => handleFilter(a)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              filterAction === a ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
            }`}
          >
            {a}
          </button>
        ))}
      </div>

      {/* Events table */}
      <div className="overflow-hidden rounded-xl border bg-card">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="text-sm font-semibold">Eventos recientes</h3>
          <span className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground">
            SHA-256 chain
          </span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              {['Hora', 'Accion', 'Usuario', 'Chain hash'].map((h) => (
                <th
                  key={h}
                  className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-sm text-muted-foreground">
                  Sin entradas
                </td>
              </tr>
            )}
            {items.map((item) => (
              <tr key={item.id} className="bg-card transition-colors hover:bg-muted/20">
                <td className="px-4 py-3 font-mono text-xs tabular-nums text-muted-foreground">
                  {new Date(item.created_at).toLocaleTimeString('es-AR')}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      ACTION_TONE[item.action] ?? 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {item.action}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs">
                  {item.user_id ? `${item.user_id.slice(0, 8)}…` : 'system'}
                  {item.ip_address && (
                    <span className="ml-2 text-muted-foreground">{item.ip_address}</span>
                  )}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                  {item.entity_id ? `${item.entity_id.slice(0, 8)}…` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center gap-3">
        {page > 1 && (
          <button
            onClick={() => load(page - 1)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Anterior
          </button>
        )}
        <span className="text-sm text-muted-foreground">
          Pagina {page} &middot; {total} total
        </span>
        {items.length === PAGE_SIZE && (
          <button
            onClick={() => load(page + 1)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Siguiente
          </button>
        )}
      </div>
    </div>
  )
}
