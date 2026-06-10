import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DuplicateServerDialog } from "../duplicate-server-dialog";

const mockMutate = vi.fn();
vi.mock("@/hooks/use-servers", () => ({
  useDuplicateServer: () => ({
    mutate: mockMutate,
    isPending: false,
  }),
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

describe("DuplicateServerDialog", () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    serverId: "server-123",
    currentName: "My API Server",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders name and slug fields", () => {
    render(<DuplicateServerDialog {...defaultProps} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByLabelText("New name")).toBeInTheDocument();
    expect(screen.getByLabelText("Slug (optional)")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /duplicate server/i }),
    ).toBeInTheDocument();
  });

  it("pre-fills name with current name plus (copy)", () => {
    render(<DuplicateServerDialog {...defaultProps} />, {
      wrapper: createWrapper(),
    });
    const nameInput = screen.getByLabelText("New name") as HTMLInputElement;
    expect(nameInput.value).toBe("My API Server (copy)");
  });

  it("calls mutate with server id and form data on submit", async () => {
    const user = userEvent.setup();
    render(<DuplicateServerDialog {...defaultProps} />, {
      wrapper: createWrapper(),
    });

    await user.click(
      screen.getByRole("button", { name: /duplicate server/i }),
    );

    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "server-123",
          data: expect.objectContaining({ new_name: "My API Server (copy)" }),
        }),
        expect.anything(),
      );
    });
  });
});
