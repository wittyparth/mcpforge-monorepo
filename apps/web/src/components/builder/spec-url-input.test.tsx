import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SpecUrlInput } from "./spec-url-input";
import type { SpecUploadResponse } from "@/types/api";

const mockUploadResponse: SpecUploadResponse = {
  spec_id: "spec-1",
  title: "Petstore API",
  version: "1.0.0",
  openapi_version: "3.0.3",
  endpoint_count: 12,
  spec_size_bytes: 4096,
  tools: [],
};

const mockMutateAsync = vi.fn().mockResolvedValue(mockUploadResponse);

vi.mock("@/hooks/use-spec", () => ({
  useFetchSpec: () => ({
    mutate: vi.fn(),
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
}));

describe("SpecUrlInput", () => {
  beforeEach(() => {
    mockMutateAsync.mockReset();
    mockMutateAsync.mockResolvedValue(mockUploadResponse);
  });

  it("renders the URL input field", () => {
    render(<SpecUrlInput onSuccess={vi.fn()} />);
    expect(
      screen.getByLabelText("OpenAPI Spec URL"),
    ).toBeInTheDocument();
  });

  it("calls mutateAsync and onSuccess on valid URL submission", async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<SpecUrlInput onSuccess={onSuccess} />);

    await user.type(
      screen.getByLabelText("OpenAPI Spec URL"),
      "https://api.example.com/openapi.json",
    );
    await user.click(screen.getByRole("button", { name: /fetch spec/i }));

    expect(mockMutateAsync).toHaveBeenCalledOnce();
    expect(mockMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ url: "https://api.example.com/openapi.json" }),
    );
    expect(onSuccess).toHaveBeenCalledWith(mockUploadResponse);
  });

  it("calls onError with the error message when fetch fails", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Network timeout"));
    const onError = vi.fn();
    const user = userEvent.setup();
    render(<SpecUrlInput onSuccess={vi.fn()} onError={onError} />);

    await user.type(
      screen.getByLabelText("OpenAPI Spec URL"),
      "https://api.example.com/openapi.json",
    );
    await user.click(screen.getByRole("button", { name: /fetch spec/i }));

    expect(onError).toHaveBeenCalledWith("Network timeout");
  });

  it("shows custom headers section when toggled", async () => {
    const user = userEvent.setup();
    render(<SpecUrlInput onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /headers/i }));

    expect(screen.getByText(/no custom headers/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add header/i })).toBeInTheDocument();
  });
});
