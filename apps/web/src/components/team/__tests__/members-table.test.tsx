import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MembersTable } from "../members-table";
import type { TeamMemberResponse } from "@/types/api";

vi.mock("@/hooks/use-team", () => ({
  useTeamMembers: () => ({
    data: {
      members: [
        {
          user_id: "user-1",
          email: "admin@example.com",
          display_name: "Admin User",
          avatar_url: null,
          role: "admin",
          joined_at: "2025-01-01T00:00:00Z",
        } satisfies TeamMemberResponse,
        {
          user_id: "user-2",
          email: "editor@example.com",
          display_name: "Editor User",
          avatar_url: null,
          role: "editor",
          joined_at: "2025-01-02T00:00:00Z",
        } satisfies TeamMemberResponse,
        {
          user_id: "user-3",
          email: "viewer@example.com",
          display_name: null,
          avatar_url: null,
          role: "viewer",
          joined_at: "2025-01-03T00:00:00Z",
        } satisfies TeamMemberResponse,
      ],
    },
    isLoading: false,
  }),
  useUpdateMemberRole: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useRemoveMember: () => ({
    mutateAsync: vi.fn(),
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

describe("MembersTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all member rows", () => {
    render(<MembersTable currentUserId="user-1" isAdmin={true} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.getByText("editor@example.com")).toBeInTheDocument();
    expect(screen.getAllByText("viewer@example.com").length).toBeGreaterThanOrEqual(1);
  });

  it("shows 'You' badge for current user", () => {
    render(<MembersTable currentUserId="user-1" isAdmin={true} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText("You")).toBeInTheDocument();
  });

  it("shows role badges for all members", () => {
    render(<MembersTable currentUserId="user-1" isAdmin={true} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("Editor")).toBeInTheDocument();
    expect(screen.getByText("Viewer")).toBeInTheDocument();
  });
});
