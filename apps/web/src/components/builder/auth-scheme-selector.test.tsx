import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthSchemeSelector } from "./auth-scheme-selector";

describe("AuthSchemeSelector", () => {
  let onChange: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onChange = vi.fn();
  });

  it("renders all 5 auth scheme options", () => {
    render(<AuthSchemeSelector value="none" onChange={onChange} />);
    expect(screen.getByText("No authentication")).toBeInTheDocument();
    expect(screen.getByText("API Key")).toBeInTheDocument();
    expect(screen.getByText("Bearer Token")).toBeInTheDocument();
    expect(screen.getByText("Basic Auth")).toBeInTheDocument();
    expect(screen.getByText("OAuth 2.0")).toBeInTheDocument();
  });

  it("renders descriptions for each scheme", () => {
    render(<AuthSchemeSelector value="none" onChange={onChange} />);
    expect(screen.getByText("Public API, no credentials needed")).toBeInTheDocument();
    expect(
      screen.getByText(/Header-based API key/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/OAuth 2.0 \/ JWT in Authorization header/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Username and password/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Client credentials flow/i),
    ).toBeInTheDocument();
  });

  it("reflects the currently selected value", () => {
    const { rerender } = render(
      <AuthSchemeSelector value="bearer" onChange={onChange} />,
    );
    expect(screen.getByRole("radio", { name: /bearer token/i })).toBeInTheDocument();

    rerender(<AuthSchemeSelector value="api_key" onChange={onChange} />);
    expect(screen.getByRole("radio", { name: /api key/i })).toBeInTheDocument();
  });

  it("calls onChange with new value when clicking a scheme", async () => {
    const user = userEvent.setup();
    render(<AuthSchemeSelector value="none" onChange={onChange} />);
    await user.click(screen.getByText("Bearer Token"));
    expect(onChange).toHaveBeenCalledWith("bearer");
  });

  it("calls onChange with api_key when API Key is clicked", async () => {
    const user = userEvent.setup();
    render(<AuthSchemeSelector value="none" onChange={onChange} />);
    await user.click(screen.getByText("API Key"));
    expect(onChange).toHaveBeenCalledWith("api_key");
  });
});
