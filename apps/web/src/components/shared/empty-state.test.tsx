import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/button";
import { EmptyState } from "./empty-state";

describe("EmptyState", () => {
  it("renders the title", () => {
    render(<EmptyState title="No servers found" />);
    expect(screen.getByText("No servers found")).toBeInTheDocument();
  });

  it("renders the description when provided", () => {
    render(
      <EmptyState
        title="Empty"
        description="Create your first server to get started"
      />,
    );
    expect(
      screen.getByText("Create your first server to get started"),
    ).toBeInTheDocument();
  });

  it("does not render a description when not provided", () => {
    const { container } = render(<EmptyState title="Empty" />);
    // The only <p> in the default EmptyState is for description; without it there is none
    expect(container.querySelector("p")).not.toBeInTheDocument();
  });

  it("renders an action button and fires onClick when clicked", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();

    render(
      <EmptyState
        title="Empty"
        action={<Button onClick={onClick}>Add Item</Button>}
      />,
    );

    await user.click(screen.getByRole("button", { name: /add item/i }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders an svg icon by default", () => {
    const { container } = render(<EmptyState title="Test" />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });
});
