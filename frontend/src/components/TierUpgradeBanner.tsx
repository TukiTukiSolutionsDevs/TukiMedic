import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import type { TierGateInfo } from '@/lib/tier-gate'

interface TierUpgradeBannerProps {
  gate?: TierGateInfo | null
}

export function TierUpgradeBanner({ gate }: TierUpgradeBannerProps) {
  return (
    <Alert className="border-amber-500/40 bg-amber-50/50 dark:bg-amber-950/20">
      <AlertTitle>Funcionalidad de plan pagado</AlertTitle>
      <AlertDescription className="space-y-3">
        <span>
          Esta funcionalidad requiere el plan{' '}
          <strong>{gate?.requiredTier ?? 'paid'}</strong>. Tu plan actual es{' '}
          <strong>{gate?.currentTier ?? 'free'}</strong>.
        </span>
        <div>
          <Button size="sm" onClick={() => { window.location.href = '/pricing' }}>
            Ver planes
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  )
}
