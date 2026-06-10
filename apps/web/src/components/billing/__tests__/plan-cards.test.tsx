import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PlanCards } from "../plan-cards";

vi.mock("@/hooks/use-billing", () => ({
  usePlans: () => ({
    data: {
      plans: [
        {
          id: "free",
          name: "Free",
          price_cents: 0,
          currency: "usd",
          period: "monthly",
          features: ["2 MCP servers", "500 calls/mo"],
          popular: false,
          min_seats: null,
        },
        {
          id: "pro",
          name: "Pro",
          price_cents: 1200,
          currency: "usd",
          period: "monthly",
          features: ["10 MCP servers", "10K calls/mo"],
          popular: true,
          min_seats: null,
        },
        {
          id: "team",
          name: "Team",
          price_cents: 2900,
          currency: "usd",
          period: "monthly",
          features: ["Unlimited servers", "100K calls/mo"],
          popular: false,
          min_seats: 2,
        },
      ],
    },
    isLoading: false,
  }),
  useCurrentSubscription: () => ({
    data: { plan: "free", status: "active" },
  }),
  useCheckout: () => ({
    mutate: vi.fn(),
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

describe("PlanCards", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all three plans", () => {
    render(<PlanCards />, { wrapper: createWrapper() });
    expect(screen.getAllByText("Free").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Pro")).toBeInTheDocument();
    expect(screen.getByText("Team")).toBeInTheDocument();
  });

  it("shows 'Current Plan' badge for active plan", () => {
    render(<PlanCards />, { wrapper: createWrapper() });
    const badges = screen.getAllByText("Current Plan");
    expect(badges.length).toBeGreaterThan(0);
  });

  it("disables the current plan button", () => {
    render(<PlanCards />, { wrapper: createWrapper() });
    const currentPlanButton = screen.getByRole("button", {
      name: /current plan/i,
    });
    expect(currentPlanButton).toBeDisabled();
  });
});
