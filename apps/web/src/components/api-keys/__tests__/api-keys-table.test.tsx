import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ApiKeysTable } from "../api-keys-table";
import type { ApiKeyResponse } from "@/types/api";

const mockKeys: ApiKeyResponse[] = [
  {
    id: "key-1",
    name: "CI/CD Pipeline",
    key_prefix: "mcpforge_li",
    scopes: ["servers:read", "servers:write"],
    last_used_at: "2025-06-01T00:00:00Z",
    expires_at: null,
    revoked_at: null,
    created_at: "2025-05-01T00:00:00Z",
  },
  {
    id: "key-2",
    name: "Old Key",
    key_prefix: "mcpforge_ol",
    scopes: ["admin"],
    last_used_at: null,
    expires_at: null,
    revoked_at: "2025-06-01T00:00:00Z",
    created_at: "2025-01-01T00:00:00Z",
  },
];

describe("ApiKeysTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders key prefix instead of full key", () => {
    render(<ApiKeysTable keys={mockKeys} showRevoked={false} />);
    expect(screen.getByText("CI/CD Pipeline")).toBeInTheDocument();
    expect(screen.getByText("mcpforge_li...")).toBeInTheDocument();
  });

  it("filters out revoked keys when showRevoked is false", () => {
    render(<ApiKeysTable keys={mockKeys} showRevoked={false} />);
    expect(screen.getByText("CI/CD Pipeline")).toBeInTheDocument();
    expect(screen.queryByText("Old Key")).not.toBeInTheDocument();
  });

  it("shows empty state when no keys exist", () => {
    render(<ApiKeysTable keys={[]} showRevoked={false} />);
    expect(
      screen.getByText(/haven't created any API keys/i),
    ).toBeInTheDocument();
  });
});
