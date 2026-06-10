import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ToolDefinition } from "@/types/api";
import type { CallLogEntry, CallResponse } from "@/hooks/use-playground";
import { ToolBrowser } from "@/components/playground/tool-browser";
import { ToolForm } from "@/components/playground/tool-form";
import { ResponseViewer } from "@/components/playground/response-viewer";
import { CallLog } from "@/components/playground/call-log";
import { ShareTestButton } from "@/components/playground/share-test-button";
import { PlaygroundPage } from "@/components/playground/playground-page";

// ── Mocks ──────────────────────────────────────────────────────────

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

vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({ children, value, onValueChange }: { children: React.ReactNode; value?: string; onValueChange?: (v: string) => void }) => (
    <div>
      <select
        data-testid="select-trigger"
        value={value ?? ""}
        onChange={(e) => onValueChange?.(e.target.value)}
      >
        <option value="">Select…</option>
        {(children as React.ReactNode[]).map((child) => {
          // Extract SelectItem children
          if (
            child &&
            typeof child === "object" &&
            "props" in child
          ) {
            const el = child as React.ReactElement<{ children?: React.ReactNode }>;
            const items = el.props?.children;
            if (Array.isArray(items)) {
              return items.map((item: React.ReactElement<{ value?: string; children?: React.ReactNode }>) => (
                <option key={item.props?.value ?? ""} value={item.props?.value ?? ""}>
                  {item.props?.children}
                </option>
              ));
            }
          }
          return null;
        })}
      </select>
    </div>
  ),
  SelectTrigger: ({ children, id }: { children: React.ReactNode; id?: string }) => (
    <div id={id}>{children}</div>
  ),
  SelectValue: ({ placeholder }: { placeholder?: string }) => (
    <span>{placeholder ?? "Select…"}</span>
  ),
  SelectContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SelectItem: ({ children, value }: { children: React.ReactNode; value: string }) => (
    <option value={value}>{children}</option>
  ),
}));

vi.mock("@/components/ui/switch", () => ({
  Switch: ({
    id,
    checked,
    onCheckedChange,
  }: {
    id?: string;
    checked?: boolean;
    onCheckedChange?: (checked: boolean) => void;
  }) => (
    <button
      id={id}
      role="switch"
      aria-checked={checked ?? false}
      onClick={() => onCheckedChange?.(!checked)}
    />
  ),
}));

