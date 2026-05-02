import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LoadingScreen } from "@/components/loading-screen";

describe("LoadingScreen", () => {
  it("renders with role=status for assistive tech", () => {
    render(<LoadingScreen />);
    const node = screen.getByTestId("loading-screen");
    expect(node).toHaveAttribute("role", "status");
    expect(node).toHaveAttribute("aria-live", "polite");
  });

  it("uses the default aria-label", () => {
    render(<LoadingScreen />);
    expect(screen.getByTestId("loading-screen")).toHaveAttribute(
      "aria-label",
      "Cargando contenido",
    );
  });

  it("respects a custom label", () => {
    render(<LoadingScreen label="Cargando casos" />);
    expect(screen.getByTestId("loading-screen")).toHaveAttribute(
      "aria-label",
      "Cargando casos",
    );
    // sr-only span also reflects the label
    expect(screen.getByText("Cargando casos")).toBeInTheDocument();
  });

  it("renders skeleton placeholders", () => {
    render(<LoadingScreen />);
    expect(screen.getByTestId("loading-skeleton")).toBeInTheDocument();
  });
});
