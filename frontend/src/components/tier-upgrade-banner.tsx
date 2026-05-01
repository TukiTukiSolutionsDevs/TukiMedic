/**
 * <TierUpgradeBanner /> — surfaces a `tier_required` 403 from the backend
 * as a non-blocking upsell instead of a generic error screen.
 *
 * Render this whenever `parseTierGate(err)` returns non-null:
 *
 *   const gate = parseTierGate(err)
 *   if (gate) return <TierUpgradeBanner {...gate} onUpgrade={...} />
 *
 * The component is purely presentational — billing logic, navigation to
 * /upgrade, and analytics live with the caller.
 */
import { Button } from '@/components/ui/button'

export interface TierUpgradeBannerProps {
  /** Tier the feature requires (e.g. "paid"). Comes from the 403 body. */
  requiredTier: string
  /** Tier the user currently has (e.g. "free"). Comes from the 403 body. */
  currentTier: string
  /** Optional CTA — when omitted the upgrade button is hidden. */
  onUpgrade?: () => void
  /** Optional dismiss — when omitted the close button is hidden. */
  onDismiss?: () => void
}

export function TierUpgradeBanner({
  requiredTier,
  currentTier,
  onUpgrade,
  onDismiss,
}: TierUpgradeBannerProps) {
  return (
    <div
      role="alert"
      aria-live="polite"
      className="flex flex-col gap-3 rounded-lg border border-amber-300/60 bg-amber-50 p-4 text-sm text-amber-900 shadow-sm sm:flex-row sm:items-center sm:justify-between dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-100"
    >
      <div className="space-y-1">
        <p className="font-semibold">Esta función requiere el plan {requiredTier}.</p>
        <p className="text-amber-800 dark:text-amber-200/90">
          Tu plan actual es <span className="font-medium">{currentTier}</span>.
          Mejorá para acceder a especialistas, subir documentos clínicos y
          exportar tus casos.
        </p>
      </div>

      <div className="flex shrink-0 gap-2 self-start sm:self-center">
        {onUpgrade && (
          <Button type="button" size="sm" onClick={onUpgrade}>
            Mejorar plan
          </Button>
        )}
        {onDismiss && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onDismiss}
            aria-label="Cerrar"
          >
            Cerrar
          </Button>
        )}
      </div>
    </div>
  )
}
