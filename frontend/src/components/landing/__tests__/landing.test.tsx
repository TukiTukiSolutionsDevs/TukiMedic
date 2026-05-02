import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import React from "react";
import Home from "@/app/page";
import { ThemeProvider } from "@/components/theme/theme-provider";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

vi.mock("next/image", () => ({
  default: ({ src, alt }: { src: string; alt: string }) => (
    <img src={src} alt={alt} />
  ),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
    "aria-label": ariaLabel,
    ...props
  }: {
    href: string;
    children?: React.ReactNode;
    className?: string;
    "aria-label"?: string;
    [k: string]: unknown;
  }) => (
    <a href={href} className={className} aria-label={ariaLabel} {...props}>
      {children}
    </a>
  ),
}));

function renderPage() {
  return render(
    <ThemeProvider defaultTheme="light">
      <Home />
    </ThemeProvider>,
  );
}

// ─── Page level ────────────────────────────────────────────────────────────────

describe("Landing page — page level", () => {
  it("renders without crashing", () => {
    renderPage();
    expect(document.body).toBeInTheDocument();
  });

  it("has a hero h1 containing the brand promise", () => {
    renderPage();
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toBeInTheDocument();
    expect(h1.textContent?.toLowerCase()).toMatch(/salud/);
  });

  it("has at least one Crear cuenta CTA linking to /register", () => {
    renderPage();
    const links = screen
      .getAllByRole("link")
      .filter((el) => /crear.*cuenta/i.test(el.textContent ?? ""));
    expect(links.length).toBeGreaterThan(0);
    expect(links[0]).toHaveAttribute("href", "/register");
  });

  it("has an Ingresar link pointing to /login", () => {
    renderPage();
    const link = screen.getByRole("link", { name: /ingresar/i });
    expect(link).toHaveAttribute("href", "/login");
  });

  it("renders all 10 sections via data-testid", () => {
    renderPage();
    const testids = [
      "landing-nav",
      "landing-hero",
      "landing-trust",
      "landing-how",
      "landing-mesa",
      "landing-features",
      "landing-pricing",
      "landing-faq",
      "landing-cta",
      "landing-footer",
    ];
    for (const id of testids) {
      expect(screen.getByTestId(id), `Missing section: ${id}`).toBeInTheDocument();
    }
  });
});

// ─── LandingNav ────────────────────────────────────────────────────────────────

describe("Landing page — LandingNav", () => {
  it("has the 4 anchor nav links", () => {
    renderPage();
    const nav = screen.getByTestId("landing-nav");
    expect(within(nav).getByRole("link", { name: /cómo funciona/i })).toHaveAttribute(
      "href",
      "#como-funciona",
    );
    expect(within(nav).getByRole("link", { name: /mesa médica/i })).toHaveAttribute(
      "href",
      "#mesa-medica",
    );
    expect(
      within(nav)
        .getAllByRole("link")
        .find((l) => l.textContent?.trim() === "Planes"),
    ).toHaveAttribute("href", "#planes");
    expect(within(nav).getByRole("link", { name: /preguntas/i })).toHaveAttribute(
      "href",
      "#faq",
    );
  });
});

// ─── LandingPricing ────────────────────────────────────────────────────────────

describe("Landing page — LandingPricing", () => {
  it("shows the free tier (S/ 0)", () => {
    renderPage();
    expect(screen.getByText(/S\/ 0/)).toBeInTheDocument();
  });

  it("shows the Pro paid tier (S/ 29)", () => {
    renderPage();
    expect(screen.getByText(/S\/ 29/)).toBeInTheDocument();
  });

  it("shows the Familia paid tier (S/ 59)", () => {
    renderPage();
    expect(screen.getByText(/S\/ 59/)).toBeInTheDocument();
  });
});

// ─── LandingFAQ ────────────────────────────────────────────────────────────────

describe("Landing page — LandingFAQ", () => {
  it("has at least 4 question buttons", () => {
    renderPage();
    const questionButtons = screen
      .getAllByRole("button")
      .filter((btn) => btn.textContent?.trim().startsWith("¿"));
    expect(questionButtons.length).toBeGreaterThanOrEqual(4);
  });

  it("FAQ answers are collapsed by default", () => {
    renderPage();
    expect(screen.queryByText(/orienta, no diagnostica/i)).not.toBeInTheDocument();
  });

  it("clicking a question reveals its answer", () => {
    renderPage();
    const questionSpan = screen.getByText(/¿TukiMedic reemplaza al médico\?/i);
    fireEvent.click(questionSpan);
    expect(screen.getByText(/orienta, no diagnostica/i)).toBeInTheDocument();
  });

  it("clicking an open question collapses it again", () => {
    renderPage();
    const questionSpan = screen.getByText(/¿TukiMedic reemplaza al médico\?/i);
    fireEvent.click(questionSpan);
    expect(screen.getByText(/orienta, no diagnostica/i)).toBeInTheDocument();
    fireEvent.click(questionSpan);
    expect(screen.queryByText(/orienta, no diagnostica/i)).not.toBeInTheDocument();
  });
});

// ─── LandingFooter ─────────────────────────────────────────────────────────────

describe("Landing page — LandingFooter", () => {
  it("has the SAMU emergency number", () => {
    renderPage();
    expect(screen.getByText(/SAMU 106/i)).toBeInTheDocument();
  });

  it("has the no-diagnosis disclaimer", () => {
    renderPage();
    expect(screen.getByText(/no diagnostica ni receta/i)).toBeInTheDocument();
  });
});
