import { describe, it, expect } from "vitest";
import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { SeverityBadge } from "./severity-badge";
import type { FindingSeverity } from "@/types/api";

const SEVERITIES: FindingSeverity[] = ["critical", "high", "medium", "info"];

describe("SeverityBadge", () => {
  it.each(SEVERITIES)("renders severity text for %s", (severity) => {
    render(<SeverityBadge severity={severity} />);
    expect(screen.getByText(severity)).toBeInTheDocument();
  });

  it("renders an aria-hidden colored dot", () => {
    const { container } = render(<SeverityBadge severity="critical" />);
    const dot = container.querySelector("span[aria-hidden='true']");
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveClass("rounded-full");
  });

  it("applies a custom className", () => {
    render(
      <SeverityBadge severity="high" className="my-custom-class" />,
    );
    expect(screen.getByText("high")).toHaveClass("my-custom-class");
  });

  it("forwards the ref to the underlying span", () => {
    const ref = createRef<HTMLSpanElement>();
    render(<SeverityBadge severity="info" ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLSpanElement);
  });

  it("applies red dot classes for critical severity", () => {
    const { container } = render(<SeverityBadge severity="critical" />);
    const dot = container.querySelector("span[aria-hidden='true']");
    expect(dot).toHaveClass("bg-red-500");
  });

  it("applies orange dot classes for high severity", () => {
    const { container } = render(<SeverityBadge severity="high" />);
    const dot = container.querySelector("span[aria-hidden='true']");
    expect(dot).toHaveClass("bg-orange-500");
  });

  it("applies amber dot classes for medium severity", () => {
    const { container } = render(<SeverityBadge severity="medium" />);
    const dot = container.querySelector("span[aria-hidden='true']");
    expect(dot).toHaveClass("bg-amber-500");
  });

  it("applies blue dot classes for info severity", () => {
    const { container } = render(<SeverityBadge severity="info" />);
    const dot = container.querySelector("span[aria-hidden='true']");
    expect(dot).toHaveClass("bg-blue-500");
  });
});
