'use client'

import { useEffect, useState } from 'react'
import { Key, RotateCw, Trash2, Plus, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const PROVIDERS = ['openai', 'gemini', 'anthropic'] as const

interface Credential {
  id: string
  provider: string
  label: string
  is_active: boolean
  created_at: string | null
  rotated_at: string | null
}

const emptyForm = { provider: 'openai', label: '', plaintext_key: '', activate: true }

export function CredentialTable() {
  const { accessToken } = useAuthStore()
  const [creds, setCreds]               = useState<Credential[]>([])
  const [error, setError]               = useState<string | null>(null)
  const [saving, setSaving]             = useState<string | null>(null)
  const [addOpen, setAddOpen]           = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Credential | null>(null)
  const [creating, setCreating]         = useState(false)
  const [form, setForm]                 = useState(emptyForm)

  const authHeaders = {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  }

  const load = async () => {
    const r = await fetch(`${API}/api/v1/admin/credentials`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!r.ok) { setError('Error al cargar credenciales'); return }
    const data = await r.json()
    setCreds(data.items ?? data)
  }

  useEffect(() => { if (accessToken) load() }, [accessToken])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      const r = await fetch(`${API}/api/v1/admin/credentials`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify(form),
      })
      if (!r.ok) { setError('Error al crear credencial'); return }
      setForm(emptyForm)
      setAddOpen(false)
      await load()
    } finally {
      setCreating(false)
    }
  }

  const handleRotate = async (id: string) => {
    setSaving(id)
    setError(null)
    try {
      const r = await fetch(`${API}/api/v1/admin/credentials/${id}/rotate`, {
        method: 'POST',
        headers: authHeaders,
      })
      if (!r.ok) { setError('Error al rotar credencial'); return }
      await load()
    } finally {
      setSaving(null)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    const id = deleteTarget.id
    setDeleteTarget(null)
    setSaving(id)
    setError(null)
    try {
      const r = await fetch(`${API}/api/v1/admin/credentials/${id}`, {
        method: 'DELETE',
        headers: authHeaders,
      })
      if (!r.ok) { setError('Error al eliminar credencial'); return }
      setCreds((prev) => prev.filter((c) => c.id !== id))
    } finally {
      setSaving(null)
    }
  }

  return (
    <>
      <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300">
        Las API keys se almacenan cifradas con AES-256-GCM. El plaintext solo se acepta al crear o rotar — nunca se expone despues.
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h3 className="text-sm font-semibold">Credenciales LLM</h3>
          <Button
            size="sm"
            onClick={() => setAddOpen(true)}
            data-testid="add-credential-btn"
          >
            <Plus size={14} /> Nueva credencial
          </Button>
        </div>

        {error && (
          <div className="flex items-center gap-2 border-b bg-destructive/5 px-4 py-2 text-sm text-destructive">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {creds.length === 0 ? (
          <div
            data-testid="credentials-empty"
            className="flex flex-col items-center gap-2 py-12 text-muted-foreground"
          >
            <Key size={32} className="opacity-30" />
            <p className="text-sm">Sin credenciales configuradas</p>
          </div>
        ) : (
          <div className="divide-y">
            {creds.map((c) => (
              <div
                key={c.id}
                data-testid={`credential-row-${c.id}`}
                className="flex items-center gap-4 px-5 py-4"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <Key size={18} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">{c.label}</span>
                    {c.is_active && (
                      <span className="rounded-full bg-green-500/15 px-2 py-0.5 text-xs font-medium text-green-700 dark:text-green-400">
                        Activa
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Provider: <strong className="text-foreground">{c.provider}</strong>
                    {c.rotated_at && (
                      <> &middot; Rotada: {new Date(c.rotated_at).toLocaleDateString('es-AR')}</>
                    )}
                    {c.created_at && (
                      <> &middot; Creada: {new Date(c.created_at).toLocaleDateString('es-AR')}</>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    disabled={saving === c.id}
                    onClick={() => handleRotate(c.id)}
                    data-testid={`rotate-btn-${c.id}`}
                    className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
                  >
                    <RotateCw size={12} /> Rotar
                  </button>
                  <button
                    disabled={saving === c.id}
                    onClick={() => setDeleteTarget(c)}
                    data-testid={`delete-btn-${c.id}`}
                    className="inline-flex items-center justify-center rounded-lg border border-destructive/40 p-1.5 text-destructive hover:bg-destructive/10 disabled:opacity-50"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add credential dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent data-testid="add-credential-dialog">
          <DialogHeader>
            <DialogTitle>Nueva credencial</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="mt-2 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cred-provider">Proveedor</Label>
              <select
                id="cred-provider"
                value={form.provider}
                onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
                className="rounded-md border bg-background px-3 py-2 text-sm"
                data-testid="provider-select"
              >
                {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cred-label-input">Etiqueta</Label>
              <Input
                id="cred-label-input"
                placeholder="Ej. Produccion"
                value={form.label}
                onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
                required
                data-testid="label-input"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cred-api-key">API Key</Label>
              <Input
                id="cred-api-key"
                type="password"
                placeholder="sk-..."
                value={form.plaintext_key}
                onChange={(e) => setForm((f) => ({ ...f, plaintext_key: e.target.value }))}
                required
                data-testid="api-key-input"
              />
            </div>
            <DialogFooter>
              <button
                type="submit"
                disabled={creating}
                data-testid="create-credential-submit"
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {creating ? 'Creando…' : 'Crear'}
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
      >
        <DialogContent data-testid="delete-credential-dialog">
          <DialogHeader>
            <DialogTitle>Eliminar credencial</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Esta accion no se puede deshacer. La credencial{' '}
            <strong>{deleteTarget?.label}</strong> sera eliminada permanentemente.
          </p>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setDeleteTarget(null)}
              className="rounded-lg border px-4 py-2 text-sm hover:bg-muted"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={confirmDelete}
              data-testid="confirm-delete-btn"
              className="rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
