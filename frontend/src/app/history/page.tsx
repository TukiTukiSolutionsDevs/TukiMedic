'use client'

import { useEffect, useState, useMemo } from 'react'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import { parseTierGate, type TierGateInfo } from '@/lib/tier-gate'
import { TierUpgradeBanner } from '@/components/TierUpgradeBanner'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuthStore } from '@/store/auth-store'

import { FilterBar, type TriageFilter, type SinceFilter } from '@/components/history/filter-bar'
import { CaseRow, type HistoryCase } from '@/components/history/case-row'
import { EmptyState } from '@/components/history/empty-state'

const PAGE_SIZE = 10

function sinceToMs(since: SinceFilter): number | null {
  if (since === 'all') return null
  const days = since === '7d' ? 7 : since === '30d' ? 30 : 90
  return days * 24 * 60 * 60 * 1000
}

export default function HistoryPage() {
  const user = useAuthStore((s) => s.user)
  const isPaid = user?.subscriptionTier === 'paid'

  const [cases, setCases] = useState<HistoryCase[]>([])
  const [loading, setLoading] = useState(true)
  const [tierGate, setTierGate] = useState<TierGateInfo | null>(null)

  const [query, setQuery] = useState('')
  const [triage, setTriage] = useState<TriageFilter>('all')
  const [since, setSince] = useState<SinceFilter>('all')
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setTierGate(null)

    api
      .get<HistoryCase[]>('/api/v1/cases')
      .then((data) => {
        if (!cancelled) setCases(data)
      })
      .catch((err) => {
        if (cancelled) return
        const gate = parseTierGate(err)
        if (gate) setTierGate(gate)
        else toast.error('No se pudo cargar el historial.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const filtered = useMemo(() => {
    const now = Date.now()
    const sinceMs = sinceToMs(since)
    return cases.filter((c) => {
      if (sinceMs !== null && now - new Date(c.created_at).getTime() > sinceMs) return false
      if (triage !== 'all' && c.triage_level !== triage) return false
      if (query) {
        const text = (c.title ?? '') + ' ' + (c.chief_complaint ?? '')
        if (!text.toLowerCase().includes(query.toLowerCase())) return false
      }
      return true
    })
  }, [cases, query, triage, since])

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const hasFilters = query !== '' || triage !== 'all' || since !== 'all'

  function clearFilters() {
    setQuery('')
    setTriage('all')
    setSince('all')
    setPage(1)
  }

  return (
    <div className="container mx-auto max-w-3xl space-y-6 py-8">
      <div>
        <h1 className="text-2xl font-bold">Mis casos</h1>
        <p className="text-sm text-muted-foreground">Historial de consultas con el equipo</p>
      </div>

      <FilterBar
        query={query}
        onQueryChange={(v) => {
          setQuery(v)
          setPage(1)
        }}
        triage={triage}
        onTriageChange={(v) => {
          setTriage(v)
          setPage(1)
        }}
        since={since}
        onSinceChange={(v) => {
          setSince(v)
          setPage(1)
        }}
      />

      {tierGate && <TierUpgradeBanner gate={tierGate} />}

      {loading && (
        <div className="space-y-3" aria-busy="true">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {!loading && !tierGate && filtered.length === 0 && (
        <EmptyState hasFilters={hasFilters} onClearFilters={clearFilters} />
      )}

      {!loading && paginated.length > 0 && (
        <div className="space-y-2">
          {paginated.map((c) => (
            <CaseRow key={c.id} c={c} isPaid={isPaid} />
          ))}
        </div>
      )}

      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Mostrando {(page - 1) * PAGE_SIZE + 1}–
            {Math.min(page * PAGE_SIZE, filtered.length)} de {filtered.length}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => p - 1)}
              disabled={page === 1}
              className="rounded border px-3 py-1 disabled:opacity-40"
              aria-label="Página anterior"
            >
              Anterior
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => p + 1)}
              disabled={page === totalPages}
              className="rounded border px-3 py-1 disabled:opacity-40"
              aria-label="Página siguiente"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
