'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

interface AuditEntry {
  id: string
  user_id: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

const ACTION_BADGE: Record<string, string> = {
  login: 'bg-blue-500/15 text-blue-400',
  register: 'bg-green-500/15 text-green-400',
  document_upload: 'bg-purple-500/15 text-purple-400',
  export_pdf: 'bg-orange-500/15 text-orange-400',
  kb_ingest: 'bg-yellow-500/15 text-yellow-400',
  kb_add_chunk: 'bg-teal-500/15 text-teal-400',
  kb_delete_chunk: 'bg-red-500/15 text-red-400',
}

const ALL_ACTIONS = Object.keys(ACTION_BADGE)

export default function AuditPage() {
  const { accessToken } = useAuthStore()
  const [items, setItems] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filterAction, setFilterAction] = useState('')
  const PAGE_SIZE = 20

  const headers = { Authorization: `Bearer ${accessToken}` }

  const load = async (p = 1, action = filterAction) => {
    const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) })
    if (action) params.set('action', action)
    const r = await fetch(`${API}/api/v1/admin/audit-log?${params}`, { headers })
    const data = await r.json()
    setItems(data.items)
    setTotal(data.total)
    setPage(p)
  }

  useEffect(() => {
    if (accessToken) load()
  }, [accessToken])

  const handleFilter = (action: string) => {
    setFilterAction(action)
    load(1, action)
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Audit Log</h1>
        <p className="text-sm text-muted-foreground">{total} entradas registradas</p>
      </div>

      {/* Action filter pills */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => handleFilter('')}
          className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
            filterAction === '' ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'
          }`}
        >
          Todas
        </button>
        {ALL_ACTIONS.map((a) => (
          <button
            key={a}
            onClick={() => handleFilter(a)}
            className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
              filterAction === a ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'
            }`}
          >
            {a}
          </button>
        ))}
      </div>

      {/* Log entries */}
      <div className="space-y-1.5">
        {items.length === 0 && (
          <p className="text-sm text-muted-foreground py-8 text-center">Sin entradas</p>
        )}
        {items.map((item) => (
          <div
            key={item.id}
            className="rounded-xl border bg-card px-4 py-3 flex items-center gap-4"
          >
            {/* Action badge */}
            <span
              className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-mono font-medium ${
                ACTION_BADGE[item.action] ?? 'bg-muted text-muted-foreground'
              }`}
            >
              {item.action}
            </span>

            {/* Details */}
            <div className="flex-1 min-w-0">
              <p className="text-xs text-muted-foreground truncate">
                {item.entity_type && (
                  <span className="mr-2 font-medium text-foreground/70">
                    {item.entity_type}
                  </span>
                )}
                {item.entity_id && (
                  <span className="font-mono">{item.entity_id.slice(0, 8)}…</span>
                )}
              </p>
              <p className="text-xs text-muted-foreground/60 mt-0.5">
                user: {item.user_id ? item.user_id.slice(0, 8) + '…' : 'system'}
                {item.ip_address && <> · IP: {item.ip_address}</>}
              </p>
            </div>

            {/* Timestamp */}
            <span className="shrink-0 text-xs text-muted-foreground/50 tabular-nums">
              {new Date(item.created_at).toLocaleString('es-AR', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        ))}
      </div>

      {/* Pagination */}
      <div className="flex items-center gap-3">
        {page > 1 && (
          <button
            onClick={() => load(page - 1)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-accent"
          >
            ← Anterior
          </button>
        )}
        <span className="text-sm text-muted-foreground">
          Página {page} · {total} total
        </span>
        {items.length === PAGE_SIZE && (
          <button
            onClick={() => load(page + 1)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-accent"
          >
            Siguiente →
          </button>
        )}
      </div>
    </div>
  )
}
