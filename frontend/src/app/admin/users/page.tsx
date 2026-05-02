'use client'

import { UserTable } from '@/components/admin/user-table'

export default function AdminUsersPage() {
  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto p-6">
      <div>
        <h1 className="text-xl font-semibold">Usuarios</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Gestion de usuarios y roles
        </p>
      </div>
      <UserTable />
    </div>
  )
}
