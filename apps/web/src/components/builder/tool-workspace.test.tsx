import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToolWorkspace } from "./tool-workspace";
import type { ToolDefinition } from "@/types/api";

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div>{children}</div> : null,
  DialogTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogContent: ({ children }: { children: React.ReactNode }) => (
    <div role="dialog">{children}</div>
  ),
  DialogHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogDescription: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogFooter: ({ children }: { children: React.ReactNode }) => (
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
    summary: "Fetch users",
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

const defaultTools: ToolDefinition[] = [
  createTool(),
  createTool({
    name: "create-user",
    method: "POST",
    path: "/users",
    summary: "Create user",
    tags: ["users"],
  }),
  createTool({
    name: "get-posts",
    method: "GET",
    path: "/posts",
    summary: "Fetch posts",
    tags: ["posts"],
  }),
];

describe("ToolWorkspace", () => {
  let onToggle: ReturnType<typeof vi.fn>;
  let onSelectAll: ReturnType<typeof vi.fn>;
  let onDeselectAll: ReturnType<typeof vi.fn>;
  let onConfirm: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onToggle = vi.fn();
    onSelectAll = vi.fn();
    onDeselectAll = vi.fn();
    onConfirm = vi.fn();
  });

  it("renders tools grouped by tag", () => {
    render(
      <ToolWorkspace
        tools={defaultTools}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByText(/3 endpoints found/i)).toBeInTheDocument();
    expect(screen.getByText("users")).toBeInTheDocument();
    expect(screen.getByText("posts")).toBeInTheDocument();
  });

  it("renders empty state when no tools", () => {
    render(
      <ToolWorkspace
        tools={[]}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByText("No tools found")).toBeInTheDocument();
  });

  it("calls onSelectAll when Select All is clicked", async () => {
    const user = userEvent.setup();
    render(
      <ToolWorkspace
        tools={defaultTools}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onConfirm={onConfirm}
      />,
    );
    const buttons = screen.getAllByRole("button", { name: /Select All/i });
    const footerBtn = buttons.find((b) => b.textContent === "Select All");
    expect(footerBtn).toBeDefined();
    await user.click(footerBtn!);
    expect(onSelectAll).toHaveBeenCalledWith([
      "get-users",
      "create-user",
      "get-posts",
    ]);
  });

  it("calls onDeselectAll when Deselect All is clicked", async () => {
    const user = userEvent.setup();
    const allNames = ["get-users", "create-user", "get-posts"];
    render(
      <ToolWorkspace
        tools={defaultTools}
        selected={new Set(allNames)}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onConfirm={onConfirm}
      />,
    );
    const buttons = screen.getAllByRole("button", { name: /Deselect All/i });
    const footerBtn = buttons.find((b) => b.textContent === "Deselect All");
    expect(footerBtn).toBeDefined();
    await user.click(footerBtn!);
    expect(onDeselectAll).toHaveBeenCalledWith(allNames);
  });

  it("calls onConfirm when Continue is clicked", async () => {
    const user = userEvent.setup();
    render(
      <ToolWorkspace
        tools={defaultTools}
        selected={new Set(["get-users"])}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onConfirm={onConfirm}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Continue/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("disables Continue when onConfirmDisabled is true", () => {
    render(
      <ToolWorkspace
        tools={defaultTools}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onConfirm={onConfirm}
        onConfirmDisabled
      />,
    );
    expect(screen.getByRole("button", { name: /Continue/i })).toBeDisabled();
  });

  it("shows LargeSpecWarning when tools exceed 200", () => {
    const manyTools = Array.from({ length: 201 }, (_, i) =>
      createTool({
        name: `tool-${i}`,
        path: `/path/${i}`,
        tags: ["bulk"],
      }),
    );
    render(
      <ToolWorkspace
        tools={manyTools}
        selected={new Set()}
        onToggle={onToggle}
        onSelectAll={onSelectAll}
        onDeselectAll={onDeselectAll}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByText("Large spec detected")).toBeInTheDocument();
    expect(screen.getByText("201 endpoints")).toBeInTheDocument();
  });
});
