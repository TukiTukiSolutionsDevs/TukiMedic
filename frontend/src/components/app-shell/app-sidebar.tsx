"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Home,
  MessageSquare,
  History,
  User,
  Shield,
  Upload,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { useAuthStore } from "@/store/auth-store";
import { NAV_ITEMS, type NavItem } from "@/components/app-shell/nav-config";
import { cn } from "@/lib/utils";

const ICON_MAP = {
  Home,
  MessageSquare,
  History,
  User,
  Shield,
  Upload,
  Settings,
} as const;

interface NavLinkProps {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}

function NavLink({ item, active, collapsed }: NavLinkProps) {
  const IconComponent = ICON_MAP[item.icon];
  return (
    <Link
      href={item.href}
      data-testid={`nav-${item.id}`}
      data-active={active}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-[var(--tm-blue-50)] text-[var(--tm-blue-700)] font-medium"
          : "text-foreground hover:bg-[var(--tm-bg-soft)]",
        collapsed && "justify-center px-2",
      )}
    >
      <IconComponent
        size={18}
        strokeWidth={active ? 2 : 1.75}
        aria-hidden
      />
      {!collapsed && <span>{item.label}</span>}
    </Link>
  );
}

interface UserCardProps {
  collapsed: boolean;
  onLogout: () => void;
}

function UserCard({ collapsed, onLogout }: UserCardProps) {
  const user = useAuthStore((s) => s.user);
  if (!user) return null;
  const display = user.displayName || user.email.split("@")[0];
  const initial = display.slice(0, 1).toUpperCase();
  const isPaid = user.subscriptionTier === "paid";

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2 px-2 py-2">
        <div
          aria-label={`Cuenta de ${display}`}
          className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold text-white"
          style={{
            background:
              "linear-gradient(135deg, var(--tm-blue-500), var(--tm-blue-700))",
          }}
        >
          {initial}
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="user-card"
      className="flex items-center gap-3 rounded-md px-2 py-2"
    >
      <div
        aria-hidden
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
        style={{
          background:
            "linear-gradient(135deg, var(--tm-blue-500), var(--tm-blue-700))",
        }}
      >
        {initial}
      </div>
      <div className="min-w-0 flex-1">
        <div
          data-testid="user-display-name"
          className="truncate text-sm font-medium"
        >
          {display}
        </div>
        <div className="text-xs text-[var(--tm-text-subtle)]">
          {isPaid ? "✦ Tuki Pro" : "Plan gratuito"}
        </div>
      </div>
      <button
        type="button"
        onClick={onLogout}
        title="Cerrar sesión"
        aria-label="Cerrar sesión"
        data-testid="logout-button"
        className="text-[var(--tm-text-subtle)] hover:text-foreground"
      >
        <LogOut size={16} aria-hidden />
      </button>
    </div>
  );
}

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  // Zustand persist rehydrates AFTER first client render. Without this gate,
  // SSR renders without the user (admin item hidden, UserCard absent) but
  // the client render after hydration shows them, triggering React #418.
  useEffect(() => {
    setMounted(true);
  }, []);

  const visibleItems = NAV_ITEMS.filter(
    (item) =>
      !item.requiresRole || (mounted && user?.role === item.requiresRole),
  );

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <aside
      data-testid="app-sidebar"
      data-collapsed={collapsed}
      className="sticky top-0 flex h-screen flex-col border-r bg-[var(--tm-surface)]"
      style={{
        width: collapsed ? 72 : 248,
        transition: "width 0.2s",
        flexShrink: 0,
      }}
    >
      <div
        className={cn(
          "flex items-center px-4 py-5",
          collapsed ? "justify-center" : "justify-between",
        )}
      >
        <Logo size={32} showText={!collapsed} asLink />
      </div>

      <nav className="flex-1 px-2">
        {visibleItems.map((item) => (
          <div key={item.id}>
            {item.separator && (
              <div
                aria-hidden
                className="my-3 mx-2 h-px bg-[var(--tm-border)]"
              />
            )}
            <NavLink
              item={item}
              active={
                pathname === item.href ||
                (item.id === "admin" && pathname.startsWith("/admin"))
              }
              collapsed={collapsed}
            />
          </div>
        ))}
      </nav>

      <div className="border-t p-3">
        {mounted && (
          <UserCard collapsed={collapsed} onLogout={handleLogout} />
        )}
        <div
          className={cn(
            "mt-2 flex gap-1.5",
            collapsed ? "flex-col items-center" : "justify-end",
          )}
        >
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? "Expandir" : "Colapsar"}
            aria-label={collapsed ? "Expandir sidebar" : "Colapsar sidebar"}
            data-testid="toggle-collapse"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--tm-border)] text-[var(--tm-text-muted)] hover:bg-[var(--tm-bg-soft)]"
          >
            {collapsed ? (
              <ChevronRight size={14} aria-hidden />
            ) : (
              <ChevronLeft size={14} aria-hidden />
            )}
          </button>
        </div>
      </div>
    </aside>
  );
}
