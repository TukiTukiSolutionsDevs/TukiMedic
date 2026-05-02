'use client'

import React from 'react'
import { Download, Copy } from 'lucide-react'
import { Disclaimer } from './disclaimer'
import { cn } from '@/lib/utils'

// ── Lightweight Markdown renderer ─────────────────────────────────────

function inlineMd(s: string): React.ReactNode {
  const parts: React.ReactNode[] = []
  const re = /\*\*([^*]+)\*\*/g
  let last = 0
  let k = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) parts.push(s.slice(last, m.index))
    parts.push(
      <strong key={k++} className="font-semibold text-foreground">
        {m[1]}
      </strong>,
    )
    last = m.index + m[0].length
  }
  if (last < s.length) parts.push(s.slice(last))
  return parts.length ? parts : s
}

export function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split('\n')
  const out: React.ReactNode[] = []
  let i = 0
  let key = 0

  while (i < lines.length) {
    const line = lines[i]
    if (/^## /.test(line)) {
      out.push(
        <h3 key={key++} className="mb-2 mt-5 text-[15px] font-semibold tracking-tight">
          {inlineMd(line.replace(/^## /, ''))}
        </h3>,
      )
      i++
    } else if (/^# /.test(line)) {
      out.push(
        <h2 key={key++} className="mb-2 mt-5 text-lg font-semibold tracking-tight">
          {inlineMd(line.replace(/^# /, ''))}
        </h2>,
      )
      i++
    } else if (/^[-*] /.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^[-*] /.test(lines[i])) {
        items.push(lines[i].replace(/^[-*] /, ''))
        i++
      }
      out.push(
        <ul key={key++} className="my-1.5 mb-3 list-disc pl-5 leading-relaxed">
          {items.map((it, j) => (
            <li key={j} className="mb-1">
              {inlineMd(it)}
            </li>
          ))}
        </ul>,
      )
    } else if (/^\d+\. /.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\. /, ''))
        i++
      }
      out.push(
        <ol key={key++} className="my-1.5 mb-3 list-decimal pl-5 leading-relaxed">
          {items.map((it, j) => (
            <li key={j} className="mb-1">
              {inlineMd(it)}
            </li>
          ))}
        </ol>,
      )
    } else if (line.trim() === '') {
      i++
    } else {
      out.push(
        <p key={key++} className="mb-3 leading-relaxed">
          {inlineMd(line)}
        </p>,
      )
      i++
    }
  }
  return out
}

// ── User bubble ────────────────────────────────────────────────────────

export function UserBubble({ text }: { text: string }) {
  return (
    <div
      data-testid="user-message"
      className="mb-5 flex justify-end animate-in fade-in slide-in-from-bottom-1 duration-200"
    >
      <div className="max-w-[70%] rounded-[18px_18px_4px_18px] bg-blue-600 px-4 py-3 text-sm leading-relaxed text-white shadow-sm">
        {text}
      </div>
    </div>
  )
}

// ── Agent processing timeline ──────────────────────────────────────────

const ORDERED_STEPS: { id: string; label: string }[] = [
  { id: 'triage', label: 'Evaluando urgencia' },
  { id: 'anamnesis', label: 'Procesando tu relato' },
  { id: 'classification', label: 'Identificando especialidades' },
  { id: 'specialists', label: 'Consultando especialistas' },
  { id: 'medical_board', label: 'Mesa médica deliberando' },
  { id: 'synthesizer', label: 'Sintetizando respuesta' },
  { id: 'guardrail', label: 'Revisando recomendaciones' },
]

// Map backend agent names to canonical step id
const AGENT_TO_STEP: Record<string, string> = {
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

export function AgentProgress({ currentAgent }: { currentAgent: string | null }) {
  const canonicalId = currentAgent ? (AGENT_TO_STEP[currentAgent] ?? currentAgent) : null
  const activeIdx = canonicalId ? ORDERED_STEPS.findIndex((s) => s.id === canonicalId) : 0

  return (
    <div
      data-testid="agent-progress"
      className="max-w-[620px] rounded-2xl border bg-card p-5 shadow-sm animate-in fade-in slide-in-from-bottom-1 duration-200"
    >
      <div className="mb-4 flex items-center gap-2.5">
        <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
        <span className="text-[13px] font-medium">Tu caso está siendo revisado</span>
        <span className="ml-auto font-mono text-[11px] text-muted-foreground">~2 min</span>
      </div>

      <div className="flex flex-col">
        {ORDERED_STEPS.map(({ id, label }, idx) => {
          const isDone = activeIdx > idx
          const isActive = activeIdx === idx
          const isPending = activeIdx < idx

          return (
            <div
              key={id}
              className={cn(
                'flex items-start gap-3.5 py-2 transition-opacity duration-300',
                isPending && 'opacity-40',
              )}
            >
              <div className="relative flex-shrink-0">
                <div
                  className={cn(
                    'flex h-7 w-7 items-center justify-center rounded-full border transition-all duration-300',
                    isDone && 'border-green-300 bg-green-50 text-green-600',
                    isActive && 'border-blue-300 bg-blue-50 text-blue-600',
                    isPending && 'border-border bg-muted text-muted-foreground',
                  )}
                >
                  {isDone ? (
                    <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                      <path
                        d="M2 5.5l2.5 2.5 4.5-4.5"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : isActive ? (
                    <span className="h-2 w-2 rounded-full bg-current animate-pulse" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  )}
                </div>
                {idx < ORDERED_STEPS.length - 1 && (
                  <div
                    className={cn(
                      'absolute left-3 top-7 w-0.5 transition-colors duration-300',
                      'h-[calc(100%+12px)]',
                      isDone ? 'bg-green-300' : 'bg-border',
                    )}
                  />
                )}
              </div>
              <div className="min-w-0 flex-1 pt-0.5">
                <span
                  className={cn(
                    'text-[13.5px] tracking-tight',
                    isActive ? 'font-semibold text-foreground' : 'font-medium',
                    isPending && 'text-muted-foreground',
                  )}
                >
                  {label}
                  {isActive && (
                    <span className="ml-1.5 font-mono text-[11px] text-blue-600">en curso…</span>
                  )}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Assistant bubble ───────────────────────────────────────────────────

function ActionButton({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      {icon}
      {label}
    </button>
  )
}

interface AssistantBubbleProps {
  content: string
  isStreaming?: boolean
  onDownloadPdf?: () => void
}

export function AssistantBubble({
  content,
  isStreaming = false,
  onDownloadPdf,
}: AssistantBubbleProps) {
  return (
    <div
      data-testid="assistant-message"
      className="mb-6 flex gap-3 animate-in fade-in slide-in-from-bottom-1 duration-200"
    >
      {/* Avatar */}
      <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full border border-border bg-muted text-[10px] font-semibold text-muted-foreground">
        TM
      </div>

      <div className="min-w-0 max-w-[720px] flex-1">
        {/* Bubble */}
        <div className="rounded-[4px_18px_18px_18px] border bg-card px-[22px] py-[18px] text-sm text-foreground shadow-sm">
          {renderMarkdown(content)}

          {isStreaming && (
            <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-blue-600 align-middle" />
          )}

          {/* Always-visible disclaimer — only on complete messages */}
          {!isStreaming && (
            <div className="-mx-[22px] mt-4 border-t border-border px-[22px] pt-3">
              <Disclaimer compact />
            </div>
          )}
        </div>

        {/* Action row */}
        {!isStreaming && (
          <div className="mt-2 flex gap-1 pl-1">
            <ActionButton
              icon={<Download size={12} />}
              label="PDF para tu médico"
              onClick={onDownloadPdf}
            />
            <ActionButton
              icon={<Copy size={12} />}
              label="Copiar"
              onClick={() => {
                navigator.clipboard.writeText(content).catch(() => {})
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
