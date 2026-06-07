import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CopyToClipboard } from "./copy-to-clipboard";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));
import { toast } from "sonner";

describe("CopyToClipboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a copy button with an accessible label", () => {
    render(<CopyToClipboard value="abc-123" />);
    const button = screen.getByRole("button", {
      name: /copy value to clipboard/i,
    });
    expect(button).toBeInTheDocument();
  });

  it("copies text and shows a success toast on click", async () => {
    const user = userEvent.setup();
    render(<CopyToClipboard value="secret-token" />);

    await user.click(screen.getByRole("button"));

    expect(toast.success).toHaveBeenCalledWith("Copied to clipboard");
  });

  it("shows a success toast with custom label", async () => {
    const user = userEvent.setup();
    render(<CopyToClipboard value="xyz" label="API key" />);

    await user.click(screen.getByRole("button"));

    expect(toast.success).toHaveBeenCalledWith("Copied API key");
  });

  it("shows an error toast when clipboard write fails", async () => {
    const origWrite = window.navigator.clipboard?.writeText;
    const writeStub = vi.fn().mockRejectedValue(new Error("denied"));
    try {
      if (window.navigator.clipboard) {
        window.navigator.clipboard.writeText = writeStub as (
          text: string,
        ) => Promise<void>;
      }

      const user = userEvent.setup();
      render(<CopyToClipboard value="test" />);
      await user.click(screen.getByRole("button"));
    } finally {
      if (window.navigator.clipboard && origWrite) {
        window.navigator.clipboard.writeText = origWrite;
      }
    }

    expect(toast.error).toHaveBeenCalledWith("Failed to copy");
  });
});
