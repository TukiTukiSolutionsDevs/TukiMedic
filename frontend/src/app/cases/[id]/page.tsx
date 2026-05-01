'use client'

import { use, useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, API_BASE_URL } from '@/lib/api'
import { parseTierGate, type TierGateInfo } from '@/lib/tier-gate'
import { useAuthStore } from '@/store/auth-store'
import { TierUpgradeBanner } from '@/components/TierUpgradeBanner'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

interface MedCase {
  id: string
  title: string | null
  status: string
  created_at: string
  summary: string | null
}

export default function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const accessToken = useAuthStore((s) => s.accessToken)

  const [caseData, setCaseData] = useState<MedCase | null>(null)
  const [loading, setLoading] = useState(true)
  const [tierGate, setTierGate] = useState<TierGateInfo | null>(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function fetchCase() {
      setLoading(true)
      try {
        const data = await api.get<MedCase>(`/api/v1/cases/${id}`)
        if (!cancelled) setCaseData(data)
      } catch {
        if (!cancelled) toast.error('No se pudo cargar el caso.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchCase()
    return () => {
      cancelled = true
    }
  }, [id])

  async function handleExportPdf() {
    if (!accessToken) return
    setExporting(true)
    setTierGate(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/cases/${id}/export/pdf`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      })

      if (!res.ok) {
        const body = await res.json().catch(() => null)
        const err = new ApiError(
          res.status,
          `Export failed: ${res.status}`,
          body,
          body?.detail?.code,
        )
        const gate = parseTierGate(err)
        if (gate) {
          setTierGate(gate)
        } else {
          toast.error('No se pudo exportar el PDF.')
        }
        return
      }

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `case_${id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('No se pudo exportar el PDF.')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="container mx-auto max-w-3xl space-y-6 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">
          {loading ? 'Cargando caso…' : (caseData?.title ?? 'Caso sin título')}
        </h1>

        <Button onClick={handleExportPdf} disabled={exporting || loading}>
          {exporting ? (
            <>
              <Loader2 className="mr-2 size-4 animate-spin" />
              Exportando…
            </>
          ) : (
            'Exportar PDF'
          )}
        </Button>
      </div>

      {tierGate && <TierUpgradeBanner gate={tierGate} />}

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {!loading && caseData && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>{caseData.title ?? 'Caso sin título'}</CardTitle>
              <Badge variant="outline">{caseData.status}</Badge>
            </div>
            <CardDescription>
              {new Date(caseData.created_at).toLocaleDateString('es-AR')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">
              {caseData.summary ?? 'Sin resumen disponible.'}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
