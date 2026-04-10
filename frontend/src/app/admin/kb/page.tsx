'use client'

import { useEffect, useState } from 'react'
import { useAuthStore } from '@/store/auth-store'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

interface KBChunk {
  id: string
  source: string
  title: string
  content: string
  chunk_index: number
  specialty_tags: string[]
  created_at: string
}

interface KBStats {
  by_source: { source: string; count: number }[]
  total: number
}

const emptyForm = {
  source: 'medlineplus',
  title: '',
  content: '',
  chunk_index: 0,
  specialty_tags: '',
}

export default function KBAdminPage() {
  const { accessToken } = useAuthStore()
  const [chunks, setChunks] = useState<KBChunk[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<KBStats | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState(emptyForm)
  const [adding, setAdding] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const PAGE_SIZE = 20

  const headers = {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  }

  const loadChunks = async (p = 1) => {
    const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) })
    if (search) params.set('source', search)
    const r = await fetch(`${API}/api/v1/admin/kb?${params}`, { headers })
    const data = await r.json()
    setChunks(data.items)
    setTotal(data.total)
    setPage(p)
  }

  const loadStats = async () => {
    const r = await fetch(`${API}/api/v1/admin/kb/stats`, { headers })
    setStats(await r.json())
  }

  useEffect(() => {
    if (!accessToken) return
    loadChunks()
    loadStats()
  }, [accessToken])

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar este chunk?')) return
    await fetch(`${API}/api/v1/admin/kb/${id}`, { method: 'DELETE', headers })
    loadChunks(page)
    loadStats()
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setAdding(true)
    await fetch(`${API}/api/v1/admin/kb`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        ...form,
        chunk_index: Number(form.chunk_index),
        specialty_tags: form.specialty_tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    })
    setForm(emptyForm)
    setAdding(false)
    loadChunks(1)
    loadStats()
  }

  const handleIngest = async () => {
    setIngesting(true)
    await fetch(`${API}/api/v1/admin/kb/ingest`, { method: 'POST', headers })
    setIngesting(false)
    alert('Ingestión iniciada en background')
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Base</h1>
          <p className="text-sm text-muted-foreground">
            {stats?.total ?? 0} chunks indexados
          </p>
        </div>
        <button
          onClick={handleIngest}
          disabled={ingesting}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {ingesting ? 'Iniciando…' : '⚡ Ingerir MedlinePlus'}
        </button>
      </div>

      {/* Stats by source */}
      {stats && stats.by_source.length > 0 && (
        <div className="flex gap-3">
          {stats.by_source.map((s) => (
            <div
              key={s.source}
              className="rounded-lg border bg-card px-4 py-2 text-sm"
            >
              <span className="font-medium">{s.source}</span>
              <span className="ml-2 text-muted-foreground">{s.count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Add chunk form */}
      <form
        onSubmit={handleAdd}
        className="rounded-xl border bg-card p-5 shadow-sm space-y-3"
      >
        <h2 className="text-sm font-semibold">Agregar chunk</h2>
        <div className="grid grid-cols-3 gap-3">
          <input
            className="col-span-1 rounded-lg border bg-background px-3 py-2 text-sm"
            placeholder="Source (medlineplus)"
            value={form.source}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
          />
          <input
            className="col-span-2 rounded-lg border bg-background px-3 py-2 text-sm"
            placeholder="Título *"
            required
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </div>
        <textarea
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm h-20"
          placeholder="Contenido *"
          required
          value={form.content}
          onChange={(e) => setForm({ ...form, content: e.target.value })}
        />
        <div className="flex gap-3">
          <input
            className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm"
            placeholder="Tags (cardiology, pediatrics)"
            value={form.specialty_tags}
            onChange={(e) => setForm({ ...form, specialty_tags: e.target.value })}
          />
          <input
            className="w-24 rounded-lg border bg-background px-3 py-2 text-sm"
            type="number"
            placeholder="Índice"
            value={form.chunk_index}
            onChange={(e) => setForm({ ...form, chunk_index: Number(e.target.value) })}
          />
          <button
            type="submit"
            disabled={adding}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {adding ? 'Agregando…' : 'Agregar'}
          </button>
        </div>
      </form>

      {/* Search / filter */}
      <div className="flex gap-3">
        <input
          className="rounded-lg border bg-background px-3 py-2 text-sm"
          placeholder="Filtrar por source…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && loadChunks(1)}
        />
        <button
          onClick={() => loadChunks(1)}
          className="rounded-lg border px-3 py-2 text-sm hover:bg-accent"
        >
          Buscar
        </button>
      </div>

      {/* Chunks list */}
      <div className="space-y-2">
        {chunks.map((c) => (
          <div
            key={c.id}
            className="rounded-xl border bg-card p-4 flex items-start justify-between gap-4"
          >
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm truncate">{c.title}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {c.source} · chunk {c.chunk_index}
                {c.specialty_tags.length > 0 && (
                  <> · {c.specialty_tags.join(', ')}</>
                )}
              </p>
              <p className="text-xs text-muted-foreground/60 mt-1 line-clamp-2">
                {c.content}
              </p>
            </div>
            <button
              onClick={() => handleDelete(c.id)}
              className="shrink-0 text-destructive text-xs hover:underline"
            >
              Eliminar
            </button>
          </div>
        ))}
      </div>

      {/* Pagination */}
      <div className="flex gap-2">
        {page > 1 && (
          <button
            onClick={() => loadChunks(page - 1)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-accent"
          >
            ← Anterior
          </button>
        )}
        <span className="px-3 py-1.5 text-sm text-muted-foreground">
          Página {page} · {total} total
        </span>
        {chunks.length === PAGE_SIZE && (
          <button
            onClick={() => loadChunks(page + 1)}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-accent"
          >
            Siguiente →
          </button>
        )}
      </div>
    </div>
  )
}
