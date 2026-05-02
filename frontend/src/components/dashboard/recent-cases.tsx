import { Skeleton } from '@/components/ui/skeleton'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card'

export interface DashboardCase {
  id: string
  title: string | null
  chief_complaint?: string
  triage_level?: 'green' | 'yellow' | 'red'
  attention_level?: string
  created_at: string
  status: string
}

const TRIAGE_DOT_CLASS: Record<string, string> = {
  green: 'bg-[var(--tm-green-500)]',
  yellow: 'bg-[var(--tm-yellow-400)]',
  red: 'bg-[var(--tm-red-500)]',
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffDays = (now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24)
  if (diffDays < 1) return 'Hoy'
  if (diffDays < 2) return 'Ayer'
  if (diffDays < 7) return `Hace ${Math.floor(diffDays)} días`
  return d.toLocaleDateString('es-AR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

interface RecentCasesProps {
  cases: DashboardCase[]
  loading: boolean
}

export function RecentCases({ cases, loading }: RecentCasesProps) {
  if (loading) {
    return (
      <div className="space-y-3" aria-busy="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    )
  }

  if (cases.length === 0) {
    return (
      <p
        className="py-10 text-center text-sm text-muted-foreground"
        data-testid="empty-state"
      >
        No tenés consultas recientes. ¡Iniciá tu primera!
      </p>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {cases.map((c) => (
        <a
          key={c.id}
          href={`/cases/${c.id}`}
          className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Card className="h-full cursor-pointer transition-shadow hover:ring-foreground/20">
            <CardHeader>
              <div className="flex items-center gap-2">
                {c.triage_level && (
                  <span
                    className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${TRIAGE_DOT_CLASS[c.triage_level] ?? 'bg-muted'}`}
                    aria-label={`Triage: ${c.triage_level}`}
                    data-testid="triage-dot"
                  />
                )}
                <CardTitle className="line-clamp-1 text-sm">
                  {c.title ?? 'Caso sin título'}
                </CardTitle>
              </div>
              <CardDescription>{formatDate(c.created_at)}</CardDescription>
            </CardHeader>
            {c.chief_complaint && (
              <CardContent>
                <p className="line-clamp-2 text-xs text-muted-foreground">
                  {c.chief_complaint}
                </p>
              </CardContent>
            )}
          </Card>
        </a>
      ))}
    </div>
  )
}
