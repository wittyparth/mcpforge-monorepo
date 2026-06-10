import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VerifyEmailBanner } from "../verify-email-banner";

const mockMutate = vi.fn();
vi.mock("@/hooks/use-auth", () => ({
  useResendVerification: () => ({
    mutate: mockMutate,
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

describe("VerifyEmailBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders verification prompt", () => {
    render(<VerifyEmailBanner />, { wrapper: createWrapper() });
    expect(
      screen.getByText(/please verify your email/i),
    ).toBeInTheDocument();
  });

  it("hides when dismiss button is clicked", async () => {
    const user = userEvent.setup();
    render(<VerifyEmailBanner />, { wrapper: createWrapper() });

    expect(
      screen.getByText(/please verify your email/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /dismiss/i }));

    expect(
      screen.queryByText(/please verify your email/i),
    ).not.toBeInTheDocument();
  });

  it("calls resend mutation when resend button is clicked", async () => {
    const user = userEvent.setup();
    render(<VerifyEmailBanner />, { wrapper: createWrapper() });

    await user.click(screen.getByRole("button", { name: /resend email/i }));

    expect(mockMutate).toHaveBeenCalled();
  });
});
