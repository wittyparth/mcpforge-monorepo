import { describe, it, expect } from "vitest";
import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { HttpMethodBadge } from "./http-method-badge";
import type { HttpMethod } from "@/types/api";

const METHODS: HttpMethod[] = [
  "GET",
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
  "HEAD",
  "OPTIONS",
];

describe("HttpMethodBadge", () => {
  it.each(METHODS)("renders method text for %s", (method) => {
    render(<HttpMethodBadge method={method} />);
    expect(screen.getByText(method)).toBeInTheDocument();
  });

  it("renders an aria-hidden colored dot", () => {
    const { container } = render(<HttpMethodBadge method="GET" />);
    const dot = container.querySelector("span[aria-hidden='true']");
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveClass("rounded-full");
  });

  it("applies a custom className", () => {
    render(<HttpMethodBadge method="POST" className="my-custom-class" />);
    expect(screen.getByText("POST")).toHaveClass("my-custom-class");
  });

  it("forwards the ref to the underlying span", () => {
    const ref = createRef<HTMLSpanElement>();
    render(<HttpMethodBadge method="GET" ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLSpanElement);
  });
});
