'use client'

import { useHydrated } from '@/hooks/use-hydrated'

interface GreetingProps {
  displayName: string | null
  email: string
}

function timeGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Buen día'
  if (h < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

export function Greeting({ displayName, email }: GreetingProps) {
  const hydrated = useHydrated()
  const name = displayName?.split(' ')[0] ?? email.split('@')[0]
  // Default the greeting to a stable string on SSR + first paint, then upgrade
  // to time-based on hydration. Avoids React #418 across the noon / 7pm boundaries.
  const salutation = hydrated ? timeGreeting() : 'Hola'

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">
        {salutation}, {name}
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">
        ¿En qué te podemos orientar hoy?
      </p>
    </div>
  )
}
