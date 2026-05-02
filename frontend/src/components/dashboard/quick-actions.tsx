import { Clock, Upload, User } from 'lucide-react'
import type { ComponentType } from 'react'

import { Card, CardContent } from '@/components/ui/card'

interface Action {
  label: string
  description: string
  href: string
  Icon: ComponentType<{ size?: number; className?: string }>
}

const ACTIONS: Action[] = [
  {
    label: 'Historial',
    description: 'Tus consultas anteriores',
    href: '/history',
    Icon: Clock,
  },
  {
    label: 'Documentos',
    description: 'Subir archivos clínicos',
    href: '/upload',
    Icon: Upload,
  },
  {
    label: 'Perfil',
    description: 'Tu cuenta y plan',
    href: '/settings',
    Icon: User,
  },
]

export function QuickActions() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {ACTIONS.map(({ label, description, href, Icon }) => (
        <a
          key={href}
          href={href}
          className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Card className="h-full cursor-pointer transition-shadow hover:ring-foreground/20">
            <CardContent className="flex items-center gap-3 pt-4">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--tm-blue-50)] text-[var(--tm-blue-700)]">
                <Icon size={18} />
              </div>
              <div>
                <p className="text-sm font-medium">{label}</p>
                <p className="text-xs text-muted-foreground">{description}</p>
              </div>
            </CardContent>
          </Card>
        </a>
      ))}
    </div>
  )
}
