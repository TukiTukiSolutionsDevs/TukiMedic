import { Search } from 'lucide-react'

export type TriageFilter = 'all' | 'green' | 'yellow' | 'red'
export type SinceFilter = '7d' | '30d' | '90d' | 'all'

interface FilterBarProps {
  query: string
  onQueryChange: (v: string) => void
  triage: TriageFilter
  onTriageChange: (v: TriageFilter) => void
  since: SinceFilter
  onSinceChange: (v: SinceFilter) => void
}

const TRIAGE_CHIPS: { label: string; value: TriageFilter }[] = [
  { label: 'Todos', value: 'all' },
  { label: 'Verde', value: 'green' },
  { label: 'Amarillo', value: 'yellow' },
  { label: 'Rojo', value: 'red' },
]

const SINCE_OPTIONS: { label: string; value: SinceFilter }[] = [
  { label: 'Última semana', value: '7d' },
  { label: 'Último mes', value: '30d' },
  { label: 'Últimos 3 meses', value: '90d' },
  { label: 'Todos', value: 'all' },
]

export function FilterBar({
  query,
  onQueryChange,
  triage,
  onTriageChange,
  since,
  onSinceChange,
}: FilterBarProps) {
  return (
    <div className="space-y-3">
      <div className="relative">
        <Search
          className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <input
          type="text"
          placeholder="Buscar por motivo de consulta..."
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          className="flex h-8 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/50"
          aria-label="Buscar casos"
        />
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por triage">
        {TRIAGE_CHIPS.map((chip) => (
          <button
            key={chip.value}
            type="button"
            aria-pressed={triage === chip.value}
            onClick={() => onTriageChange(chip.value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              triage === chip.value
                ? 'border-foreground bg-foreground text-background'
                : 'border-border bg-background text-muted-foreground hover:bg-muted'
            }`}
          >
            {chip.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por período">
        {SINCE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            aria-pressed={since === opt.value}
            onClick={() => onSinceChange(opt.value)}
            className={`rounded-md border px-3 py-1 text-xs transition-colors ${
              since === opt.value
                ? 'border-foreground bg-foreground text-background'
                : 'border-border bg-background text-muted-foreground hover:bg-muted'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}
