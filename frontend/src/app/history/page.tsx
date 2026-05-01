'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import { parseTierGate, type TierGateInfo } from '@/lib/tier-gate'
import { TierUpgradeBanner } from '@/components/TierUpgradeBanner'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

type DaysFilter = 7 | 30 | 90 | 'all'

interface MedCase {
  id: string
  title: string | null
  status: string
  created_at: string
}

export default function HistoryPage() {
  const [cases, setCases] = useState<MedCase[]>([])
  const [loading, setLoading] = useState(true)
  const [tierGate, setTierGate] = useState<TierGateInfo | null>(null)
  const [days, setDays] = useState<DaysFilter>(7)

  useEffect(() => {
    let cancelled = false

    async function fetchCases() {
      setLoading(true)
      setTierGate(null)
      try {
        const params = days === 'all' ? '' : `?days=${days}`
        const data = await api.get<MedCase[]>(`/api/v1/cases${params}`)
        if (!cancelled) setCases(data)
      } catch (err) {
        if (cancelled) return
        const gate = parseTierGate(err)
        if (gate) {
          setTierGate(gate)
        } else {
          toast.error('No se pudo cargar el historial.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchCases()
    return () => {
      cancelled = true
    }
  }, [days])

  return (
    <div className="container mx-auto max-w-3xl space-y-6 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Historial</h1>
        <select
          aria-label="Filtrar por días"
          className="rounded-md border bg-background px-3 py-1.5 text-sm"
          value={days}
          onChange={(e) => {
            const v = e.target.value
            setDays(v === 'all' ? 'all' : (Number(v) as 7 | 30 | 90))
          }}
        >
          <option value={7}>Últimos 7 días</option>
          <option value={30}>Últimos 30 días</option>
          <option value={90}>Últimos 90 días</option>
          <option value="all">Todos</option>
        </select>
      </div>

      {tierGate && <TierUpgradeBanner gate={tierGate} />}

      {loading && (
        <div className="space-y-3" aria-busy="true">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      )}

      {!loading && !tierGate && cases.length === 0 && (
        <p className="text-center text-muted-foreground">No hay casos en este período.</p>
      )}

      {!loading &&
        cases.map((c) => (
          <Card key={c.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{c.title ?? 'Caso sin título'}</CardTitle>
                <Badge variant="outline">{c.status}</Badge>
              </div>
              <CardDescription>
                {new Date(c.created_at).toLocaleDateString('es-AR')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <a
                href={`/cases/${c.id}`}
                className="text-sm underline underline-offset-4 hover:text-foreground"
              >
                Ver detalle
              </a>
            </CardContent>
          </Card>
        ))}
    </div>
  )
}
