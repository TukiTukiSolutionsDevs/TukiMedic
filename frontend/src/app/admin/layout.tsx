'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth-store'

/**
 * Guard layout for all /admin routes.
 *
 * Auth state lives in localStorage (zustand persist). We defer the check
 * to after the first client-side render (setReady) to avoid acting on the
 * server-side initial state (isAuthenticated=false before rehydration).
 *
 * - Unauthenticated → /login
 * - Authenticated but role != 'admin' → /chat
 * - Admin → render children
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { isAuthenticated, user } = useAuthStore()
  const [ready, setReady] = useState(false)

  // Signal that zustand has rehydrated from localStorage.
  useEffect(() => {
    setReady(true)
  }, [])

  useEffect(() => {
    if (!ready) return
    if (!isAuthenticated) {
      router.replace('/login')
    } else if (user?.role !== 'admin') {
      router.replace('/chat')
    }
  }, [ready, isAuthenticated, user, router])

  if (!ready || !isAuthenticated || user?.role !== 'admin') {
    return null
  }

  return <>{children}</>
}
