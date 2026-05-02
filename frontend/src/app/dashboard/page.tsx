'use client'

import { useEffect, useState } from 'react'

import { api } from '@/lib/api'
import { useAuthStore } from '@/store/auth-store'
import { TierUpgradeBanner } from '@/components/tier-upgrade-banner'
import { Greeting } from '@/components/dashboard/greeting'
import { RecentCases, type DashboardCase } from '@/components/dashboard/recent-cases'
import { StatsRow } from '@/components/dashboard/stats-row'
import { QuickActions } from '@/components/dashboard/quick-actions'
import { Button } from '@/components/ui/button'

// TODO: remove MOCK_CASES once GET /api/v1/cases is wired.
// When the endpoint is ready, delete this array and remove the catch fallback below.
const MOCK_CASES: DashboardCase[] = [
  {
    id: 'c1',
    title: 'Dolor de rodilla post-running',
    chief_complaint:
      'Hace 3 días corrí 10km y me lastimé la rodilla derecha. Hincha y duele al apoyar.',
    triage_level: 'yellow',
    attention_level: '24-48h',
    created_at: '2026-04-29T14:32:00',
    status: 'resolved',
  },
  {
    id: 'c2',
    title: 'Fiebre en pediátrica',
    chief_complaint:
      'Mi nena de 4 años pesa 17 kg, tiene 37.8°C de fiebre.',
    triage_level: 'green',
    attention_level: 'rutina',
    created_at: '2026-04-25T09:14:00',
    status: 'resolved',
  },
  {
    id: 'c3',
    title: 'Cefalea recurrente',
    chief_complaint:
      'Tengo dolores de cabeza desde hace 2 semanas, sobre todo a la tarde.',
    triage_level: 'yellow',
    attention_level: '24-48h',
    created_at: '2026-04-18T19:02:00',
    status: 'resolved',
  },
  {
    id: 'c4',
    title: 'Higiene del sueño',
    chief_complaint: 'Me cuesta dormir hace un mes, doy vueltas en la cama 1-2 horas.',
    triage_level: 'green',
    attention_level: 'rutina',
    created_at: '2026-04-10T22:48:00',
    status: 'resolved',
  },
]

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const [cases, setCases] = useState<DashboardCase[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function fetchCases() {
      setLoading(true)
      try {
        // One-line swap when endpoint is ready: remove the catch fallback below.
        const data = await api.get<DashboardCase[]>('/api/v1/cases?limit=5')
        if (!cancelled) setCases(data)
      } catch {
        // TODO: once GET /api/v1/cases is wired, surface errors instead of mock data
        if (!cancelled) setCases(MOCK_CASES)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchCases()
    return () => {
      cancelled = true
    }
  }, [])

  const isPaid = user?.subscriptionTier === 'paid'

  return (
    <div className="flex-1 overflow-auto p-6 space-y-8">
      <div className="flex items-start justify-between gap-4">
        {user && (
          <Greeting
            displayName={user.displayName}
            email={user.email}
          />
        )}
        <a href="/chat">
          <Button size="lg">Nueva consulta</Button>
        </a>
      </div>

      {!isPaid && user && (
        <TierUpgradeBanner
          requiredTier="paid"
          currentTier={user.subscriptionTier}
          onUpgrade={() => {
            window.location.href = '/settings'
          }}
        />
      )}

      <section aria-labelledby="stats-heading">
        <h2 id="stats-heading" className="sr-only">
          Estadísticas
        </h2>
        <StatsRow cases={cases} />
      </section>

      <section aria-labelledby="recent-heading">
        <div className="mb-4 flex items-center justify-between">
          <h2
            id="recent-heading"
            className="text-lg font-semibold tracking-tight"
          >
            Tus consultas recientes
          </h2>
          <a
            href="/history"
            className="text-sm text-[var(--tm-blue-600)] hover:underline"
          >
            Ver todas
          </a>
        </div>
        <RecentCases cases={cases} loading={loading} />
      </section>

      <section aria-labelledby="quicklinks-heading">
        <h2
          id="quicklinks-heading"
          className="mb-4 text-lg font-semibold tracking-tight"
        >
          Accesos rápidos
        </h2>
        <QuickActions />
      </section>
    </div>
  )
}
