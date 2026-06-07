"use client";

import * as React from "react";
import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/** Human-readable labels for known warning codes. */
const WARNING_LABELS: Record<string, string> = {
  missing_operation_id:
    "Tool name was auto-generated from path (no operationId provided)",
  no_description:
    "Missing description. LLM selection will be less accurate.",
  untagged: "Not in any tag group",
};

function getWarningLabel(warning: string): string {
  return WARNING_LABELS[warning] ?? warning;
}

export interface ToolWarningsProps {
  /** Warning codes to display. */
  warnings: string[];
  /**
   * Visual size variant.
   * @default "default"
   */
  size?: "sm" | "default";
}

const ToolWarnings = React.forwardRef<HTMLDivElement, ToolWarningsProps>(
  ({ warnings, size = "default" }, ref) => {
    if (warnings.length === 0) return null;

    return (
      <div ref={ref} className="inline-flex items-center">
        <Popover>
          <Tooltip>
            <TooltipTrigger asChild>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "relative text-yellow-600 hover:text-yellow-700 dark:text-yellow-400 dark:hover:text-yellow-300",
                    "hover:bg-yellow-500/10",
                    "focus-visible:ring-yellow-500/50",
                    size === "sm" ? "h-6 w-6" : "h-7 w-7",
                  )}
                  aria-label={`${warnings.length} warning${warnings.length !== 1 ? "s" : ""}`}
                >
                  <AlertTriangle
                    className={cn(
                      "animate-[pulse_3s_ease-in-out_infinite]",
                      size === "sm" ? "h-3 w-3" : "h-4 w-4",
                    )}
                  />
                  {warnings.length > 1 && (
                    <span
                      className={cn(
                        "absolute -right-1 -top-1 flex items-center justify-center",
                        "rounded-full bg-yellow-500 px-1 text-[9px] font-bold leading-none text-white",
                        "h-3.5 min-w-[14px]",
                      )}
                      aria-hidden="true"
                    >
                      {warnings.length}
                    </span>
                  )}
                </Button>
              </PopoverTrigger>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>
                {warnings.length} issue{warnings.length !== 1 ? "s" : ""}
              </p>
            </TooltipContent>
          </Tooltip>

          <PopoverContent side="bottom" align="end" className="w-72 p-3">
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Issues
              </p>
              <ul className="space-y-1.5">
                {warnings.map((warning, i) => (
                  <li
                    key={`${warning}-${i}`}
                    className="flex items-start gap-2 text-sm"
                  >
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-600 dark:text-yellow-400" />
                    <span>{getWarningLabel(warning)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </PopoverContent>
        </Popover>
      </div>
    );
  },
);
ToolWarnings.displayName = "ToolWarnings";

export { ToolWarnings, getWarningLabel };
