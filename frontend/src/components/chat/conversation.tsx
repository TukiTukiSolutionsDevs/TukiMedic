'use client'

import { useEffect, useRef } from 'react'
import { UserBubble, AssistantBubble, AgentProgress } from './message-bubble'

const EMPTY_EXAMPLES = [
  {
    title: 'Pediátrica',
    body: 'Mi nena de 4 años tiene 37.8°C. ¿Cuánto paracetamol le doy?',
  },
  {
    title: 'Lesión deportiva',
    body: 'Hace 3 días corrí y me lastimé la rodilla, hincha y duele al apoyar.',
  },
  {
    title: 'Cefalea',
    body: 'Dolores de cabeza desde hace 2 semanas, sobre todo a la tarde.',
  },
]

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
}

interface ConversationProps {
  messages: Message[]
  streamingMessage: string | null
  isLoading: boolean
  currentAgentNode: string | null
  onPrompt?: (text: string) => void
  onDownloadPdf?: () => void
}

export function Conversation({
  messages,
  streamingMessage,
  isLoading,
  currentAgentNode,
  onPrompt,
  onDownloadPdf,
}: ConversationProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMessage, currentAgentNode])

  const isEmpty = messages.length === 0 && streamingMessage === null && !isLoading

  if (isEmpty) {
    return (
      <div
        data-testid="chat-empty"
        className="flex flex-1 flex-col items-center justify-center gap-8 px-8 py-10 text-center"
      >
        <div>
          <h2 className="text-4xl font-normal tracking-tight leading-tight">
            ¿Qué te trae{' '}
            <em className="not-italic text-blue-600">hoy</em>?
          </h2>
          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
            Contanos qué síntomas tenés, desde cuándo y con qué intensidad. Tu caso pasa por
            triage, especialistas y mesa médica antes de la respuesta — puede tardar hasta 2
            minutos.
          </p>
        </div>

        <div className="grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
          {EMPTY_EXAMPLES.map((ex) => (
            <button
              key={ex.title}
              type="button"
              onClick={() => onPrompt?.(ex.body)}
              className="flex flex-col gap-2 rounded-xl border bg-card p-4 text-left text-sm transition-all hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md"
            >
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {ex.title}
              </span>
              <span className="leading-relaxed text-foreground">"{ex.body}"</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-8 md:px-8">
      <div className="mx-auto max-w-[920px]">
        {messages.map((msg) =>
          msg.role === 'user' ? (
            <UserBubble key={msg.id} text={msg.content} />
          ) : (
            <AssistantBubble key={msg.id} content={msg.content} onDownloadPdf={onDownloadPdf} />
          ),
        )}

        {/* Streaming text */}
        {streamingMessage !== null && (
          <AssistantBubble content={streamingMessage} isStreaming />
        )}

        {/* Agent progress (processing, no text yet) */}
        {isLoading && streamingMessage === null && (
          <div className="mb-6 flex gap-3 animate-in fade-in slide-in-from-bottom-1 duration-200">
            <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full border border-border bg-muted text-[10px] font-semibold text-muted-foreground">
              TM
            </div>
            <div className="min-w-0 flex-1">
              <AgentProgress currentAgent={currentAgentNode} />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
