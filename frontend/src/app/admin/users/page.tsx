'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const PAGE_SIZE = 20

interface AdminUser {
  id: string
  email: string
  display_name: string | null
  role: string
  subscription_tier: string
  is_active: boolean
  created_at: string | null
}

const ROLES = ['customer', 'admin']
const TIERS = ['free', 'pro', 'enterprise']

export default function AdminUsersPage() {
  const { accessToken } = useAuthStore()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const headers = {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  }

  const loadUsers = async (p = 1) => {
    const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) })
    const r = await fetch(`${API}/api/v1/admin/users?${params}`, { headers })
    if (!r.ok) { setError('Error al cargar usuarios'); return }
    const data = await r.json()
    setUsers(data.items)
    setTotal(data.total)
    setPage(p)
  }

  useEffect(() => {
    if (accessToken) loadUsers()
  }, [accessToken])

  const handlePatch = async (
    userId: string,
    patch: Partial<Pick<AdminUser, 'role' | 'subscription_tier' | 'is_active'>>,
  ) => {
    setSaving(userId)
    setError(null)
    try {
      const r = await fetch(`${API}/api/v1/admin/users/${userId}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(patch),
      })
      if (r.status === 409) {
        setError('No se puede degradar al último administrador.')
        return
      }
      if (!r.ok) {
        setError('Error al actualizar usuario.')
        return
      }
      const updated: AdminUser = await r.json()
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)))
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Usuarios</h1>
        <p className="text-sm text-muted-foreground">{total} usuarios registrados</p>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Users table */}
      <div className="rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Email</th>
              <th className="px-4 py-3 text-left font-medium">Rol</th>
              <th className="px-4 py-3 text-left font-medium">Plan</th>
              <th className="px-4 py-3 text-left font-medium">Estado</th>
              <th className="px-4 py-3 text-left font-medium">Creado</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {users.map((u) => (
              <tr key={u.id} className="bg-card hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3">
                  <p className="font-medium truncate max-w-xs">{u.email}</p>
                  {u.display_name && (
                    <p className="text-xs text-muted-foreground">{u.display_name}</p>
                  )}
                </td>

                {/* Role select */}
                <td className="px-4 py-3">
                  <select
                    value={u.role}
                    disabled={saving === u.id}
                    onChange={(e) => handlePatch(u.id, { role: e.target.value })}
                    className="rounded-md border bg-background px-2 py-1 text-xs disabled:opacity-50"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </td>

                {/* Tier select */}
                <td className="px-4 py-3">
                  <select
                    value={u.subscription_tier}
                    disabled={saving === u.id}
                    onChange={(e) => handlePatch(u.id, { subscription_tier: e.target.value })}
                    className="rounded-md border bg-background px-2 py-1 text-xs disabled:opacity-50"
                  >
                    {TIERS.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </td>

                {/* Active toggle */}
                <td className="px-4 py-3">
                  <button
                    disabled={saving === u.id}
                    onClick={() => handlePatch(u.id, { is_active: !u.is_active })}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                      u.is_active
                        ? 'bg-green-500/15 text-green-600 hover:bg-red-500/15 hover:text-red-600'
                        : 'bg-red-500/15 text-red-600 hover:bg-green-500/15 hover:text-green-600'
                    }`}
                  >
                    {u.is_active ? 'Activo' : 'Inactivo'}
                  </button>
                </td>

                <td className="px-4 py-3 text-xs text-muted-foreground tabular-nums">
                  {u.created_at
                    ? new Date(u.created_at).toLocaleDateString('es-AR')
                    : '—'}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">
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
            onClick={() => loadUsers(page - 1)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-accent"
          >
            ← Anterior
          </button>
        )}
        <span className="text-sm text-muted-foreground">
          Página {page} · {total} total
        </span>
        {users.length === PAGE_SIZE && (
          <button
            onClick={() => loadUsers(page + 1)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-accent"
          >
            Siguiente →
          </button>
        )}
      </div>
    </div>
  )
}
