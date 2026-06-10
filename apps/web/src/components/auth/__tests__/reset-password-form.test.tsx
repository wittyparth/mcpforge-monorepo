import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResetPasswordForm } from "../reset-password-form";

const mockMutate = vi.fn();
vi.mock("@/hooks/use-auth", () => ({
  useResetPassword: () => ({
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

describe("ResetPasswordForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders password and confirm password fields", () => {
    render(<ResetPasswordForm token="valid-token" />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByLabelText("New password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /reset password/i }),
    ).toBeInTheDocument();
  });

  it("shows error for password shorter than 12 characters", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordForm token="valid-token" />, {
      wrapper: createWrapper(),
    });

    await user.type(screen.getByLabelText("New password"), "short");
    await user.type(screen.getByLabelText("Confirm password"), "short");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(screen.getByText(/at least 12 characters/i)).toBeInTheDocument();
    });
  });

  it("shows error when passwords do not match", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordForm token="valid-token" />, {
      wrapper: createWrapper(),
    });

    await user.type(
      screen.getByLabelText("New password"),
      "longpassword123",
    );
    await user.type(
      screen.getByLabelText("Confirm password"),
      "differentpassword123",
    );
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    });
  });

  it("calls mutate with token and password on valid submit", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordForm token="test-token-abc" />, {
      wrapper: createWrapper(),
    });

    await user.type(
      screen.getByLabelText("New password"),
      "strongpassword123",
    );
    await user.type(
      screen.getByLabelText("Confirm password"),
      "strongpassword123",
    );
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith({
        token: "test-token-abc",
        password: "strongpassword123",
      });
    });
  });
});
