import { FileText } from 'lucide-react'

interface EmptyStateProps {
  hasFilters: boolean
  onClearFilters: () => void
}

export function EmptyState({ hasFilters, onClearFilters }: EmptyStateProps) {
  if (hasFilters) {
    return (
      <div
        className="flex flex-col items-center gap-3 py-16 text-center"
        data-testid="empty-filters"
      >
        <p className="text-sm text-muted-foreground">No hay casos con esos filtros.</p>
        <button
          type="button"
          onClick={onClearFilters}
          className="rounded-md border px-3 py-1 text-xs hover:bg-muted"
        >
          Limpiar filtros
        </button>
      </div>
    )
  }

  return (
    <div
      className="flex flex-col items-center gap-4 py-16 text-center"
      data-testid="empty-state"
    >
      <FileText className="size-10 text-muted-foreground/40" aria-hidden="true" />
      <p className="text-sm text-muted-foreground">Aún no tenés consultas.</p>
      <a
        href="/chat"
        className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        Iniciar consulta
      </a>
    </div>
  )
}
