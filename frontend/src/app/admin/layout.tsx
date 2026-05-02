'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth-store'
import { AdminSubNav } from '@/components/admin/sub-nav'

/**
 * Guard layout for all /admin routes.
 *
 * Auth state lives in localStorage (zustand persist). We defer the check
 * to after the first client-side render (setReady) to avoid acting on the
 * server-side initial state (isAuthenticated=false before rehydration).
 *
 * - Unauthenticated → /login
 * - Authenticated but role != 'admin' → /chat
 * - Admin → render sub-nav + children
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { isAuthenticated, user } = useAuthStore()
  const [ready, setReady] = useState(false)

  useEffect(() => { setReady(true) }, [])

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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <AdminSubNav />
      {children}
    </div>
  )
}
