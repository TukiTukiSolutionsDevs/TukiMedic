'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Shield, Key, Users, BookOpen } from 'lucide-react'

const LINKS = [
  { href: '/admin/audit',       label: 'Audit',          icon: Shield   },
  { href: '/admin/credentials', label: 'Credenciales',   icon: Key      },
  { href: '/admin/users',       label: 'Usuarios',       icon: Users    },
  { href: '/admin/kb',          label: 'Knowledge Base', icon: BookOpen },
] as const

export function AdminSubNav() {
  const pathname = usePathname()

  return (
    <nav
      data-testid="admin-sub-nav"
      className="flex border-b bg-card px-6"
    >
      {LINKS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`)
        return (
          <Link
            key={href}
            href={href}
            data-testid={`admin-nav-${href.split('/').at(-1)}`}
            data-active={String(active)}
            className={[
              'inline-flex items-center gap-2 border-b-2 px-4 py-3.5 text-sm transition-colors',
              active
                ? 'border-primary font-semibold text-foreground'
                : 'border-transparent font-normal text-muted-foreground hover:text-foreground',
            ].join(' ')}
          >
            <Icon size={15} />
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
