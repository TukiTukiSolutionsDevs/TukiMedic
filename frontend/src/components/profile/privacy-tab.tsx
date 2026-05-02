"use client"

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { DeleteAccountDialog } from '@/components/profile/delete-account-dialog'
import { Download, Shield, Trash2 } from 'lucide-react'

export function PrivacyTab() {
  const [deleteOpen, setDeleteOpen] = useState(false)

  return (
    <div className="max-w-xl flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-muted-foreground" aria-hidden="true" />
            <CardTitle>¿Qué guardamos?</CardTitle>
          </div>
          <CardDescription>
            Guardamos tu historial de consultas, mensajes con los agentes y la
            información de tu ficha clínica (alergias, medicación, condiciones
            crónicas). Todo está cifrado en reposo y en tránsito. Nunca compartimos
            datos identificables con terceros.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Exportar mis datos</CardTitle>
          <CardDescription>
            Descargá una copia completa de tus datos en formato JSON (GDPR Art. 20).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" disabled>
            <Download size={16} aria-hidden="true" />
            Descargar mis datos
          </Button>
          <p className="text-xs text-muted-foreground mt-2">
            Función disponible próximamente.
          </p>
        </CardContent>
      </Card>

      <Card className="border-destructive/25">
        <CardHeader>
          <CardTitle className="text-destructive">Eliminar mi cuenta</CardTitle>
          <CardDescription>
            Eliminá tu cuenta y todos tus datos de forma permanente. Esta acción no
            se puede deshacer.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
            <Trash2 size={16} aria-hidden="true" />
            Eliminar mi cuenta
          </Button>
        </CardContent>
      </Card>

      <DeleteAccountDialog open={deleteOpen} onOpenChange={setDeleteOpen} />
    </div>
  )
}
