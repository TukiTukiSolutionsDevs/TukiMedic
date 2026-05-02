/**
 * Navigation configuration for the authenticated app shell.
 *
 * Order matters — this is the order shown in the sidebar.
 * `requiresRole` gates the item; the renderer must filter on user.role.
 * `separator: true` adds a visual divider above the item.
 */

export interface NavItem {
  id: string;
  label: string;
  /** Lucide icon name. Imported by the renderer. */
  icon:
    | "Home"
    | "MessageSquare"
    | "History"
    | "User"
    | "Shield"
    | "Settings"
    | "Upload";
  href: string;
  requiresRole?: "admin";
  separator?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { id: "dashboard", label: "Inicio", icon: "Home", href: "/dashboard" },
  { id: "chat", label: "Nueva consulta", icon: "MessageSquare", href: "/chat" },
  { id: "history", label: "Mis casos", icon: "History", href: "/history" },
  { id: "upload", label: "Documentos", icon: "Upload", href: "/upload" },
  { id: "settings", label: "Mi perfil", icon: "User", href: "/settings" },
  {
    id: "admin",
    label: "Admin",
    icon: "Shield",
    href: "/admin/users",
    requiresRole: "admin",
    separator: true,
  },
];

/**
 * Routes that render WITHOUT the sidebar shell.
 * Includes both public (landing + auth) and full-bleed authenticated screens
 * like /escalation that need the entire viewport.
 */
export const PUBLIC_ROUTES = new Set<string>(["/", "/login", "/register"]);
export const FULL_BLEED_ROUTES = new Set<string>(["/escalation"]);

export function isPublicRoute(pathname: string): boolean {
  if (PUBLIC_ROUTES.has(pathname)) return true;
  if (FULL_BLEED_ROUTES.has(pathname)) return true;
  // future: /verify-email, /reset-password, etc.
  return false;
}
