import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ServerConfigForm } from "./server-config-form";

vi.mock("@/components/ui/select", () => ({
  Select: ({
    children,
    onValueChange,
    defaultValue,
  }: {
    children: React.ReactNode;
    onValueChange?: (value: string) => void;
    defaultValue?: string;
  }) => (
    <div>
      <select
        data-testid="transport-select"
        defaultValue={defaultValue}
        onChange={(e) => onValueChange?.(e.target.value)}
      >
        {children}
      </select>
    </div>
  ),
  SelectTrigger: ({ children, id }: { children: React.ReactNode; id?: string }) => (
    <button id={id} type="button">{children}</button>
  ),
  SelectValue: ({ placeholder }: { placeholder?: string }) => (
    <span>{placeholder}</span>
  ),
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectItem: ({
    value,
    children,
  }: {
    value: string;
    children: React.ReactNode;
  }) => <option value={value}>{children}</option>,
}));

describe("ServerConfigForm", () => {
  let onSubmit: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSubmit = vi.fn();
  });

  it("renders name, slug, base_url, description, and transport fields", () => {
    render(<ServerConfigForm onSubmit={onSubmit} />);
    expect(screen.getByLabelText(/server name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/server slug/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/base url/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/transport mode/i)).toBeInTheDocument();
  });

  it("auto-derives slug from name", async () => {
    const user = userEvent.setup();
    render(<ServerConfigForm onSubmit={onSubmit} />);
    await user.type(screen.getByLabelText(/server name/i), "My API Server");
    await waitFor(() => {
      const slugInput = screen.getByLabelText(/server slug/i) as HTMLInputElement;
      expect(slugInput.value).toBe("my-api-server");
    });
  });

  it("locks auto-derivation when slug is manually edited", async () => {
    const user = userEvent.setup();
    render(<ServerConfigForm onSubmit={onSubmit} />);
    const slugInput = screen.getByLabelText(/server slug/i);
    await user.type(slugInput, "custom-slug");
    await user.type(screen.getByLabelText(/server name/i), "My API");
    await waitFor(() => {
      expect((slugInput as HTMLInputElement).value).toBe("custom-slug");
    });
  });

  it("shows validation errors for empty required fields", async () => {
    const user = userEvent.setup();
    render(<ServerConfigForm onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: /save and continue/i }));
    await waitFor(() => {
      expect(screen.getByText("Server name is required")).toBeInTheDocument();
      expect(screen.getByText("Base URL is required")).toBeInTheDocument();
    });
  });

  it("calls onSubmit when form is valid after filling all fields", async () => {
    const user = userEvent.setup();
    render(<ServerConfigForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/server name/i), "My API");
    await user.type(
      screen.getByLabelText(/base url/i),
      "https://api.example.com",
    );

    const submitBtn = screen.getByRole("button", { name: /save and continue/i });
    expect(submitBtn).not.toBeDisabled();
    await user.click(submitBtn);

    await waitFor(
      () => {
        expect(onSubmit).toHaveBeenCalledOnce();
      },
      { timeout: 5000 },
    );
  });

  it("disables submit button when isSubmitting is true", () => {
    render(<ServerConfigForm onSubmit={onSubmit} isSubmitting />);
    expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled();
    expect(screen.getByText("Saving...")).toBeInTheDocument();
  });
});
