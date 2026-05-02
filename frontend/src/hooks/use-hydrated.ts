"use client";

import { useEffect, useState } from "react";

/**
 * Returns `false` during SSR and the first client render, then `true` after
 * the first effect tick. Use this to gate any UI whose value depends on
 * persisted client state (zustand persist, localStorage, sessionStorage,
 * `Date.now()`, `Math.random()`, etc) to avoid React #418 hydration errors.
 *
 * Example:
 *   const hydrated = useHydrated();
 *   const user = useAuthStore((s) => s.user);
 *   if (!hydrated) return null; // or a skeleton
 *   return <UserCard user={user} />;
 */
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    setHydrated(true);
  }, []);
  return hydrated;
}
