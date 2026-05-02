'use client'

import { cn } from '@/lib/utils'

const AGENT_LABELS: Record<string, string> = {
  triage: 'Triage',
  anamnesis: 'Anamnesis',
  classification: 'Clasificación',
  classifier: 'Clasificación',
  specialists: 'Especialistas',
  general_medicine: 'Medicina General',
  medical_board: 'Mesa Médica',
  devils_advocate: 'Revisión Crítica',
  synthesizer: 'Síntesis',
  guardrail: 'Verificación',
}

// Ordered list that drives the panel display
const PANEL_AGENTS = [
  'triage',
  'anamnesis',
  'classification',
  'specialists',
  'medical_board',
  'synthesizer',
  'guardrail',
]

// Map backend names to canonical panel ids
const TO_PANEL_ID: Record<string, string> = {
  triage: 'triage',
  anamnesis: 'anamnesis',
  classification: 'classification',
  classifier: 'classification',
  specialists: 'specialists',
  general_medicine: 'specialists',
  medical_board: 'medical_board',
  devils_advocate: 'medical_board',
  synthesizer: 'synthesizer',
  guardrail: 'guardrail',
}

interface AgentsPanelProps {
  currentAgent: string | null
  isLoading: boolean
}

export function AgentsPanel({ currentAgent, isLoading }: AgentsPanelProps) {
  if (!isLoading && !currentAgent) return null

  const activeId = currentAgent ? (TO_PANEL_ID[currentAgent] ?? currentAgent) : null
  const activeIdx = activeId ? PANEL_AGENTS.indexOf(activeId) : -1

  return (
    <aside
      data-testid="agents-panel"
      className="hidden w-60 shrink-0 flex-col border-l bg-muted/30 md:flex"
    >
      <div className="border-b px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Mesa de Especialistas
        </p>
      </div>

      <div className="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
        {PANEL_AGENTS.map((id, idx) => {
          const isDone = activeIdx > idx
          const isActive = activeIdx === idx
          const isPending = activeIdx < idx || activeIdx === -1

          return (
            <div
              key={id}
              data-testid={`agent-row-${id}`}
              className={cn(
                'flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors',
                isActive &&
                  'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300',
                isDone && 'text-muted-foreground',
                isPending && !isActive && !isDone && 'text-muted-foreground/40',
              )}
            >
              <span
                className={cn(
                  'h-1.5 w-1.5 flex-shrink-0 rounded-full',
                  isActive && 'animate-pulse bg-blue-500',
                  isDone && 'bg-green-500',
                  isPending && !isActive && !isDone && 'bg-muted-foreground/30',
                )}
              />
              <span className={cn('font-medium', isActive && 'font-semibold')}>
                {AGENT_LABELS[id] ?? id}
              </span>
              {isActive && (
                <span className="ml-auto font-mono text-[10px] opacity-60">analizando</span>
              )}
              {isDone && (
                <svg
                  className="ml-auto h-3 w-3 shrink-0 text-green-500"
                  viewBox="0 0 12 12"
                  fill="none"
                >
                  <path
                    d="M2 6l3 3 5-5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </div>
          )
        })}
      </div>
    </aside>
  )
}
