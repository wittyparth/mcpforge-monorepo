import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LargeSpecWarning } from "./large-spec-warning";

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div role="dialog">{children}</div> : null,
  DialogTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
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

describe("LargeSpecWarning", () => {
  let onOpenChange: ReturnType<typeof vi.fn>;
  let onConfirm: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onOpenChange = vi.fn();
    onConfirm = vi.fn();
  });

  it("renders warning title", () => {
    render(
      <LargeSpecWarning
        endpointCount={250}
        open={true}
        onOpenChange={onOpenChange}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByText("Large spec detected")).toBeInTheDocument();
  });

  it("renders endpoint count in the message", () => {
    render(
      <LargeSpecWarning
        endpointCount={250}
        open={true}
        onOpenChange={onOpenChange}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByText(/250 endpoints/)).toBeInTheDocument();
  });

  it("does not render when open is false", () => {
    render(
      <LargeSpecWarning
        endpointCount={250}
        open={false}
        onOpenChange={onOpenChange}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.queryByText("Large spec detected")).not.toBeInTheDocument();
  });

  it("calls onConfirm and onOpenChange(false) when Continue is clicked", async () => {
    const user = userEvent.setup();
    render(
      <LargeSpecWarning
        endpointCount={250}
        open={true}
        onOpenChange={onOpenChange}
        onConfirm={onConfirm}
      />,
    );
    await user.click(screen.getByText("Continue with all selected"));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls onOpenChange(false) when Let me curate first is clicked", async () => {
    const user = userEvent.setup();
    render(
      <LargeSpecWarning
        endpointCount={250}
        open={true}
        onOpenChange={onOpenChange}
        onConfirm={onConfirm}
      />,
    );
    await user.click(screen.getByText("Let me curate first"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