vi.mock("@monaco-editor/react", () => ({
  __esModule: true,
  default: ({
    value,
    "data-testid": testId,
  }: {
    value?: string;
    "data-testid"?: string;
  }) => (
    <pre data-testid={testId ?? "monaco-editor"}>{value}</pre>
  ),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// ── Helpers ────────────────────────────────────────────────────────

function createTool(overrides: Partial<ToolDefinition> = {}): ToolDefinition {
  return {
    name: "echo",
    description: "Echo back the input message",
    input_schema: {
      type: "object",
      properties: {
        message: { type: "string", description: "Message to echo" },
      },
      required: ["message"],
    },
    base_url_override: null,
    operation_id: null,
    method: "POST",
    path: "/echo",
    original_operation_id: null,
    summary: "Echo a message",
    tags: ["utility"],
    parameters: [],
    request_body_schema: null,
    response_schemas: {},
    security_requirements: [],
    selected: true,
    warnings: [],
    ...overrides,
  };
}

function createCallResponse(overrides: Partial<CallResponse> = {}): CallResponse {
  return {
    content: [{ type: "text", text: "hello world" }],
    isError: false,
    request_id: "req-123",
    ...overrides,
  };
}

function createCallLogEntry(overrides: Partial<CallLogEntry> = {}): CallLogEntry {
  return {
    id: "call-1",
    toolName: "echo",
    arguments: { message: "hello" },
    response: createCallResponse(),
    timestamp: Date.now(),
    ...overrides,
  };
}

// ══════════════════════════════════════════════════════════════════════
// Tests
// ══════════════════════════════════════════════════════════════════════

describe("Playground — FormField Generators", () => {
  // Lazy import to avoid module-level mock issues
  const renderFormField = async (schema: Record<string, unknown>, name = "test") => {
    const { FormField } = await import(
      "@/components/playground/form-field-generators"
    );
    const onChange = vi.fn();
    return {
      ...render(
        <FormField
          schema={schema}
          name={name}
          value={undefined}
          onChange={onChange}
        />,
      ),
      onChange,
    };
  };

  it("renders a text input for string type", async () => {
    const { getByRole } = await renderFormField({ type: "string" });
    expect(getByRole("textbox")).toBeInTheDocument();
  });

  it("renders a number input for integer type", async () => {
    const { getByRole } = await renderFormField({ type: "integer" }, "count");
    expect(getByRole("spinbutton")).toBeInTheDocument();
  });

  it("renders a switch for boolean type", async () => {
    const { getByRole } = await renderFormField({ type: "boolean" }, "flag");
    expect(getByRole("switch")).toBeInTheDocument();
  });

  it("renders a select for enum type", async () => {
    const { getByTestId } = await renderFormField(
      { type: "string", enum: ["a", "b", "c"] },
      "choice",
    );
    expect(getByTestId("select-trigger")).toBeInTheDocument();
  });

  it("renders a textarea for JSON object type", async () => {
    const { getByRole } = await renderFormField(
      { type: "object", properties: { key: { type: "string" } } },
      "data",
    );
    expect(getByRole("textbox")).toBeInTheDocument();
  });
});

describe("Playground — ToolBrowser", () => {

  const defaultTools: ToolDefinition[] = [
    createTool({ name: "echo", method: "POST", path: "/echo" }),
    createTool({
      name: "get-user",
      method: "GET",
      path: "/users/{id}",
      description: "Get a user by ID",
    }),
    createTool({
      name: "delete-user",
      method: "DELETE",
      path: "/users/{id}",
      description: "Delete a user",
    }),
  ];

  it("renders all tools in the list", () => {
    const onSelectTool = vi.fn();
    render(
      <ToolBrowser
        tools={defaultTools}
        selectedTool={null}
        onSelectTool={onSelectTool}
        isConnected={true}
        error={null}
      />,
    );
    expect(screen.getByText("echo")).toBeInTheDocument();
    expect(screen.getByText("get-user")).toBeInTheDocument();
    expect(screen.getByText("delete-user")).toBeInTheDocument();
  });

  it("shows tool count badge", () => {
    render(
      <ToolBrowser
        tools={defaultTools}
        selectedTool={null}
        onSelectTool={vi.fn()}
        isConnected={true}
        error={null}
      />,
    );
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("calls onSelectTool when a tool is clicked", async () => {
    const user = userEvent.setup();
    const onSelectTool = vi.fn();
    render(
      <ToolBrowser
        tools={defaultTools}
        selectedTool={null}
        onSelectTool={onSelectTool}
        isConnected={true}
        error={null}
      />,
    );
    await user.click(screen.getByText("echo"));
    expect(onSelectTool).toHaveBeenCalledWith(
      expect.objectContaining({ name: "echo" }),
    );
  });

  it("filters tools by search query", async () => {
    const user = userEvent.setup();
    render(
      <ToolBrowser
        tools={defaultTools}
        selectedTool={null}
        onSelectTool={vi.fn()}
        isConnected={true}
        error={null}
      />,
    );
    const searchInput = screen.getByPlaceholderText("Search tools…");
    await user.type(searchInput, "delete");

    expect(screen.getByText("delete-user")).toBeInTheDocument();
    expect(screen.queryByText("echo")).not.toBeInTheDocument();
    expect(screen.queryByText("get-user")).not.toBeInTheDocument();
  });

  it("shows disconnected state when not connected", () => {
    render(
      <ToolBrowser
        tools={defaultTools}
        selectedTool={null}
        onSelectTool={vi.fn()}
        isConnected={false}
        error={null}
      />,
    );
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });

  it("shows error banner when error is provided", () => {
    render(
      <ToolBrowser
        tools={defaultTools}
        selectedTool={null}
        onSelectTool={vi.fn()}
        isConnected={false}
        error="Connection refused"
      />,
    );
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
  });

  it("shows empty state when no tools are available", () => {
    render(
      <ToolBrowser
        tools={[]}
        selectedTool={null}
        onSelectTool={vi.fn()}
        isConnected={true}
        error={null}
      />,
    );
    expect(screen.getByText("No tools available")).toBeInTheDocument();
  });

  it("highlights the selected tool", () => {
    const selectedTool = defaultTools[0]!;
    render(
      <ToolBrowser
        tools={defaultTools}
        selectedTool={selectedTool}
        onSelectTool={vi.fn()}
        isConnected={true}
        error={null}
      />,
    );
    const option = screen.getByRole("option", { name: /echo/i });
    expect(option).toHaveAttribute("aria-selected", "true");
  });
});

describe("Playground — ToolForm", () => {

  it("shows empty state when no tool is selected", () => {
    render(
      <ToolForm tool={null} isCalling={false} onCallTool={vi.fn()} onClear={vi.fn()} />,
    );
    expect(
      screen.getByText("Select a tool to configure and call it"),
    ).toBeInTheDocument();
  });

  it("renders form fields from tool input_schema", () => {
    const tool = createTool({
      input_schema: {
        type: "object",
        properties: {
          message: { type: "string", description: "Message to echo" },
          count: { type: "integer", description: "Repeat count" },
          verbose: { type: "boolean", description: "Enable verbose output" },
        },
        required: ["message"],
      },
    });
    render(
      <ToolForm tool={tool} isCalling={false} onCallTool={vi.fn()} onClear={vi.fn()} />,
    );
    expect(screen.getByText("Message")).toBeInTheDocument();
    expect(screen.getByText("Count")).toBeInTheDocument();
    expect(screen.getByText("Verbose")).toBeInTheDocument();
  });

  it("shows tool name in header", () => {
    const tool = createTool({ name: "my-tool" });
    render(
      <ToolForm tool={tool} isCalling={false} onCallTool={vi.fn()} onClear={vi.fn()} />,
    );
    expect(screen.getByText("my-tool")).toBeInTheDocument();
  });

  it("calls onCallTool with correct arguments on submit", async () => {
    const user = userEvent.setup();
    const onCallTool = vi.fn();
    const tool = createTool({
      input_schema: {
        type: "object",
        properties: {
          message: { type: "string" },
        },
        required: ["message"],
      },
    });
    render(
      <ToolForm tool={tool} isCalling={false} onCallTool={onCallTool} onClear={vi.fn()} />,
    );

    const input = screen.getByRole("textbox");
    await user.type(input, "hello world");
    await user.click(screen.getByRole("button", { name: /Call Tool/i }));

    expect(onCallTool).toHaveBeenCalledWith("echo", { message: "hello world" });
  });

  it("disables Call Tool button while calling", () => {
    const tool = createTool();
    render(
      <ToolForm tool={tool} isCalling={true} onCallTool={vi.fn()} onClear={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /Calling/i })).toBeDisabled();
  });

  it("resets form values when reset button is clicked", async () => {
    const user = userEvent.setup();
    const tool = createTool({
      input_schema: {
        type: "object",
        properties: {
          message: { type: "string", default: "default-value" },
        },
      },
    });
    render(
      <ToolForm tool={tool} isCalling={false} onCallTool={vi.fn()} onClear={vi.fn()} />,
    );

    const input = screen.getByRole("textbox");
    await user.clear(input);
    await user.type(input, "custom value");
    expect(input).toHaveValue("custom value");

    await user.click(screen.getByLabelText("Reset form values"));
    expect(input).toHaveValue("default-value");
  });

  it("shows 'No input parameters required' for schemaless tools", () => {
    const tool = createTool({ input_schema: {} });
    render(
      <ToolForm tool={tool} isCalling={false} onCallTool={vi.fn()} onClear={vi.fn()} />,
    );
    expect(
      screen.getByText("No input parameters required"),
    ).toBeInTheDocument();
  });
});

describe("Playground — ResponseViewer", () => {

  it("shows empty state when no response", () => {
    render(
      <ResponseViewer response={null} latencyMs={null} toolName={null} />,
    );
    expect(
      screen.getByText("Response will appear here after a tool call"),
    ).toBeInTheDocument();
  });

  it("renders response with formatted JSON", () => {
    const response = createCallResponse();
    render(
      <ResponseViewer response={response} latencyMs={42} toolName="echo" />,
    );
    expect(screen.getByText("Response")).toBeInTheDocument();
    expect(screen.getByText("200 OK")).toBeInTheDocument();
    expect(screen.getByText("42 ms")).toBeInTheDocument();
  });

  it("shows error state for error responses", () => {
    const response = createCallResponse({
      isError: true,
      content: [{ type: "text", text: "Tool execution failed" }],
    });
    render(
      <ResponseViewer response={response} latencyMs={12} toolName="echo" />,
    );
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText("Tool call returned an error")).toBeInTheDocument();
  });

  it("displays tool name in meta tab", () => {
    const response = createCallResponse();
    render(
      <ResponseViewer response={response} latencyMs={100} toolName="my-tool" />,
    );
    // Meta info should show the tool name
    expect(screen.getByText("Meta")).toBeInTheDocument();
  });
});

describe("Playground — CallLog", () => {

  it("shows empty state when no entries", () => {
    render(
      <CallLog entries={[]} onClear={vi.fn()} onReplayEntry={vi.fn()} />,
    );
    expect(screen.getByText("No calls yet")).toBeInTheDocument();
  });

  it("renders call log entries", () => {
    const entries = [
      createCallLogEntry({ id: "1", toolName: "echo" }),
      createCallLogEntry({ id: "2", toolName: "get-user" }),
    ];
    render(
      <CallLog entries={entries} onClear={vi.fn()} onReplayEntry={vi.fn()} />,
    );
    expect(screen.getByText("echo")).toBeInTheDocument();
    expect(screen.getByText("get-user")).toBeInTheDocument();
  });

  it("shows entry count badge", () => {
    const entries = [
      createCallLogEntry({ id: "1" }),
      createCallLogEntry({ id: "2" }),
      createCallLogEntry({ id: "3" }),
    ];
    render(
      <CallLog entries={entries} onClear={vi.fn()} onReplayEntry={vi.fn()} />,
    );
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("calls onClear when clear button is clicked", async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();
    const entries = [createCallLogEntry()];
    render(
      <CallLog entries={entries} onClear={onClear} onReplayEntry={vi.fn()} />,
    );
    await user.click(screen.getByLabelText("Clear call log"));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("displays arguments in the log entry", () => {
    const entries = [
      createCallLogEntry({ arguments: { message: "test-input" } }),
    ];
    render(
      <CallLog entries={entries} onClear={vi.fn()} onReplayEntry={vi.fn()} />,
    );
    expect(screen.getByText('{"message":"test-input"}')).toBeInTheDocument();
  });

  it("calls onReplayEntry when replay button is clicked", async () => {
    const user = userEvent.setup();
    const onReplayEntry = vi.fn();
    const entry = createCallLogEntry({ id: "call-replay-1", toolName: "echo" });
    render(
      <CallLog entries={[entry]} onClear={vi.fn()} onReplayEntry={onReplayEntry} />,
    );
    await user.hover(screen.getByText("echo"));
    await user.click(screen.getByLabelText("Replay echo call"));
    expect(onReplayEntry).toHaveBeenCalledWith(entry);
  });
});

describe("Playground — ShareTestButton", () => {

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is disabled when enabled is false", () => {
    render(
      <ShareTestButton
        serverSlug="test-server"
        toolName="echo"
        parameters={{}}
        enabled={false}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Share/i }),
    ).toBeDisabled();
  });

  it("is enabled when enabled is true and toolName is set", () => {
    render(
      <ShareTestButton
        serverSlug="test-server"
        toolName="echo"
        parameters={{ message: "hi" }}
        enabled={true}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Share/i }),
    ).not.toBeDisabled();
  });

  it("generates share URL and copies to clipboard on click", async () => {
    const user = userEvent.setup();
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText: writeTextMock } });

    render(
      <ShareTestButton
        serverSlug="my-server"
        toolName="echo"
        parameters={{ message: "hello" }}
        enabled={true}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Share/i }));

    expect(writeTextMock).toHaveBeenCalledOnce();
    const calledUrl = writeTextMock.mock.calls[0]![0] as string;
    expect(calledUrl).toContain("/dashboard/servers/my-server/playground");
    expect(calledUrl).toContain("tool=echo");
    expect(calledUrl).toContain("params=");
  });

  it("does not include params when parameters are empty", async () => {
    const user = userEvent.setup();
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText: writeTextMock } });

    render(
      <ShareTestButton
        serverSlug="my-server"
        toolName="echo"
        parameters={{}}
        enabled={true}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Share/i }));

    const calledUrl = writeTextMock.mock.calls[0]![0] as string;
    expect(calledUrl).toContain("tool=echo");
    expect(calledUrl).not.toContain("params=");
  });
});

