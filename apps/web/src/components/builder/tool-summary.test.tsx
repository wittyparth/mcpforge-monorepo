import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToolSummary } from "./tool-summary";

describe("ToolSummary", () => {
  let onSearch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSearch = vi.fn();
  });

  it("renders total count", () => {
    render(
      <ToolSummary total={10} selected={3} excluded={7} onSearch={onSearch} />,
    );
    expect(screen.getByText("10 endpoints found")).toBeInTheDocument();
  });

  it("renders selected count badge", () => {
    render(
      <ToolSummary total={10} selected={3} excluded={7} onSearch={onSearch} />,
    );
    expect(screen.getByText("3 selected")).toBeInTheDocument();
  });

  it("renders excluded count badge", () => {
    render(
      <ToolSummary total={10} selected={3} excluded={7} onSearch={onSearch} />,
    );
    expect(screen.getByText("7 excluded")).toBeInTheDocument();
  });

  it("shows zero-selected warning when no tools selected", () => {
    render(
      <ToolSummary total={5} selected={0} excluded={5} onSearch={onSearch} />,
    );
    expect(
      screen.getByText("Select at least 1 tool to continue"),
    ).toBeInTheDocument();
  });

  it("hides zero-selected warning when tools are selected", () => {
    render(
      <ToolSummary total={5} selected={3} excluded={2} onSearch={onSearch} />,
    );
    expect(
      screen.queryByText("Select at least 1 tool to continue"),
    ).not.toBeInTheDocument();
  });

  it("calls onSearch when typing in the filter input", async () => {
    const user = userEvent.setup();
    render(
      <ToolSummary total={10} selected={0} excluded={10} onSearch={onSearch} />,
    );
    const input = screen.getByLabelText(/filter tools/i);
    await user.type(input, "users");
    await waitFor(
      () => {
        expect(onSearch).toHaveBeenCalledWith("users");
      },
      { timeout: 3000 },
    );
  });

  it("renders singular 'endpoint' when total is 1", () => {
    render(
      <ToolSummary total={1} selected={0} excluded={1} onSearch={onSearch} />,
    );
    expect(screen.getByText("1 endpoint found")).toBeInTheDocument();
  });
});
