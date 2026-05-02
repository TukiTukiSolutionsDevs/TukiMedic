import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorScreen } from "@/components/error-screen";

function makeError(message: string, digest?: string): Error & { digest?: string } {
  const e = new Error(message) as Error & { digest?: string };
  if (digest) e.digest = digest;
  return e;
}

describe("ErrorScreen", () => {
  it("renders default title and reset button", () => {
    render(<ErrorScreen error={makeError("boom")} reset={vi.fn()} />);
    expect(screen.getByTestId("error-screen")).toBeInTheDocument();
    expect(screen.getByText(/Algo salió mal/i)).toBeInTheDocument();
    expect(screen.getByTestId("error-reset")).toBeInTheDocument();
  });

  it("uses role=alert for screen readers", () => {
    render(<ErrorScreen error={makeError("boom")} reset={vi.fn()} />);
    const node = screen.getByTestId("error-screen");
    expect(node).toHaveAttribute("role", "alert");
    expect(node).toHaveAttribute("aria-live", "polite");
  });

  it("calls reset when Reintentar is clicked", () => {
    const reset = vi.fn();
    render(<ErrorScreen error={makeError("boom")} reset={reset} />);
    screen.getByTestId("error-reset").click();
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("shows the digest when provided", () => {
    render(
      <ErrorScreen
        error={makeError("boom", "abc-123")}
        reset={vi.fn()}
      />,
    );
    expect(screen.getByTestId("error-digest")).toHaveTextContent("abc-123");
  });

  it("hides the digest when not provided", () => {
    render(<ErrorScreen error={makeError("boom")} reset={vi.fn()} />);
    expect(screen.queryByTestId("error-digest")).not.toBeInTheDocument();
  });

  it("renders the home link by default", () => {
    render(<ErrorScreen error={makeError("boom")} reset={vi.fn()} />);
    const link = screen.getByTestId("error-home");
    expect(link).toHaveAttribute("href", "/dashboard");
  });

  it("hides the home link when showHomeLink=false", () => {
    render(
      <ErrorScreen
        error={makeError("boom")}
        reset={vi.fn()}
        showHomeLink={false}
      />,
    );
    expect(screen.queryByTestId("error-home")).not.toBeInTheDocument();
  });

  it("respects a custom title", () => {
    render(
      <ErrorScreen
        error={makeError("boom")}
        reset={vi.fn()}
        title="No pudimos cargar el chat"
      />,
    );
    expect(
      screen.getByText("No pudimos cargar el chat"),
    ).toBeInTheDocument();
  });
});
