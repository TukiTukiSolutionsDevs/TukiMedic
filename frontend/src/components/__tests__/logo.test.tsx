import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Logo } from "@/components/logo";

describe("Logo", () => {
  it("renders the bitmap image with alt text", () => {
    render(<Logo />);
    const img = screen.getByAltText("TukiMedic");
    expect(img).toBeInTheDocument();
    expect(img.tagName).toBe("IMG");
  });

  it("shows the wordmark by default", () => {
    render(<Logo />);
    expect(screen.getByText("TukiMedic")).toBeInTheDocument();
  });

  it("hides the wordmark when showText=false", () => {
    render(<Logo showText={false} />);
    expect(screen.queryByText("TukiMedic")).not.toBeInTheDocument();
  });

  it("wraps in a link when asLink=true", () => {
    render(<Logo asLink />);
    const link = screen.getByRole("link", { name: "TukiMedic" });
    expect(link).toHaveAttribute("href", "/");
  });

  it("does not wrap in a link by default", () => {
    render(<Logo />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("respects custom text override", () => {
    render(<Logo text="TukiMedic Beta" />);
    expect(screen.getByText("TukiMedic Beta")).toBeInTheDocument();
  });
});
