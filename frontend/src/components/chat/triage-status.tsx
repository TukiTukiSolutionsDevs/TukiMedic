'use client'

export type TriageLevel = 'green' | 'yellow' | 'red'

const CONFIG = {
  green: {
    label: 'Rutina',
    dot: 'bg-green-500',
    text: 'text-green-700 dark:text-green-400',
    bg: 'bg-green-50 border-green-200 dark:bg-green-950/40 dark:border-green-800',
  },
  yellow: {
    label: 'Atención',
    dot: 'bg-amber-500',
    text: 'text-amber-700 dark:text-amber-400',
    bg: 'bg-amber-50 border-amber-200 dark:bg-amber-950/40 dark:border-amber-800',
  },
  red: {
    label: 'Urgencia',
    dot: 'bg-red-500',
    text: 'text-red-700 dark:text-red-400',
    bg: 'bg-red-50 border-red-200 dark:bg-red-950/40 dark:border-red-800',
  },
} as const

export interface TriageStatusProps {
  level: TriageLevel | null
  /** Animate the dot while the model is still analyzing */
  isActive?: boolean
}

export function TriageStatus({ level, isActive = false }: TriageStatusProps) {
  if (!level) return null
  const cfg = CONFIG[level]
  return (
    <span
      data-testid="triage-status"
      data-level={level}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${cfg.bg} ${cfg.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot} ${isActive ? 'animate-pulse' : ''}`} />
      {cfg.label}
    </span>
  )
}
