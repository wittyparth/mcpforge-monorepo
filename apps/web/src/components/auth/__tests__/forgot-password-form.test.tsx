import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ForgotPasswordForm } from "../forgot-password-form";

// Mock the hook
const mockMutate = vi.fn();
vi.mock("@/hooks/use-auth", () => ({
  useForgotPassword: () => ({
    mutate: mockMutate,
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
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

describe("ForgotPasswordForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders email field and submit button", () => {
    render(<ForgotPasswordForm />, { wrapper: createWrapper() });
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /send reset link/i }),
    ).toBeInTheDocument();
  });

  it("does not call mutate for invalid email", async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordForm />, { wrapper: createWrapper() });

    const emailInput = screen.getByLabelText("Email");
    await user.clear(emailInput);
    await user.type(emailInput, "not-an-email");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("calls mutate with email on valid submit", async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordForm />, { wrapper: createWrapper() });

    const emailInput = screen.getByLabelText("Email");
    await user.type(emailInput, "user@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith("user@example.com");
    });
  });
});
