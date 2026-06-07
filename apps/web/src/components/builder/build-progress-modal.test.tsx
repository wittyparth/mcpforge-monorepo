import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BuildProgressModal } from "./build-progress-modal";
import { useStartBuild, useBuildStatus } from "@/hooks/use-build-status";
import type { BuildStatusEvent } from "@/types/api";

vi.mock("@/hooks/use-build-status", () => ({
  useStartBuild: vi.fn(),
  useBuildStatus: vi.fn(),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div role="dialog">{children}</div> : null,
  DialogTrigger: () => null,
  DialogContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
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

vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
}));

describe("BuildProgressModal", () => {
  let onOpenChange: ReturnType<typeof vi.fn>;
  let onComplete: ReturnType<typeof vi.fn>;
  let onError: ReturnType<typeof vi.fn>;
  let mockMutateAsync: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onOpenChange = vi.fn();
    onComplete = vi.fn();
    onError = vi.fn();
    mockMutateAsync = vi.fn().mockResolvedValue(undefined);

    vi.mocked(useStartBuild).mockReturnValue({
      mutateAsync: mockMutateAsync,
      isError: false,
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useStartBuild>);

    vi.mocked(useBuildStatus).mockReturnValue({
      status: null,
      isStreaming: false,
      error: null,
      start: vi.fn(),
      stop: vi.fn(),
    } as unknown as ReturnType<typeof useBuildStatus>);
  });

  it("renders dialog content when open is true", () => {
    render(
      <BuildProgressModal
        open={true}
        onOpenChange={onOpenChange}
        slug="test-server"
        onComplete={onComplete}
        onError={onError}
      />,
    );
    expect(screen.getByText("Building your MCP server")).toBeInTheDocument();
  });

  it("does not render dialog content when open is false", () => {
    render(
      <BuildProgressModal
        open={false}
        onOpenChange={onOpenChange}
        slug="test-server"
        onComplete={onComplete}
        onError={onError}
      />,
    );
    expect(
      screen.queryByText("Building your MCP server"),
    ).not.toBeInTheDocument();
  });

  it("renders BuildStepIndicator", () => {
    render(
      <BuildProgressModal
        open={true}
        onOpenChange={onOpenChange}
        slug="test-server"
        onComplete={onComplete}
        onError={onError}
      />,
    );
    expect(screen.getByText("Parsing")).toBeInTheDocument();
    expect(screen.getByText("AI Enhancement")).toBeInTheDocument();
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("renders build event log entries", async () => {
    const events: BuildStatusEvent[] = [
      { stage: "parsing", progress: 10, message: "Parsing OpenAPI spec..." },
      { stage: "generating", progress: 50, message: "Generating tools..." },
    ];

    vi.mocked(useBuildStatus).mockReturnValue({
      status: events[0],
      isStreaming: true,
      error: null,
      start: vi.fn(),
      stop: vi.fn(),
    } as unknown as ReturnType<typeof useBuildStatus>);

    // We need to simulate React re-render when status changes.
    // Since we control the mock, events will be collected via the
    // useEffect that watches buildStatus.status.
    const { rerender } = render(
      <BuildProgressModal
        open={true}
        onOpenChange={onOpenChange}
        slug="test-server"
        onComplete={onComplete}
        onError={onError}
      />,
    );

    // Update mock status to second event and re-render
    vi.mocked(useBuildStatus).mockReturnValue({
      status: events[1],
      isStreaming: true,
      error: null,
      start: vi.fn(),
      stop: vi.fn(),
    } as unknown as ReturnType<typeof useBuildStatus>);

    rerender(
      <BuildProgressModal
        open={true}
        onOpenChange={onOpenChange}
        slug="test-server"
        onComplete={onComplete}
        onError={onError}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Parsing OpenAPI spec...")).toBeInTheDocument();
    });
  });

  it("shows Cancel button during build", async () => {
    render(
      <BuildProgressModal
        open={true}
        onOpenChange={onOpenChange}
        slug="test-server"
        onComplete={onComplete}
        onError={onError}
      />,
    );

    // Initially building, so Cancel should exist
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    });
  });

  it("shows correct description for each state", () => {
    const { rerender } = render(
      <BuildProgressModal
        open={true}
        onOpenChange={onOpenChange}
        slug="test-server"
        onComplete={onComplete}
        onError={onError}
      />,
    );
    // Building state
    expect(
      screen.getByText(/Your server is being built/i),
    ).toBeInTheDocument();

    // Completed state
    vi.mocked(useBuildStatus).mockReturnValue({
      status: { stage: "complete", progress: 100, message: "Done" },
      isStreaming: false,
      error: null,
      start: vi.fn(),
      stop: vi.fn(),
    } as unknown as ReturnType<typeof useBuildStatus>);

    rerender(
      <BuildProgressModal
        open={true}
        onOpenChange={onOpenChange}
        slug="test-server"
        onComplete={onComplete}
        onError={onError}
      />,
    );

    expect(screen.getByText(/Your MCP server is ready/i)).toBeInTheDocument();
  });
});
