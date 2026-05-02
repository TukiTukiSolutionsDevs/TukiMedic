"use client"

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth-store'
import { useHydrated } from '@/hooks/use-hydrated'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { LogOut } from 'lucide-react'

export function AccountTab() {
  const router = useRouter()
  const hydrated = useHydrated()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const [displayName, setDisplayName] = useState('')

  // Sync the local form state once auth-store has rehydrated from localStorage.
  useEffect(() => {
    if (hydrated && user?.displayName != null) {
      setDisplayName(user.displayName)
    }
  }, [hydrated, user?.displayName])
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  // After hydration the store has the persisted user; on the server-rendered
  // pass it is null. Reading user.* before hydration would diverge between
  // the two passes -> React #418.
  const isPaid = hydrated && user?.subscriptionTier === 'paid'
  const userEmail = hydrated ? (user?.email ?? '') : ''

  function handleSaveName() {
    // TODO: PATCH /api/v1/auth/me { display_name }
  }

  function handleSavePassword() {
    // TODO: PATCH /api/v1/auth/me { current_password, new_password }
  }

  function handleLogout() {
    logout()
    router.push('/')
  }

  return (
    <div className="max-w-xl flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Información de cuenta</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="displayName">Nombre</Label>
            <div className="flex gap-2">
              <Input
                id="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Tu nombre"
              />
              <Button onClick={handleSaveName} variant="secondary" size="sm">
                Guardar nombre
              </Button>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={userEmail}
              readOnly
            />
            <p className="text-xs text-muted-foreground">
              Para cambiarlo contactá soporte
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Plan</Label>
            <div className="flex items-center gap-3">
              <Badge
                variant={isPaid ? 'default' : 'secondary'}
                data-testid="tier-badge"
              >
                {isPaid ? 'Tuki Pro' : 'Plan Gratuito'}
              </Badge>
              {!isPaid && (
                <Button variant="link" size="sm" className="h-auto p-0">
                  Mejorar a Pro
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cambiar contraseña</CardTitle>
          <CardDescription>
            Te recomendamos cambiarla cada 6 meses.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="currentPassword">Contraseña actual</Label>
            <Input
              id="currentPassword"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="newPassword">Nueva contraseña</Label>
            <Input
              id="newPassword"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirmPassword">Confirmar contraseña</Label>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>
          <Button onClick={handleSavePassword} variant="secondary" className="self-start">
            Guardar contraseña
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <Button
            variant="ghost"
            onClick={handleLogout}
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
          >
            <LogOut size={16} aria-hidden="true" />
            Cerrar sesión
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
