import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToolRow } from "./tool-row";
import type { ToolDefinition } from "@/types/api";

vi.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  PopoverTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  PopoverContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
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

function createTool(
  overrides: Partial<ToolDefinition> = {},
): ToolDefinition {
  return {
    name: "get-users",
    description: "Get all users",
    input_schema: {},
    base_url_override: null,
    operation_id: null,
    method: "GET",
    path: "/users",
    original_operation_id: null,
    summary: "Fetch a list of users",
    tags: ["users"],
    parameters: [],
    request_body_schema: null,
    response_schemas: {},
    security_requirements: [],
    selected: false,
    warnings: [],
    ...overrides,
  };
}

describe("ToolRow", () => {
  let onToggle: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onToggle = vi.fn();
  });

  it("renders method, name, path, and summary", () => {
    const tool = createTool();
    render(<ToolRow tool={tool} selected={false} onToggle={onToggle} />);
    expect(screen.getByText("GET")).toBeInTheDocument();
    expect(screen.getByText("get-users")).toBeInTheDocument();
    expect(screen.getByText("/users")).toBeInTheDocument();
    expect(screen.getByText("Fetch a list of users")).toBeInTheDocument();
  });

  it("checkbox reflects selected state", () => {
    const { rerender } = render(
      <ToolRow tool={createTool()} selected={false} onToggle={onToggle} />,
    );
    expect(
      screen.getByRole("checkbox", { checked: false }),
    ).toBeInTheDocument();

    rerender(<ToolRow tool={createTool()} selected={true} onToggle={onToggle} />);
    expect(
      screen.getByRole("checkbox", { checked: true }),
    ).toBeInTheDocument();
  });

  it("calls onToggle when clicked", async () => {
    const user = userEvent.setup();
    render(
      <ToolRow tool={createTool()} selected={false} onToggle={onToggle} />,
    );
    await user.click(screen.getByRole("checkbox"));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("renders warnings icon when tool has warnings", () => {
    const tool = createTool({ warnings: ["missing_operation_id"] });
    render(<ToolRow tool={tool} selected={false} onToggle={onToggle} />);
    expect(screen.getByLabelText(/1 warning/i)).toBeInTheDocument();
  });

  it("does not render warnings when tool has no warnings", () => {
    const tool = createTool({ warnings: [] });
    render(<ToolRow tool={tool} selected={false} onToggle={onToggle} />);
    expect(screen.queryByLabelText(/warning/i)).not.toBeInTheDocument();
  });

  it("calls onToggle on Enter key press", async () => {
    const user = userEvent.setup();
    render(
      <ToolRow tool={createTool()} selected={false} onToggle={onToggle} />,
    );
    const row = screen.getByRole("checkbox");
    row.focus();
    await user.keyboard("{Enter}");
    expect(onToggle).toHaveBeenCalledOnce();
  });
});
