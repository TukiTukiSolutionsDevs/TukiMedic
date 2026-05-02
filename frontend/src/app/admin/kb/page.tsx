'use client'

import { KBStatus } from '@/components/admin/kb-status'

export default function KBAdminPage() {
  return (
    <div className="flex flex-1 flex-col gap-6 overflow-auto p-6">
      <div>
        <h1 className="text-xl font-semibold">Knowledge Base</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Fuentes de conocimiento medico indexado
        </p>
      </div>
      <KBStatus />
    </div>
  )
}
