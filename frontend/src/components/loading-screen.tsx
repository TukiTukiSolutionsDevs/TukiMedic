import { Skeleton } from "@/components/ui/skeleton";

interface LoadingScreenProps {
  /** Compact variant for narrow side-panels */
  compact?: boolean;
  /** Optional accessible label override */
  label?: string;
}

/**
 * Generic loading skeleton used by Next.js `loading.tsx` boundaries.
 *
 * Renders a shimmering header + 3 row placeholders that match the
 * post-login content area. Honors `prefers-reduced-motion` because the
 * shadcn Skeleton uses CSS animation.
 */
export function LoadingScreen({
  compact = false,
  label = "Cargando contenido",
}: LoadingScreenProps) {
  return (
    <div
      data-testid="loading-screen"
      role="status"
      aria-live="polite"
      aria-label={label}
      className={
        compact
          ? "flex flex-col gap-3 p-4"
          : "flex flex-1 flex-col gap-4 p-6 md:p-8"
      }
    >
      <Skeleton
        className={compact ? "h-5 w-1/3" : "h-7 w-1/3"}
        data-testid="loading-skeleton"
      />
      <Skeleton className="h-4 w-2/3" />
      <div className="flex flex-col gap-3 pt-2">
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}
