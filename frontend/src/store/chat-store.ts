import { create } from 'zustand'

export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'authenticating'
  | 'connected'
  | 'error'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  agentsInvolved?: string[]
  caseId?: string
}

interface ChatError {
  code: string
  message: string
}

interface ChatState {
  messages: Message[]
  isLoading: boolean
  currentCaseId: string | null
  // Streaming state
  streamingMessage: string | null
  connectionStatus: ConnectionStatus
  currentAgentNode: string | null
  error: ChatError | null
  // Existing actions
  addMessage: (message: Message) => void
  setLoading: (loading: boolean) => void
  setCurrentCase: (caseId: string | null) => void
  clearMessages: () => void
  // Streaming actions
  appendToken: (chunk: string) => void
  setAgentNode: (agent: string | null) => void
  setConnectionStatus: (status: ConnectionStatus) => void
  commitStreamingMessage: (fullResponse: string, caseId: string) => void
  setError: (code: string, message: string) => void
  addUserMessage: (content: string) => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  currentCaseId: null,
  streamingMessage: null,
  connectionStatus: 'disconnected',
  currentAgentNode: null,
  error: null,

  // Existing actions
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setLoading: (loading) => set({ isLoading: loading }),
  setCurrentCase: (caseId) => set({ currentCaseId: caseId }),
  clearMessages: () => set({ messages: [] }),

  // Streaming actions
  appendToken: (chunk) =>
    set((state) => ({
      streamingMessage: (state.streamingMessage ?? '') + chunk,
    })),

  setAgentNode: (agent) => set({ currentAgentNode: agent }),

  setConnectionStatus: (status) => set({ connectionStatus: status }),

  commitStreamingMessage: (fullResponse, caseId) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: fullResponse,
          timestamp: new Date(),
          agentsInvolved: [],
          caseId,
        },
      ],
      streamingMessage: null,
      currentAgentNode: null,
      currentCaseId: caseId,
    })),

  setError: (code, message) =>
    set({ isLoading: false, error: { code, message } }),

  addUserMessage: (content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: crypto.randomUUID(),
          role: 'user',
          content,
          timestamp: new Date(),
        },
      ],
    })),
}))
