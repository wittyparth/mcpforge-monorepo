import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SpecInput } from "./spec-input";
import type { SpecUploadResponse } from "@/types/api";

const mockUploadResponse: SpecUploadResponse = {
  spec_id: "spec-1",
  title: "Test API",
  version: "1.0.0",
  openapi_version: "3.0.0",
  endpoint_count: 5,
  spec_size_bytes: 2048,
  tools: [],
};

const mockMutateAsync = vi.fn().mockResolvedValue(mockUploadResponse);

vi.mock("@/hooks/use-spec", () => ({
  useFetchSpec: () => ({
    mutate: vi.fn(),
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
  useUploadSpec: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn().mockResolvedValue(mockUploadResponse),
    isPending: false,
  }),
}));

describe("SpecInput", () => {
  beforeEach(() => {
    mockMutateAsync.mockReset();
    mockMutateAsync.mockResolvedValue(mockUploadResponse);
  });

  it("renders the card title and description", () => {
    render(<SpecInput onSuccess={vi.fn()} />);
    expect(screen.getByText("Import OpenAPI Spec")).toBeInTheDocument();
    expect(screen.getByText(/provide an openapi/i)).toBeInTheDocument();
  });

  it("renders both tab triggers", () => {
    render(<SpecInput onSuccess={vi.fn()} />);
    expect(
      screen.getByRole("tab", { name: /from url/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /upload file/i }),
    ).toBeInTheDocument();
  });

  it("shows the URL form by default", () => {
    render(<SpecInput onSuccess={vi.fn()} />);
    expect(
      screen.getByLabelText("OpenAPI Spec URL"),
    ).toBeInTheDocument();
  });

  it("switches to the upload tab and shows upload content", async () => {
    const user = userEvent.setup();
    render(<SpecInput onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("tab", { name: /upload file/i }));

    expect(screen.getByText(/drop your openapi spec/i)).toBeInTheDocument();
  });
});
