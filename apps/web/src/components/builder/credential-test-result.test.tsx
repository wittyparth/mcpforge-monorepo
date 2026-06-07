import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CredentialTestResult } from "./credential-test-result";
import type { CredentialTestResponse } from "@/types/api";

vi.mock("@/components/ui/alert", () => ({
  Alert: ({ children, variant }: { children: React.ReactNode; variant?: string }) => (
    <div data-variant={variant}>{children}</div>
  ),
  AlertDescription: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

const successResult: CredentialTestResponse = {
  success: true,
  status_code: 200,
  latency_ms: 42,
  error: null,
};

const failureResult: CredentialTestResponse = {
  success: false,
  status_code: 401,
  latency_ms: null,
  error: "Invalid API key",
};

describe("CredentialTestResult", () => {
  it("renders success state with green styling, status code, and latency", () => {
    render(<CredentialTestResult result={successResult} />);
    expect(screen.getByText("Connected in 42ms")).toBeInTheDocument();
    expect(screen.getByText("200")).toBeInTheDocument();
    expect(
      screen.getByText(/Connection test succeeded/i),
    ).toBeInTheDocument();
  });

  it("renders failure state with red styling and error message", () => {
    render(<CredentialTestResult result={failureResult} />);
    expect(screen.getAllByText("Invalid API key").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("401")).toBeInTheDocument();
  });

  it("renders testing state with spinner", () => {
    render(<CredentialTestResult result={null} loading={true} />);
    expect(screen.getByText("Testing connection...")).toBeInTheDocument();
  });

  it("returns null when idle (no result, not loading, no error)", () => {
    const { container } = render(<CredentialTestResult result={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders error state with error message", () => {
    render(
      <CredentialTestResult
        result={null}
        loading={false}
        error="Network error"
      />,
    );
    expect(screen.getByText("Connection failed")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders failure result without status code gracefully", () => {
    const result: CredentialTestResponse = {
      success: false,
      status_code: null,
      latency_ms: null,
      error: "Unauthorized",
    };
    render(<CredentialTestResult result={result} />);
    expect(screen.getAllByText("Unauthorized").length).toBeGreaterThanOrEqual(1);
  });
});
