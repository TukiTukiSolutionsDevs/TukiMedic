import { create } from 'zustand'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  agentsInvolved?: string[]
}

interface ChatState {
  messages: Message[]
  isLoading: boolean
  currentCaseId: string | null
  addMessage: (message: Message) => void
  setLoading: (loading: boolean) => void
  setCurrentCase: (caseId: string | null) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  currentCaseId: null,
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setLoading: (loading) => set({ isLoading: loading }),
  setCurrentCase: (caseId) => set({ currentCaseId: caseId }),
  clearMessages: () => set({ messages: [] }),
}))
