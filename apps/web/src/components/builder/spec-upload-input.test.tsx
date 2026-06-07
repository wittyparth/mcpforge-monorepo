import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SpecUploadInput } from "./spec-upload-input";
import type { SpecUploadResponse } from "@/types/api";

const mockUploadResponse: SpecUploadResponse = {
  spec_id: "spec-2",
  title: "Uploaded API",
  version: "2.0.0",
  openapi_version: "3.1.0",
  endpoint_count: 8,
  spec_size_bytes: 1024,
  tools: [],
};

const mockMutateAsync = vi.fn().mockResolvedValue(mockUploadResponse);

vi.mock("@/hooks/use-spec", () => ({
  useUploadSpec: () => ({
    mutate: vi.fn(),
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
}));

describe("SpecUploadInput", () => {
  beforeEach(() => {
    mockMutateAsync.mockReset();
    mockMutateAsync.mockResolvedValue(mockUploadResponse);
  });

  it("renders the drop zone and browse button", () => {
    render(<SpecUploadInput onSuccess={vi.fn()} />);
    expect(
      screen.getByText(/drop your openapi spec/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /browse files/i }),
    ).toBeInTheDocument();
  });

  it("calls mutateAsync and onSuccess on file selection", async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    const { container } = render(
      <SpecUploadInput onSuccess={onSuccess} />,
    );

    const file = new File(
      ["openapi: 3.0.0"],
      "spec.yaml",
      { type: "text/yaml" },
    );
    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(fileInput, file);

    expect(mockMutateAsync).toHaveBeenCalledOnce();
    expect(mockMutateAsync).toHaveBeenCalledWith(file);
    expect(onSuccess).toHaveBeenCalledWith(mockUploadResponse);
  });

  it("calls onError with the error message when upload fails", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Upload rejected"));
    const onError = vi.fn();
    const user = userEvent.setup();
    const { container } = render(
      <SpecUploadInput onSuccess={vi.fn()} onError={onError} />,
    );

    const file = new File(
      ["{}"],
      "spec.json",
      { type: "application/json" },
    );
    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(fileInput, file);

    expect(onError).toHaveBeenCalledWith("Upload rejected");
  });

  it("shows a file preview after selection", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <SpecUploadInput onSuccess={vi.fn()} />,
    );

    const file = new File(
      ["data"],
      "openapi.json",
      { type: "application/json" },
    );
    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    await user.upload(fileInput, file);

    expect(screen.getByText("openapi.json")).toBeInTheDocument();
  });
});
