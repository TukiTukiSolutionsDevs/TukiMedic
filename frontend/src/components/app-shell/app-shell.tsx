"use client";

import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/app-shell/app-sidebar";
import { isPublicRoute } from "@/components/app-shell/nav-config";

interface AppShellProps {
  children: React.ReactNode;
}

/**
 * Top-level chrome decision: public routes (landing, login, register) render
 * the children full-bleed. Authenticated routes render with the sidebar.
 *
 * This sits inside the ThemeProvider, so both branches inherit theme tokens.
 */
export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();

  if (isPublicRoute(pathname)) {
    return (
      <main
        data-testid="public-shell"
        className="min-h-screen bg-[var(--tm-bg)]"
      >
        {children}
      </main>
    );
  }

  return (
    <div
      data-testid="app-shell"
      className="flex min-h-screen bg-[var(--tm-bg)]"
    >
      <AppSidebar />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
