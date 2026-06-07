import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SpecValidationErrors } from "./spec-validation-errors";
import type { SpecValidationError } from "@/types/api";

describe("SpecValidationErrors", () => {
  it("returns null when error is null", () => {
    const { container } = render(
      <SpecValidationErrors error={null} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the top-level error message", () => {
    render(
      <SpecValidationErrors error="Failed to parse: invalid YAML" />,
    );
    expect(
      screen.getByText("Couldn't parse this spec"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Failed to parse: invalid YAML"),
    ).toBeInTheDocument();
  });

  it("renders validation detail items with path and message", () => {
    const details: SpecValidationError[] = [
      { path: "$.info.title", message: "is required" },
      { path: "$.info.version", message: "must be a valid semver string" },
    ];

    render(
      <SpecValidationErrors
        error="Validation failed"
        details={details}
      />,
    );

    expect(screen.getByText(/is required/)).toBeInTheDocument();
    expect(screen.getByText(/must be a valid semver string/)).toBeInTheDocument();
    expect(screen.getByText("$.info.title")).toBeInTheDocument();
    expect(screen.getByText("$.info.version")).toBeInTheDocument();
  });

  it("renders line and column info when provided", () => {
    const details: SpecValidationError[] = [
      { path: "$", message: "syntax error", line: 5, column: 10 },
    ];

    render(
      <SpecValidationErrors error="Parse error" details={details} />,
    );

    expect(screen.getByText(/line 5/i)).toBeInTheDocument();
    expect(screen.getByText(/column 10/i)).toBeInTheDocument();
  });

  it("collapses to 5 items and shows a toggle when there are more", async () => {
    const details: SpecValidationError[] = Array.from(
      { length: 7 },
      (_, i) => ({
        path: `$.paths[${i}]`,
        message: `Error ${i + 1}`,
      }),
    );

    const user = userEvent.setup();
    render(
      <SpecValidationErrors
        error="Multiple errors found"
        details={details}
      />,
    );

    // Only first 5 should be visible
    const listItems = screen.getAllByRole("listitem");
    expect(listItems).toHaveLength(5);
    expect(listItems[0]).toHaveTextContent("Error 1");
    expect(listItems[4]).toHaveTextContent("Error 5");

    expect(screen.queryByText("Error 6")).not.toBeInTheDocument();
    expect(screen.queryByText("Error 7")).not.toBeInTheDocument();

    const toggle = screen.getByRole("button", {
      name: /show all 7 errors/i,
    });
    expect(toggle).toBeInTheDocument();

    // Click to expand
    await user.click(toggle);

    const allItems = screen.getAllByRole("listitem");
    expect(allItems).toHaveLength(7);
    expect(allItems[5]).toHaveTextContent("Error 6");
    expect(allItems[6]).toHaveTextContent("Error 7");

    expect(
      screen.getByRole("button", { name: /show less/i }),
    ).toBeInTheDocument();
  });
});
