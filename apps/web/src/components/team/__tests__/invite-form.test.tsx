import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InviteForm } from "../invite-form";

const mockMutateAsync = vi.fn();
vi.mock("@/hooks/use-team", () => ({
  useInviteMember: () => ({
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

describe("InviteForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders email field and role selector", () => {
    render(<InviteForm />, { wrapper: createWrapper() });
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(screen.getByText(/role/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /send invitation/i }),
    ).toBeInTheDocument();
  });

  it("shows validation error for invalid email", async () => {
    const user = userEvent.setup();
    render(<InviteForm />, { wrapper: createWrapper() });

    await user.type(screen.getByLabelText("Email address"), "bad-email");
    await user.click(screen.getByRole("button", { name: /send invitation/i }));

    // form-level validation should trigger
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  it("submits form with email and default role", async () => {
    mockMutateAsync.mockResolvedValueOnce({
      id: "inv-1",
      email: "new@example.com",
      role: "viewer",
      token: "test-token",
      expires_at: new Date(Date.now() + 86400000).toISOString(),
      created_at: new Date().toISOString(),
    });

    const user = userEvent.setup();
    render(<InviteForm />, { wrapper: createWrapper() });

    await user.type(screen.getByLabelText("Email address"), "new@example.com");
    await user.click(screen.getByRole("button", { name: /send invitation/i }));

    expect(mockMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ email: "new@example.com" }),
    );
  });
});
