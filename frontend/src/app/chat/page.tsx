'use client'

import { type FormEvent, useEffect, useRef, useState } from 'react'
import { useChatWS } from '@/hooks/use-chat-ws'
import { useDocumentUpload } from '@/hooks/use-document-upload'
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
  const { uploadDocument, isUploading, uploadError, lastUploadedDoc } = useDocumentUpload()
  const {
    messages,
    streamingMessage,
    isLoading,
    currentAgentNode,
    currentCaseId,
  } = useChatStore()

  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    uploadDocument(file, currentCaseId ?? undefined)
    e.target.value = ''
  }

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
        {/* Upload status feedback */}
        {isUploading && (
          <p className="mb-2 text-xs text-muted-foreground">📎 Subiendo archivo...</p>
        )}
        {uploadError && (
          <p className="mb-2 text-xs text-red-500">⚠️ {uploadError}</p>
        )}
        {lastUploadedDoc && !isUploading && (
          <p className="mb-2 text-xs text-green-600">
            ✅ Archivo subido — procesando en segundo plano
          </p>
        )}

        <form onSubmit={handleSubmit} className="flex gap-2 items-end">
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            className="hidden"
            onChange={handleFileSelect}
          />

          {/* Paperclip button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            title="Adjuntar documento (PDF, JPG, PNG)"
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md border border-input bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>

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