describe("Playground — PlaygroundPage integration", () => {

  vi.mock("@/hooks/use-playground", () => ({
    usePlayground: () => ({
      tools: [
        createTool({ name: "echo" }),
        createTool({ name: "get-user", method: "GET", path: "/users/{id}" }),
      ],
      selectedTool: createTool({ name: "echo" }),
      response: null,
      callLog: [],
      isConnected: true,
      reconnectAttempt: 0,
      error: null,
      selectTool: vi.fn(),
      callTool: vi.fn(),
      clearLog: vi.fn(),
      clearResponse: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
    }),
  }));

  it("renders all 4 panels", () => {
    render(
      <PlaygroundPage
        serverId="test-id"
        serverSlug="test-server"
        serverName="Test Server"
        accessToken={null}
      />,
    );

    // Panel 1: Tool Browser
    expect(screen.getByText("Tools")).toBeInTheDocument();
    // Panel 2: Tool Form
    expect(screen.getByText("echo")).toBeInTheDocument();
    // Panel 3: Response Viewer (empty state)
    expect(
      screen.getByText("Response will appear here after a tool call"),
    ).toBeInTheDocument();
    // Panel 4: Call Log
    expect(screen.getByText("Call Log")).toBeInTheDocument();
  });

  it("shows server name and connection status", () => {
    render(
      <PlaygroundPage
        serverId="test-id"
        serverSlug="test-server"
        serverName="My API Server"
        accessToken={null}
      />,
    );
    expect(screen.getByText("My API Server")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows share button", () => {
    render(
      <PlaygroundPage
        serverId="test-id"
        serverSlug="test-server"
        serverName="Test Server"
        accessToken={null}
      />,
    );
    expect(screen.getByText("Share")).toBeInTheDocument();
  });
});
