import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToolTagGroup } from "./tool-tag-group";
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
    description: "Get users",
    input_schema: {},
    base_url_override: null,
    operation_id: null,
    method: "GET",
    path: "/users",
    original_operation_id: null,
    summary: null,
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

const userTools: ToolDefinition[] = [
  createTool({ name: "get-users" }),
  createTool({ name: "create-user", method: "POST" }),
];

describe("ToolTagGroup", () => {
  let onToggle: ReturnType<typeof vi.fn>;
  let onSelectAll: ReturnType<typeof vi.fn>;
  let onDeselectAll: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onToggle = vi.fn();
    onSelectAll = vi.fn();
    onDeselectAll = vi.fn();
  });

  it("renders tag name and tool count", () => {
    render(
      <ToolTagGroup
        tag="users"
        tools={userTools}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
      />,
    );
    expect(screen.getByText("users")).toBeInTheDocument();
    expect(screen.getByText("2 tools")).toBeInTheDocument();
  });

  it("returns null when tools array is empty", () => {
    const { container } = render(
      <ToolTagGroup
        tag="empty"
        tools={[]}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders tool rows", () => {
    render(
      <ToolTagGroup
        tag="users"
        tools={userTools}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
      />,
    );
    expect(screen.getByText("get-users")).toBeInTheDocument();
    expect(screen.getByText("create-user")).toBeInTheDocument();
  });

  it("shows select all button and calls onSelectAll", async () => {
    const user = userEvent.setup();
    render(
      <ToolTagGroup
        tag="users"
        tools={userTools}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
      />,
    );
    await user.click(screen.getByText("Select all"));
    expect(onSelectAll).toHaveBeenCalledWith(["get-users", "create-user"]);
  });

  it("shows deselect all when all selected", () => {
    render(
      <ToolTagGroup
        tag="users"
        tools={userTools}
        selected={new Set(["get-users", "create-user"])}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
      />,
    );
    expect(screen.getByText("Deselect all")).toBeInTheDocument();
    expect(screen.getByText("All selected")).toBeInTheDocument();
  });

  it("toggles aria-expanded when header is clicked", async () => {
    const user = userEvent.setup();
    render(
      <ToolTagGroup
        tag="users"
        tools={userTools}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
      />,
    );
    const headerButton = screen.getByRole("button", { name: /users/i });
    expect(headerButton).toHaveAttribute("aria-expanded", "true");

    await user.click(headerButton);
    expect(headerButton).toHaveAttribute("aria-expanded", "false");
  });
});
