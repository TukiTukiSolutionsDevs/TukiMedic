'use client'

import { CredentialTable } from '@/components/admin/credential-table'

export default function AdminCredentialsPage() {
  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto p-6">
      <div>
        <h1 className="text-xl font-semibold">Credenciales LLM</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Gestion de API keys por proveedor
        </p>
      </div>
      <CredentialTable />
    </div>
  )
}
