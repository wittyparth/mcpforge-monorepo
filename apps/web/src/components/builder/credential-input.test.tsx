import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CredentialInput } from "./credential-input";
import type {
  CredentialInfo,
  CredentialCreateRequest,
  CredentialTestRequest,
  CredentialTestResponse,
} from "@/types/api";

vi.mock("@/components/ui/alert", () => ({
  Alert: ({ children, ...props }: { children: React.ReactNode; variant?: string }) => (
    <div {...props}>{children}</div>
  ),
  AlertDescription: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  AlertTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

const existingCredentials: CredentialInfo[] = [
  {
    id: "1",
    env_var_name: "EXISTING_KEY",
    auth_scheme: "api_key",
    auth_header_name: null,
    encryption_key_id: null,
    rotated_at: null,
    last_used_at: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: null,
  },
];

describe("CredentialInput", () => {
  let onAdd: ReturnType<typeof vi.fn>;
  let onTest: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onAdd = vi.fn().mockResolvedValue(undefined);
    onTest = vi.fn().mockResolvedValue({
      success: true,
      status_code: 200,
      latency_ms: 42,
      error: null,
    } satisfies CredentialTestResponse);
  });

  it("renders env_var_name and value fields", () => {
    render(
      <CredentialInput
        onAdd={onAdd}
        onTest={onTest}
        existingCredentials={[]}
        authScheme="bearer"
      />,
    );
    expect(screen.getByLabelText(/environment variable name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^value$/i)).toBeInTheDocument();
  });

  it("shows auth header name field for api_key scheme", () => {
    render(
      <CredentialInput
        onAdd={onAdd}
        onTest={onTest}
        existingCredentials={[]}
        authScheme="api_key"
      />,
    );
    expect(screen.getByLabelText(/auth header name/i)).toBeInTheDocument();
  });

  it("hides auth header name field for non-api_key schemes", () => {
    render(
      <CredentialInput
        onAdd={onAdd}
        onTest={onTest}
        existingCredentials={[]}
        authScheme="bearer"
      />,
    );
    expect(screen.queryByLabelText(/auth header name/i)).not.toBeInTheDocument();
  });

  it("shows no-auth message when authScheme is none", () => {
    render(
      <CredentialInput
        onAdd={onAdd}
        onTest={onTest}
        existingCredentials={[]}
        authScheme="none"
      />,
    );
    expect(
      screen.getByText(/No authentication selected/i),
    ).toBeInTheDocument();
  });

  it("calls onTest when Test Connection is clicked", async () => {
    const user = userEvent.setup();
    render(
      <CredentialInput
        onAdd={onAdd}
        onTest={onTest}
        existingCredentials={[]}
        authScheme="bearer"
      />,
    );
    await user.type(screen.getByLabelText(/environment variable name/i), "MY_KEY");
    await user.type(screen.getByLabelText(/^value$/i), "secret123");
    await user.click(screen.getByRole("button", { name: /test connection/i }));
    await waitFor(() => {
      expect(onTest).toHaveBeenCalledWith({
        env_var_name: "MY_KEY",
        test_value: "secret123",
      } satisfies CredentialTestRequest);
    });
  });

  it("calls onAdd when Save Credential is clicked", async () => {
    const user = userEvent.setup();
    render(
      <CredentialInput
        onAdd={onAdd}
        onTest={onTest}
        existingCredentials={[]}
        authScheme="bearer"
      />,
    );
    await user.type(screen.getByLabelText(/environment variable name/i), "MY_KEY");
    await user.type(screen.getByLabelText(/^value$/i), "secret123");
    await user.click(screen.getByRole("button", { name: /save credential/i }));
    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledWith(
        expect.objectContaining({
          env_var_name: "MY_KEY",
          value: "secret123",
          auth_scheme: "bearer",
        } satisfies Partial<CredentialCreateRequest>),
      );
    });
  });

  it("shows warning when env var name already exists", async () => {
    const user = userEvent.setup();
    render(
      <CredentialInput
        onAdd={onAdd}
        onTest={onTest}
        existingCredentials={existingCredentials}
        authScheme="bearer"
      />,
    );
    await user.type(
      screen.getByLabelText(/environment variable name/i),
      "existing_key",
    );
    await waitFor(() => {
      expect(
        screen.getByText(/This credential already exists/i),
      ).toBeInTheDocument();
    });
  });

  it("enforces uppercase env var name", async () => {
    const user = userEvent.setup();
    render(
      <CredentialInput
        onAdd={onAdd}
        onTest={onTest}
        existingCredentials={[]}
        authScheme="bearer"
      />,
    );
    const input = screen.getByLabelText(/environment variable name/i);
    await user.type(input, "my_key");
    await waitFor(() => {
      expect((input as HTMLInputElement).value).toBe("MY_KEY");
    });
  });
});
