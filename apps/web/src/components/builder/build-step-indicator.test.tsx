import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BuildStepIndicator } from "./build-step-indicator";

describe("BuildStepIndicator", () => {
  it("renders all 4 stage labels", () => {
    render(<BuildStepIndicator />);
    expect(screen.getByText("Parsing")).toBeInTheDocument();
    expect(screen.getByText("AI Enhancement")).toBeInTheDocument();
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("highlights in-progress stage for parsing", () => {
    render(<BuildStepIndicator currentStage="parsing" />);
    // Parsing should be in-progress (pulse animation indicates this)
    const parsingStep = screen.getByText("Parsing");
    expect(parsingStep).toHaveClass("text-primary");
    expect(parsingStep).toHaveClass("font-semibold");
  });

  it("marks earlier stages as complete when a later stage is active", () => {
    render(<BuildStepIndicator currentStage="deploying" />);
    const parsingStep = screen.getByText("Parsing");
    const aiStep = screen.getByText("AI Enhancement");
    const securityStep = screen.getByText("Security");
    // Parsing, AI Enhancement, and Security should be complete (emerald)
    expect(parsingStep).toHaveClass("text-emerald-600");
    expect(aiStep).toHaveClass("text-emerald-600");
    expect(securityStep).toHaveClass("text-emerald-600");
    // Ready should be in-progress
    const readyStep = screen.getByText("Ready");
    expect(readyStep).toHaveClass("text-primary");
  });

  it("renders all steps dimmed when no currentStage", () => {
    render(<BuildStepIndicator />);
    const steps = ["Parsing", "AI Enhancement", "Security", "Ready"];
    for (const label of steps) {
      const step = screen.getByText(label);
      expect(step).toHaveClass("text-muted-foreground/50");
    }
  });

  it("renders error state on the active step", () => {
    render(<BuildStepIndicator currentStage="error" />);
    // When error happens before parsing starts, no step is marked as error
    // All should be upcoming
    const parsingStep = screen.getByText("Parsing");
    expect(parsingStep).toHaveClass("text-muted-foreground/50");
  });

  it("marks step as error when error occurs during generating", () => {
    // Mount with generating first, then error
    const { rerender } = render(
      <BuildStepIndicator currentStage="generating" />,
    );
    rerender(<BuildStepIndicator currentStage="error" />);
    // Parsing should be complete, AI Enhancement should be error
    expect(screen.getByText("Parsing")).toHaveClass("text-emerald-600");
    expect(screen.getByText("AI Enhancement")).toHaveClass("text-destructive");
  });

  it("renders all steps complete when currentStage is complete", () => {
    render(<BuildStepIndicator currentStage="complete" />);
    const steps = ["Parsing", "AI Enhancement", "Security", "Ready"];
    for (const label of steps) {
      expect(screen.getByText(label)).toHaveClass("text-emerald-600");
    }
  });
});
