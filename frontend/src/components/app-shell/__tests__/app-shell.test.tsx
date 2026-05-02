import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/app-shell/app-shell";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { useAuthStore } from "@/store/auth-store";

const pushMock = vi.fn();
let mockPathname = "/dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn() }),
}));

function renderShell(children: React.ReactNode = <div />) {
  return render(
    <ThemeProvider defaultTheme="light">
      <AppShell>{children}</AppShell>
    </ThemeProvider>,
  );
}

function seedUser(
  overrides: Partial<{
    id: string;
    email: string;
    displayName: string | null;
    role: string;
    subscriptionTier: string;
  }> = {},
) {
  useAuthStore.setState({
    user: {
      id: "user-1",
      email: "test@tuki.dev",
      displayName: null,
      role: "customer",
      subscriptionTier: "free",
      ...overrides,
    },
    accessToken: "tok",
    refreshToken: "ref",
    isAuthenticated: true,
  });
}

beforeEach(() => {
  pushMock.mockReset();
  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
  });
});

afterEach(() => {
  mockPathname = "/dashboard";
});

describe("AppShell layout decision", () => {
  it("renders public-shell on landing", () => {
    mockPathname = "/";
    renderShell(<div data-testid="content">child</div>);
    expect(screen.getByTestId("public-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("app-shell")).not.toBeInTheDocument();
    expect(screen.queryByTestId("app-sidebar")).not.toBeInTheDocument();
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  it("renders public-shell on /login", () => {
    mockPathname = "/login";
    renderShell();
    expect(screen.getByTestId("public-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("app-sidebar")).not.toBeInTheDocument();
  });

  it("renders public-shell on /register", () => {
    mockPathname = "/register";
    renderShell();
    expect(screen.queryByTestId("app-sidebar")).not.toBeInTheDocument();
  });

  it("renders app-shell with sidebar on /dashboard", () => {
    mockPathname = "/dashboard";
    seedUser();
    renderShell();
    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(screen.getByTestId("app-sidebar")).toBeInTheDocument();
  });
});

describe("AppSidebar nav items", () => {
  beforeEach(() => {
    mockPathname = "/dashboard";
  });

  it("shows core nav items for any authenticated user", () => {
    seedUser();
    renderShell();
    expect(screen.getByTestId("nav-dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("nav-chat")).toBeInTheDocument();
    expect(screen.getByTestId("nav-history")).toBeInTheDocument();
    expect(screen.getByTestId("nav-settings")).toBeInTheDocument();
  });

  it("hides admin item for non-admin role", () => {
    seedUser({ role: "customer" });
    renderShell();
    expect(screen.queryByTestId("nav-admin")).not.toBeInTheDocument();
  });

  it("shows admin item for admin role", () => {
    seedUser({ role: "admin" });
    renderShell();
    expect(screen.getByTestId("nav-admin")).toBeInTheDocument();
  });

  it("marks the active route with data-active=true", () => {
    mockPathname = "/chat";
    seedUser();
    renderShell();
    expect(screen.getByTestId("nav-chat")).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(screen.getByTestId("nav-dashboard")).toHaveAttribute(
      "data-active",
      "false",
    );
  });

  it("treats /admin/users as admin nav being active", () => {
    mockPathname = "/admin/users";
    seedUser({ role: "admin" });
    renderShell();
    expect(screen.getByTestId("nav-admin")).toHaveAttribute(
      "data-active",
      "true",
    );
  });
});

describe("AppSidebar user card", () => {
  beforeEach(() => {
    mockPathname = "/dashboard";
  });

  it("uses displayName when present", () => {
    seedUser({ displayName: "Andre" });
    renderShell();
    expect(screen.getByTestId("user-display-name")).toHaveTextContent(
      "Andre",
    );
  });

  it("falls back to email local-part when displayName missing", () => {
    seedUser({ displayName: null, email: "carlos@tuki.dev" });
    renderShell();
    expect(screen.getByTestId("user-display-name")).toHaveTextContent(
      "carlos",
    );
  });

  it("logout clears auth and navigates to /", () => {
    seedUser();
    renderShell();
    const button = screen.getByTestId("logout-button");
    button.click();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("shows Tuki Pro badge for paid tier", () => {
    seedUser({ subscriptionTier: "paid" });
    renderShell();
    expect(screen.getByText(/Tuki Pro/)).toBeInTheDocument();
  });
});
