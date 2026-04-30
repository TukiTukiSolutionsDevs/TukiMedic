'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

interface Credential {
  id: string
  provider: string
  label: string
  is_active: boolean
  created_at: string | null
  rotated_at: string | null
}

const PROVIDERS = ['openai', 'gemini', 'anthropic']

export default function AdminCredentialsPage() {
  const { accessToken } = useAuthStore()
  const [creds, setCreds] = useState<Credential[]>([])
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    provider: 'openai',
    label: '',
    plaintext_key: '',
    activate: true,
  })
  const [creating, setCreating] = useState(false)

  const headers = {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  }

  const loadCreds = async () => {
    const r = await fetch(`${API}/api/v1/admin/credentials`, { headers })
    if (!r.ok) { setError('Error al cargar credenciales'); return }
    const data = await r.json()
    setCreds(data.items)
  }

  useEffect(() => {
    if (accessToken) loadCreds()
  }, [accessToken])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      const r = await fetch(`${API}/api/v1/admin/credentials`, {
        method: 'POST',
        headers,
        body: JSON.stringify(form),
      })
      if (!r.ok) { setError('Error al crear credencial'); return }
      setForm({ provider: 'openai', label: '', plaintext_key: '', activate: true })
      await loadCreds()
    } finally {
      setCreating(false)
    }
  }

  const handleActivate = async (id: string) => {
    setSaving(id)
    setError(null)
    try {
      const r = await fetch(`${API}/api/v1/admin/credentials/${id}/activate`, {
        method: 'PATCH',
        headers,
      })
      if (!r.ok) { setError('Error al activar credencial'); return }
      await loadCreds()
    } finally {
      setSaving(null)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar esta credencial?')) return
    setSaving(id)
    setError(null)
    try {
      const r = await fetch(`${API}/api/v1/admin/credentials/${id}`, {
        method: 'DELETE',
        headers,
      })
      if (!r.ok) { setError('Error al eliminar credencial'); return }
      setCreds((prev) => prev.filter((c) => c.id !== id))
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">API Keys</h1>
        <p className="text-sm text-muted-foreground">
          Claves cifradas por proveedor. El valor nunca se muestra tras la creación.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Create form */}
      <form onSubmit={handleCreate} className="rounded-xl border p-4 space-y-3">
        <h2 className="font-semibold text-sm">Nueva credencial</h2>
        <div className="flex flex-wrap gap-3 items-end">
          <select
            value={form.provider}
            onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
            className="rounded-md border bg-background px-2 py-1.5 text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Etiqueta (ej. Producción)"
            value={form.label}
            onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
            required
            className="rounded-md border bg-background px-2 py-1.5 text-sm flex-1 min-w-40"
          />

          <input
            type="password"
            placeholder="API Key"
            value={form.plaintext_key}
            onChange={(e) => setForm((f) => ({ ...f, plaintext_key: e.target.value }))}
            required
            className="rounded-md border bg-background px-2 py-1.5 text-sm flex-1 min-w-48"
          />

          <label className="flex items-center gap-1.5 text-sm select-none">
            <input
              type="checkbox"
              checked={form.activate}
              onChange={(e) => setForm((f) => ({ ...f, activate: e.target.checked }))}
            />
            Activar
          </label>

          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {creating ? 'Creando…' : 'Crear'}
          </button>
        </div>
      </form>

      {/* Credentials table */}
      <div className="rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Proveedor</th>
              <th className="px-4 py-3 text-left font-medium">Etiqueta</th>
              <th className="px-4 py-3 text-left font-medium">Estado</th>
              <th className="px-4 py-3 text-left font-medium">Creado</th>
              <th className="px-4 py-3 text-left font-medium">Rotado</th>
              <th className="px-4 py-3 text-left font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {creds.map((c) => (
              <tr key={c.id} className="bg-card hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3 font-mono text-xs">{c.provider}</td>
                <td className="px-4 py-3">{c.label}</td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      c.is_active
                        ? 'bg-green-500/15 text-green-600'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {c.is_active ? 'Activa' : 'Inactiva'}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground tabular-nums">
                  {c.created_at ? new Date(c.created_at).toLocaleDateString('es-AR') : '—'}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground tabular-nums">
                  {c.rotated_at ? new Date(c.rotated_at).toLocaleDateString('es-AR') : '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    {!c.is_active && (
                      <button
                        disabled={saving === c.id}
                        onClick={() => handleActivate(c.id)}
                        className="rounded-md border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
                      >
                        Activar
                      </button>
                    )}
                    <button
                      disabled={saving === c.id}
                      onClick={() => handleDelete(c.id)}
                      className="rounded-md border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
                    >
                      Eliminar
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {creds.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-sm text-muted-foreground"
                >
                  Sin credenciales configuradas
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
