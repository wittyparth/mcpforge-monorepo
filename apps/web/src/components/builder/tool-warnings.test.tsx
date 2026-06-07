import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ToolWarnings } from "./tool-warnings";

vi.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  PopoverTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  PopoverContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="popover-content">{children}</div>
  ),
}));

vi.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

describe("ToolWarnings", () => {
  it("renders warning list items", () => {
    const warnings = ["missing_operation_id", "no_description"];
    render(<ToolWarnings warnings={warnings} />);
    expect(
      screen.getByText(
        "Tool name was auto-generated from path (no operationId provided)",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Missing description. LLM selection will be less accurate/),
    ).toBeInTheDocument();
  });

  it("returns null when warnings array is empty", () => {
    const { container } = render(<ToolWarnings warnings={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders warning count badge for multiple warnings", () => {
    const warnings = ["missing_operation_id", "no_description", "untagged"];
    render(<ToolWarnings warnings={warnings} />);
    expect(screen.getByLabelText("3 warnings")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders warning icon for single warning without count badge", () => {
    render(<ToolWarnings warnings={["missing_operation_id"]} />);
    expect(screen.getByLabelText("1 warning")).toBeInTheDocument();
    // Single warning: no numeric badge rendered
    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });

  it("renders unknown warning codes as-is", () => {
    render(<ToolWarnings warnings={["custom_warning_code"]} />);
    expect(screen.getByText("custom_warning_code")).toBeInTheDocument();
  });
});
