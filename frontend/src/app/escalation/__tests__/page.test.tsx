import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import EscalationPage from "@/app/escalation/page";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn() }),
  usePathname: () => "/escalation",
}));

beforeEach(() => {
  pushMock.mockReset();
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("EscalationPage rendering", () => {
  it("renders with role=alert and aria-live", () => {
    render(<EscalationPage />);
    const page = screen.getByTestId("escalation-page");
    expect(page).toHaveAttribute("role", "alert");
    expect(page).toHaveAttribute("aria-live", "assertive");
  });

  it("shows the RED triage badge", () => {
    render(<EscalationPage />);
    expect(screen.getByTestId("escalation-badge")).toHaveTextContent(
      /Triage RED/,
    );
  });

  it("links to SAMU 106", () => {
    render(<EscalationPage />);
    const callLink = screen.getByTestId("escalation-call");
    expect(callLink).toHaveAttribute("href", "tel:106");
  });

  it("opens the hospitals search in a new tab", () => {
    render(<EscalationPage />);
    const link = screen.getByTestId("escalation-hospitals");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("falls back to default red flags when no payload is present", () => {
    render(<EscalationPage />);
    const items = screen.getAllByTestId("escalation-redflag-item");
    expect(items.length).toBeGreaterThanOrEqual(3);
    expect(items[0]).toHaveTextContent(/Dolor torácico/i);
  });

  it("renders the red flags from sessionStorage payload when present", () => {
    window.sessionStorage.setItem(
      "tm-escalation",
      JSON.stringify({
        redFlags: ["Pérdida súbita de visión", "Cefalea explosiva"],
        at: "2026-05-01T22:00:00Z",
      }),
    );
    render(<EscalationPage />);
    const items = screen.getAllByTestId("escalation-redflag-item");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent(/Pérdida súbita de visión/);
    expect(items[1]).toHaveTextContent(/Cefalea explosiva/);
  });
});

describe("EscalationPage navigation", () => {
  it("Iniciar consulta nueva clears the payload and pushes /chat", () => {
    window.sessionStorage.setItem(
      "tm-escalation",
      JSON.stringify({ redFlags: ["x"] }),
    );
    render(<EscalationPage />);
    const button = screen.getByTestId("escalation-new-case");
    button.click();
    expect(window.sessionStorage.getItem("tm-escalation")).toBeNull();
    expect(pushMock).toHaveBeenCalledWith("/chat");
  });

  it("provides a Volver link to /dashboard", () => {
    render(<EscalationPage />);
    expect(screen.getByTestId("escalation-back")).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("provides a Volver al inicio link to /dashboard", () => {
    render(<EscalationPage />);
    expect(screen.getByTestId("escalation-go-dashboard")).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});
