import { describe, expect, it } from "vitest";
import {
  NAV_ITEMS,
  PUBLIC_ROUTES,
  isPublicRoute,
} from "@/components/app-shell/nav-config";

describe("nav-config", () => {
  it("includes the core authenticated routes", () => {
    const ids = NAV_ITEMS.map((i) => i.id);
    expect(ids).toContain("dashboard");
    expect(ids).toContain("chat");
    expect(ids).toContain("history");
    expect(ids).toContain("settings");
  });

  it("gates the admin item with role=admin", () => {
    const admin = NAV_ITEMS.find((i) => i.id === "admin");
    expect(admin).toBeDefined();
    expect(admin!.requiresRole).toBe("admin");
  });

  it("places admin behind a separator", () => {
    const admin = NAV_ITEMS.find((i) => i.id === "admin");
    expect(admin!.separator).toBe(true);
  });

  it("treats /, /login, /register as public", () => {
    expect(PUBLIC_ROUTES.has("/")).toBe(true);
    expect(isPublicRoute("/login")).toBe(true);
    expect(isPublicRoute("/register")).toBe(true);
  });

  it("does NOT treat app routes as public", () => {
    expect(isPublicRoute("/dashboard")).toBe(false);
    expect(isPublicRoute("/chat")).toBe(false);
    expect(isPublicRoute("/admin/users")).toBe(false);
  });

  it("every nav item has an href starting with /", () => {
    for (const item of NAV_ITEMS) {
      expect(item.href.startsWith("/")).toBe(true);
    }
  });
});
