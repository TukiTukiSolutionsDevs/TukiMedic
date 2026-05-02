'use client'

import { useEffect, useState } from 'react'
import { AlertCircle, Search } from 'lucide-react'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const PAGE_SIZE = 20
const TIERS = ['free', 'pro', 'enterprise']

interface AdminUser {
  id: string
  email: string
  display_name: string | null
  role: string
  subscription_tier: string
  is_active: boolean
  created_at: string | null
}

export function UserTable() {
  const { accessToken } = useAuthStore()
  const [users, setUsers]   = useState<AdminUser[]>([])
  const [total, setTotal]   = useState(0)
  const [page, setPage]     = useState(1)
  const [search, setSearch] = useState('')
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError]   = useState<string | null>(null)

  const authHeaders = {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  }

  const load = async (p = 1, q = search) => {
    const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) })
    if (q) params.set('search', q)
    const r = await fetch(`${API}/api/v1/admin/users?${params}`, { headers: authHeaders })
    if (!r.ok) { setError('Error al cargar usuarios'); return }
    const data = await r.json()
    setUsers(data.items)
    setTotal(data.total)
    setPage(p)
  }

  useEffect(() => { if (accessToken) load() }, [accessToken])

  const handlePatch = async (
    userId: string,
    patch: Partial<Pick<AdminUser, 'role' | 'subscription_tier' | 'is_active'>>,
  ) => {
    setSaving(userId)
    setError(null)
    try {
      const r = await fetch(`${API}/api/v1/admin/users/${userId}`, {
        method: 'PATCH',
        headers: authHeaders,
        body: JSON.stringify(patch),
      })
      if (r.status === 409) { setError('No se puede degradar al ultimo administrador.'); return }
      if (!r.ok) { setError('Error al actualizar usuario.'); return }
      const updated: AdminUser = await r.json()
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)))
    } finally {
      setSaving(null)
    }
  }

  const initials = (u: AdminUser) => {
    const name = u.display_name ?? u.email
    return name.split(/[\s@]/)[0].slice(0, 2).toUpperCase()
  }

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border bg-card">
        {/* Toolbar */}
        <div className="flex items-center gap-3 border-b px-4 py-3">
          <div className="relative max-w-xs flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              data-testid="user-search"
              type="text"
              placeholder="Buscar usuario..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load(1, search)}
              className="w-full rounded-lg border bg-background py-1.5 pl-8 pr-3 text-sm"
            />
          </div>
          <button
            onClick={() => load(1, search)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Buscar
          </button>
        </div>

        {/* Table */}
        <table className="w-full text-sm" data-testid="users-table">
          <thead className="bg-muted/40">
            <tr>
              {['Usuario', 'Rol', 'Plan', 'Estado', 'Creado'].map((h) => (
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
            {users.map((u) => (
              <tr
                key={u.id}
                data-testid={`user-row-${u.id}`}
                className="bg-card transition-colors hover:bg-muted/20"
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-700 text-xs font-semibold text-white">
                      {initials(u)}
                    </div>
                    <div>
                      <p className="font-medium">{u.email}</p>
                      {u.display_name && (
                        <p className="text-xs text-muted-foreground">{u.display_name}</p>
                      )}
                    </div>
                  </div>
                </td>

                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      u.role === 'admin'
                        ? 'bg-red-500/15 text-red-700 dark:text-red-400'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {u.role}
                  </span>
                </td>

                <td className="px-4 py-3">
                  <select
                    value={u.subscription_tier}
                    disabled={saving === u.id}
                    onChange={(e) => handlePatch(u.id, { subscription_tier: e.target.value })}
                    data-testid={`tier-select-${u.id}`}
                    className="rounded-md border bg-background px-2 py-1 text-xs disabled:opacity-50"
                  >
                    {TIERS.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </td>

                <td className="px-4 py-3">
                  <button
                    disabled={saving === u.id}
                    onClick={() => handlePatch(u.id, { is_active: !u.is_active })}
                    data-testid={`status-btn-${u.id}`}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                      u.is_active
                        ? 'bg-green-500/15 text-green-700 hover:bg-red-500/15 hover:text-red-600'
                        : 'bg-red-500/15 text-red-700 hover:bg-green-500/15 hover:text-green-600'
                    }`}
                  >
                    {u.is_active ? 'Activo' : 'Suspendido'}
                  </button>
                </td>

                <td className="px-4 py-3 tabular-nums text-xs text-muted-foreground">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString('es-AR') : '—'}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-10 text-center text-sm text-muted-foreground"
                  data-testid="users-empty"
                >
                  Sin usuarios
                </td>
              </tr>
            )}
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
        {users.length === PAGE_SIZE && (
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
