import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoadingSpinner, spinnerSizeMap } from "./loading-spinner";

describe("LoadingSpinner", () => {
  it("renders with role status", () => {
    render(<LoadingSpinner />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders an accessible label", () => {
    render(<LoadingSpinner />);
    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
  });

  it("renders label text when provided", () => {
    render(<LoadingSpinner label="Loading servers…" />);
    expect(screen.getByText("Loading servers…")).toBeInTheDocument();
  });

  it("does not render a label element when no label prop is given", () => {
    // When no label is provided, only the Loader2 SVG renders as content
    const { container } = render(<LoadingSpinner />);
    // The <span> child only exists when label is truthy
    const spans = container.querySelectorAll("span");
    expect(spans.length).toBe(0);
  });

  it("applies size classes from spinnerSizeMap", () => {
    const { container, rerender } = render(<LoadingSpinner size="sm" />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveClass(...spinnerSizeMap.sm.split(" "));

    rerender(<LoadingSpinner size="lg" />);
    expect(svg).toHaveClass(...spinnerSizeMap.lg.split(" "));
  });
});
