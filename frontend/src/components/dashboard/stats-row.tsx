import { Check, Shield, Clock } from 'lucide-react'
import type { ComponentType } from 'react'

import { Card, CardContent } from '@/components/ui/card'
import type { DashboardCase } from './recent-cases'

interface StatCardProps {
  Icon: ComponentType<{ size?: number; className?: string }>
  label: string
  value: number
  sub: string
  iconClass: string
}

function StatCard({ Icon, label, value, sub, iconClass }: StatCardProps) {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="mb-2 flex items-center gap-3">
          <div
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${iconClass}`}
          >
            <Icon size={18} />
          </div>
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            {label}
          </span>
        </div>
        <p
          className="text-3xl font-semibold tracking-tight"
          data-testid="stat-value"
        >
          {value}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
      </CardContent>
    </Card>
  )
}

interface StatsRowProps {
  cases: DashboardCase[]
}

export function StatsRow({ cases }: StatsRowProps) {
  const total = cases.length
  const routine = cases.filter((c) => c.triage_level === 'green').length
  const urgent = cases.filter(
    (c) => c.triage_level === 'yellow' || c.triage_level === 'red',
  ).length

  return (
    <div
      className="grid grid-cols-1 gap-4 sm:grid-cols-3"
      data-testid="stats-row"
    >
      <StatCard
        Icon={Clock}
        label="Consultas totales"
        value={total}
        sub="Total histórico"
        iconClass="bg-[var(--tm-blue-50)] text-[var(--tm-blue-700)]"
      />
      <StatCard
        Icon={Check}
        label="Rutina"
        value={routine}
        sub="Sin alarmas"
        iconClass="bg-[var(--tm-green-50)] text-[var(--tm-green-700)]"
      />
      <StatCard
        Icon={Shield}
        label="Atención pronta"
        value={urgent}
        sub="Consultá en 24-48h"
        iconClass="bg-[var(--tm-amber-50)] text-[var(--tm-amber-700)]"
      />
    </div>
  )
}
