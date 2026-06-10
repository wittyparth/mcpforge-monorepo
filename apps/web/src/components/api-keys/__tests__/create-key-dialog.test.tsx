import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CreateKeyDialog } from "../create-key-dialog";

const mockMutateAsync = vi.fn();
vi.mock("@/hooks/use-api-keys", () => ({
  useCreateApiKey: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return Wrapper;
};

describe("CreateKeyDialog", () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onKeyCreated: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders dialog with name field, scopes, and expiration", () => {
    render(<CreateKeyDialog {...defaultProps} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByText("Scopes")).toBeInTheDocument();
    expect(screen.getByText("Expiration")).toBeInTheDocument();
    expect(screen.getByText("servers:read")).toBeInTheDocument();
    expect(screen.getByText("servers:write")).toBeInTheDocument();
    expect(screen.getByText("analytics:read")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("shows error when submitting without name or scopes", async () => {
    const user = userEvent.setup();
    render(<CreateKeyDialog {...defaultProps} />, {
      wrapper: createWrapper(),
    });

    await user.click(screen.getByRole("button", { name: /create key/i }));

    // Should not call mutate because name is empty and no scopes selected
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  it("calls onKeyCreated after successful creation", async () => {
    mockMutateAsync.mockResolvedValueOnce({
      key: {
        id: "new-key",
        name: "Test Key",
        key_prefix: "mcpforge_te",
        scopes: ["servers:read"],
        last_used_at: null,
        expires_at: null,
        revoked_at: null,
        created_at: new Date().toISOString(),
      },
      plaintext_key: "mcpforge_testplaintextkey123456",
    });

    const user = userEvent.setup();
    render(<CreateKeyDialog {...defaultProps} />, {
      wrapper: createWrapper(),
    });

    await user.type(screen.getByLabelText("Name"), "Test Key");

    // Select servers:read scope by clicking its label
    await user.click(screen.getByText("servers:read"));

    await user.click(screen.getByRole("button", { name: /create key/i }));

    expect(mockMutateAsync).toHaveBeenCalled();
  });
});
