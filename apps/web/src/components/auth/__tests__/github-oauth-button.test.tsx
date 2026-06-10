import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GithubOAuthButton } from "../github-oauth-button";

vi.mock("@/hooks/use-auth", () => ({}));

describe("GithubOAuthButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders 'Sign in with GitHub' for signin mode", () => {
    render(<GithubOAuthButton mode="signin" />);
    expect(
      screen.getByRole("button", { name: /sign in with github/i }),
    ).toBeInTheDocument();
  });

  it("renders 'Sign up with GitHub' for signup mode", () => {
    render(<GithubOAuthButton mode="signup" />);
    expect(
      screen.getByRole("button", { name: /sign up with github/i }),
    ).toBeInTheDocument();
  });

  it("redirects to GitHub OAuth URL on click", async () => {
    const user = userEvent.setup();
    const assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      value: { href: "", assign: assignSpy },
      writable: true,
    });

    render(<GithubOAuthButton mode="signin" />);
    await user.click(
      screen.getByRole("button", { name: /sign in with github/i }),
    );

    expect(window.location.href).toContain("/api/v1/auth/github");
  });
});
