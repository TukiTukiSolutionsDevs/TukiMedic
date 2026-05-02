import { Lock, FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export interface HistoryCase {
  id: string
  title: string | null
  chief_complaint?: string
  triage_level?: 'green' | 'yellow' | 'red'
  specialties?: string[]
  status: string
  created_at: string
}

const TRIAGE_DOT: Record<string, string> = {
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

interface CaseRowProps {
  c: HistoryCase
  isPaid: boolean
}

export function CaseRow({ c, isPaid }: CaseRowProps) {
  const label = c.title ?? c.chief_complaint ?? 'Caso sin título'
  const specialties = c.specialties ?? []
  const visible = specialties.slice(0, 3)
  const overflow = specialties.length - visible.length

  return (
    <div
      data-testid="case-row"
      className="flex items-center gap-3 rounded-xl border bg-card px-4 py-3 transition-shadow hover:shadow-sm"
    >
      {c.triage_level && (
        <span
          className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${TRIAGE_DOT[c.triage_level] ?? 'bg-muted'}`}
          aria-label={`Triage: ${c.triage_level}`}
          data-testid="triage-dot"
        />
      )}

      <span className="w-20 shrink-0 text-xs text-muted-foreground">
        {formatDate(c.created_at)}
      </span>

      <span className="min-w-0 flex-1 truncate text-sm font-medium">{label}</span>

      <div className="hidden shrink-0 items-center gap-1 sm:flex">
        {visible.map((s) => (
          <Badge key={s} variant="secondary" className="text-xs">
            {s}
          </Badge>
        ))}
        {overflow > 0 && (
          <Badge variant="outline" className="text-xs">
            +{overflow}
          </Badge>
        )}
      </div>

      <Badge variant="outline" className="shrink-0 text-xs">
        {c.status}
      </Badge>

      {isPaid ? (
        <button
          type="button"
          aria-label="Exportar PDF"
          data-testid="pdf-button"
          className="flex size-7 shrink-0 items-center justify-center rounded-md hover:bg-muted"
        >
          <FileText className="size-3.5" />
        </button>
      ) : (
        <span
          className="flex size-7 shrink-0 items-center justify-center text-muted-foreground/40"
          aria-label="PDF disponible en plan pagado"
          data-testid="pdf-locked"
        >
          <Lock className="size-3.5" />
        </span>
      )}

      <a
        href={`/cases/${c.id}`}
        className="shrink-0 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted"
      >
        Ver
      </a>
    </div>
  )
}
