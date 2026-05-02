'use client'

import { useEffect, useRef, useState } from 'react'
import { Send, Paperclip, Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ChatInputProps {
  onSend: (content: string) => void
  onFileSelect?: (file: File) => void
  disabled?: boolean
  isPaidTier?: boolean
  isUploading?: boolean
}

export function ChatInput({
  onSend,
  onFileSelect,
  disabled = false,
  isPaidTier = false,
  isUploading = false,
}: ChatInputProps) {
  const [text, setText] = useState('')
  const taRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Auto-grow textarea up to 200px
  useEffect(() => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [text])

  function send() {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    onFileSelect?.(file)
    e.target.value = ''
  }

  const placeholder = disabled
    ? 'Esperá a que termine la respuesta…'
    : 'Contanos qué te pasa, desde cuándo y con qué intensidad…'

  return (
    <div
      className={cn(
        'rounded-2xl border bg-card shadow-[0_8px_32px_-12px_rgba(15,23,42,0.12),0_2px_6px_-1px_rgba(15,23,42,0.04)] transition-colors',
        !disabled && 'focus-within:border-ring',
      )}
    >
      {/* Hidden real file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        className="hidden"
        onChange={handleFileChange}
        aria-label="Adjuntar archivo"
      />

      {/* Textarea */}
      <textarea
        ref={taRef}
        data-testid="chat-textarea"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        rows={1}
        className="w-full resize-none border-none bg-transparent px-4 py-3.5 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
        style={{ minHeight: 48 }}
      />

      {/* Toolbar */}
      <div className="flex items-center justify-between border-t border-border px-3 pb-2.5 pt-2">
        {/* Paperclip — gated by tier */}
        <div>
          {isPaidTier ? (
            <button
              type="button"
              data-testid="attach-button"
              disabled={isUploading || disabled}
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Paperclip size={13} />
              Adjuntar (PDF, foto)
            </button>
          ) : (
            <button
              type="button"
              data-testid="attach-button-locked"
              disabled
              title="Disponible en Tuki Pro"
              className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground/50"
            >
              <Lock size={13} />
              Adjuntar (Pro)
            </button>
          )}
        </div>

        {/* Send */}
        <Button
          size="sm"
          data-testid="send-button"
          onClick={send}
          disabled={disabled || !text.trim()}
        >
          <Send size={14} className="mr-1.5" />
          Enviar
        </Button>
      </div>
    </div>
  )
}
