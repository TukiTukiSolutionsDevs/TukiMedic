'use client'

import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '@/store/auth-store'
import { useChatStore, type ConnectionStatus } from '@/store/chat-store'

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'
const WS_ENDPOINT = `${WS_BASE}/api/v1/chat/ws`
const BACKOFF_MS = [1000, 2000, 4000, 8000, 30000]
const PING_INTERVAL_MS = 25_000

export interface UseChatWSReturn {
  sendMessage: (content: string, caseId?: string | null) => void
  connectionStatus: ConnectionStatus
  isConnected: boolean
  disconnect: () => void
}

export function useChatWS(): UseChatWSReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const intentionalRef = useRef(false)
  const attemptRef = useRef(0)
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [connectionStatus, setLocalStatus] = useState<ConnectionStatus>('disconnected')

  const accessToken = useAuthStore((s) => s.accessToken)
  const {
    appendToken,
    setAgentNode,
    setConnectionStatus: storeSetStatus,
    commitStreamingMessage,
    setError,
    setLoading,
  } = useChatStore()

  function setStatus(status: ConnectionStatus) {
    setLocalStatus(status)
    storeSetStatus(status)
  }

  function clearPing() {
    if (pingTimerRef.current !== null) {
      clearInterval(pingTimerRef.current)
      pingTimerRef.current = null
    }
  }

  function startPing(ws: WebSocket) {
    clearPing()
    pingTimerRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, PING_INTERVAL_MS)
  }

  function connect() {
    if (!accessToken) return

    const ws = new WebSocket(WS_ENDPOINT)
    wsRef.current = ws
    setStatus('connecting')

    ws.onopen = () => {
      attemptRef.current = 0
      ws.send(JSON.stringify({ type: 'auth', token: accessToken }))
      setStatus('authenticating')
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      let msg: Record<string, unknown>
      try {
        msg = JSON.parse(event.data) as Record<string, unknown>
      } catch {
        return
      }

      switch (msg.type) {
        case 'auth_ok':
          setStatus('connected')
          startPing(ws)
          break
        case 'agent_start':
          setAgentNode(msg.agent as string)
          break
        case 'token':
          appendToken(msg.content as string)
          break
        case 'done':
          commitStreamingMessage(msg.response as string, msg.case_id as string)
          setLoading(false)
          setAgentNode(null)
          break
        case 'pong':
          // no-op — keep-alive acknowledged
          break
        case 'error':
          setError(msg.code as string, msg.message as string)
          setStatus('error')
          break
      }
    }

    ws.onclose = () => {
      clearPing()
      if (!intentionalRef.current && attemptRef.current < BACKOFF_MS.length) {
        const delay = BACKOFF_MS[attemptRef.current]
        attemptRef.current++
        setTimeout(connect, delay)
      } else {
        setStatus('disconnected')
      }
    }

    ws.onerror = () => {
      setStatus('error')
    }
  }

  useEffect(() => {
    intentionalRef.current = false
    if (accessToken) connect()

    return () => {
      intentionalRef.current = true
      clearPing()
      wsRef.current?.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken])

  function sendMessage(content: string, caseId?: string | null) {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    setLoading(true)
    wsRef.current.send(
      JSON.stringify({ type: 'message', content, case_id: caseId ?? null })
    )
  }

  function disconnect() {
    intentionalRef.current = true
    clearPing()
    wsRef.current?.close()
  }

  return {
    sendMessage,
    connectionStatus,
    isConnected: connectionStatus === 'connected',
    disconnect,
  }
}
