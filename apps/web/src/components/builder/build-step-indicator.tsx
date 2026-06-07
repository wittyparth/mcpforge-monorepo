"use client";

import * as React from "react";
import {
  Check,
  FileSearch,
  Rocket,
  Shield,
  Sparkles,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { BuildStage } from "@/types/api";

interface BuildStep {
  label: string;
  icon: React.ElementType;
}

const STEPS: BuildStep[] = [
  { label: "Parsing", icon: FileSearch },
  { label: "AI Enhancement", icon: Sparkles },
  { label: "Security", icon: Shield },
  { label: "Ready", icon: Rocket },
];

type StepState = "upcoming" | "in-progress" | "complete" | "error";

/**
 * Determine the state of each step given the current build stage.
 *
 * Stage-to-step mapping:
 *   parsing    → step 0 in-progress
 *   generating → step 1 in-progress (step 0 complete)
 *   testing    → step 2 in-progress (steps 0-1 complete)
 *   deploying  → step 3 in-progress (steps 0-2 complete)
 *   complete   → all steps complete
 *   error      → the previously-active step turns red
 */
function getStepState(
  stepIndex: number,
  currentStage: BuildStage | undefined,
  lastNonErrorStage: BuildStage | undefined,
): StepState {
  if (!currentStage) return "upcoming";

  // Error state: mark the step that was active when error occurred
  if (currentStage === "error") {
    const effective = lastNonErrorStage;
    if (!effective) return "upcoming";
    const activeStep = stageToActiveStep(effective);
    if (stepIndex < activeStep) return "complete";
    if (stepIndex === activeStep) return "error";
    return "upcoming";
  }

  const activeStep = stageToActiveStep(currentStage);
  if (stepIndex < activeStep) return "complete";
  if (stepIndex === activeStep) return "in-progress";
  return "upcoming";
}

/** Map a build stage to the 0-based step index that is active. */
function stageToActiveStep(stage: BuildStage): number {
  switch (stage) {
    case "parsing":
      return 0;
    case "generating":
      return 1;
    case "testing":
      return 2;
    case "deploying":
      return 3;
    case "complete":
      return 4; // past all steps
    case "error":
      return -1; // handled separately
  }
}

interface BuildStepIndicatorProps {
  /** Current build pipeline stage */
  currentStage?: BuildStage;
  className?: string;
}

/**
 * A 4-step horizontal stepper showing build pipeline progress.
 *
 * Each step has an icon in a circle, a label below, and a connecting
 * line to the next step. States include upcoming, in-progress (pulsing),
 * complete (green checkmark), and error (red X).
 */
const BuildStepIndicator = React.forwardRef<
  HTMLDivElement,
  BuildStepIndicatorProps
>(({ currentStage, className }, ref) => {
  // Track the last non-error stage so we can show which step errored
  const lastNonErrorRef = React.useRef<BuildStage | undefined>(undefined);

  React.useEffect(() => {
    if (currentStage && currentStage !== "error") {
      lastNonErrorRef.current = currentStage;
    }
  }, [currentStage]);

  return (
    <div
      ref={ref}
      className={cn("flex items-start justify-center gap-0", className)}
    >
      {STEPS.map((step, index) => {
        const state = getStepState(
          index,
          currentStage,
          lastNonErrorRef.current,
        );
        const Icon =
          state === "complete"
            ? Check
            : state === "error"
              ? X
              : step.icon;
        const isLast = index === STEPS.length - 1;

        return (
          <React.Fragment key={step.label}>
            {/* Step circle + label */}
            <div className="flex flex-col items-center gap-2">
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all duration-300",
                  state === "complete" &&
                    "border-emerald-500 bg-emerald-500 text-white",
                  state === "in-progress" &&
                    "border-primary bg-primary/10 text-primary animate-pulse",
                  state === "error" &&
                    "border-destructive bg-destructive/10 text-destructive",
                  state === "upcoming" &&
                    "border-muted-foreground/30 text-muted-foreground/50 bg-transparent",
                )}
              >
                <Icon
                  className={cn(
                    "h-5 w-5 transition-all duration-300",
                    state === "complete" && "h-5 w-5",
                    state === "in-progress" && "h-5 w-5",
                    state === "error" && "h-5 w-5",
                    state === "upcoming" && "h-4 w-4",
                  )}
                />
              </div>
              <span
                className={cn(
                  "text-xs font-medium transition-colors duration-200 text-center max-w-[80px] leading-tight",
                  state === "complete" && "text-emerald-600 dark:text-emerald-400",
                  state === "in-progress" && "text-primary font-semibold",
                  state === "error" && "text-destructive",
                  state === "upcoming" && "text-muted-foreground/50",
                )}
              >
                {step.label}
              </span>
            </div>

            {/* Connecting line */}
            {!isLast && (
              <div className="flex items-center pt-5 px-2">
                <div
                  className={cn(
                    "h-0.5 w-12 sm:w-16 transition-colors duration-300 rounded-full",
                    state === "complete"
                      ? "bg-emerald-500"
                      : "bg-muted-foreground/20",
                  )}
                />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
});
BuildStepIndicator.displayName = "BuildStepIndicator";

export { BuildStepIndicator };
export type { BuildStepIndicatorProps };
