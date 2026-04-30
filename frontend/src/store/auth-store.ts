import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface User {
  id: string
  email: string
  displayName: string | null
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  setAuth: (user: User, accessToken: string, refreshToken: string) => void
  setTokens: (accessToken: string, refreshToken: string) => void
  logout: () => void
}

const STORAGE_KEY = 'tuki-auth'

/**
 * Auth store with localStorage persistence.
 *
 * Trade-off: tokens in localStorage are readable by any JS running in the
 * page (XSS risk). The mitigation is a strict Content-Security-Policy
 * (configured in next.config.ts) plus never rendering user input as HTML
 * in the chat. For full defense in depth, a httpOnly refresh-token cookie
 * + short-lived access token in memory is the next step (Sprint 3+).
 *
 * The login page also sets a non-httpOnly companion cookie ('tuki-auth=1')
 * so proxy.ts can do server-side route guards without seeing the token.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      setAuth: (user, accessToken, refreshToken) =>
        set({ user, accessToken, refreshToken, isAuthenticated: true }),
      setTokens: (accessToken, refreshToken) =>
        set({ accessToken, refreshToken, isAuthenticated: true }),
      logout: () => {
        // Clear the companion cookie so proxy.ts redirects on next nav.
        if (typeof document !== 'undefined') {
          document.cookie = 'tuki-auth=; Path=/; Max-Age=0; SameSite=Strict'
        }
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        })
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      // Only persist what's necessary; never persist transient UI state.
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
)
