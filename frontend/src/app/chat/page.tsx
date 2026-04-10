'use client'

import { type FormEvent, useEffect, useRef, useState } from 'react'
import { useChatWS } from '@/hooks/use-chat-ws'
import { useChatStore, type ConnectionStatus } from '@/store/chat-store'
import { Button } from '@/components/ui/button'

const AGENT_LABELS: Record<string, string> = {
  triage: 'Triage',
  anamnesis: 'Anamnesis',
  classifier: 'Clasificador',
  general_medicine: 'Medicina General',
  medical_board: 'Mesa Médica',
  devils_advocate: 'Abogado del Diablo',
  guardrail: 'Guardrail',
  synthesizer: 'Síntesis',
}

const STATUS_CONFIG: Record<ConnectionStatus, { dot: string; label: string }> = {
  disconnected: { dot: 'bg-gray-400', label: 'Desconectado' },
  connecting: { dot: 'bg-yellow-400 animate-pulse', label: 'Conectando...' },
  authenticating: { dot: 'bg-yellow-400 animate-pulse', label: 'Autenticando...' },
  connected: { dot: 'bg-green-500', label: 'Conectado' },
  error: { dot: 'bg-red-500', label: 'Error de conexión' },
}

function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  const { dot, label } = STATUS_CONFIG[status]
  return (
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {label}
    </div>
  )
}

export default function ChatPage() {
  const { sendMessage, connectionStatus } = useChatWS()
  const {
    messages,
    streamingMessage,
    isLoading,
    currentAgentNode,
    currentCaseId,
  } = useChatStore()

  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMessage])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || connectionStatus !== 'connected' || isLoading) return
    sendMessage(trimmed, currentCaseId)
    setInput('')
  }

  const isDisabled = connectionStatus !== 'connected' || isLoading

  return (
    <div className="flex flex-1 flex-col">
      {/* Header */}
      <header className="flex h-14 items-center justify-between border-b px-4">
        <h2 className="font-semibold">Nueva consulta</h2>
        <ConnectionBadge status={connectionStatus} />
      </header>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && streamingMessage === null && (
          <p className="text-center text-sm text-muted-foreground">
            Describe tus síntomas para comenzar el análisis
          </p>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[75%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-foreground'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {/* Streaming partial message */}
        {streamingMessage !== null && (
          <div className="flex justify-start">
            <div className="max-w-[75%] rounded-lg bg-muted px-4 py-2 text-sm text-foreground whitespace-pre-wrap">
              {streamingMessage}
              <span className="ml-1 inline-block h-3 w-0.5 animate-pulse bg-current align-middle" />
            </div>
          </div>
        )}

        {/* Agent activity indicator */}
        {isLoading && currentAgentNode && (
          <div className="flex justify-start">
            <div className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
              🔍 {AGENT_LABELS[currentAgentNode] ?? currentAgentNode} analizando...
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="border-t p-4">
        <form onSubmit={handleSubmit} className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e as unknown as FormEvent)
              }
            }}
            disabled={isDisabled}
            placeholder={
              connectionStatus !== 'connected'
                ? 'Conectando...'
                : 'Describe tus síntomas... (Enter para enviar, Shift+Enter para nueva línea)'
            }
            rows={3}
            className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          />
          <Button type="submit" disabled={isDisabled || !input.trim()}>
            {isLoading ? 'Procesando...' : 'Enviar'}
          </Button>
        </form>
      </div>
    </div>
  )
}
