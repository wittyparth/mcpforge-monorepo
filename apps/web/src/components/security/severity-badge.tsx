"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import type { FindingSeverity } from "@/types/api";

/**
 * Maps a finding severity to Tailwind color classes for a compact pill badge.
 *
 * Returns a tuple of [containerClasses, dotClasses].
 */
function getSeverityColors(
  severity: FindingSeverity,
): [string, string] {
  switch (severity) {
    case "critical":
      return [
        "bg-red-500/10 text-red-700 dark:text-red-300 ring-red-500/20",
        "bg-red-500",
      ];
    case "high":
      return [
        "bg-orange-500/10 text-orange-700 dark:text-orange-300 ring-orange-500/20",
        "bg-orange-500",
      ];
    case "medium":
      return [
        "bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-amber-500/20",
        "bg-amber-500",
      ];
    case "info":
      return [
        "bg-blue-500/10 text-blue-700 dark:text-blue-300 ring-blue-500/20",
        "bg-blue-500",
      ];
  }
}

export interface SeverityBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  /** The finding severity level to display. */
  severity: FindingSeverity;
}

/**
 * A compact, color-coded pill badge for security finding severities.
 *
 * Renders a small uppercase label (e.g. "CRITICAL", "HIGH") with a
 * semantic color scheme and a colored dot prefix. Designed to fit
 * inline with surrounding text.
 */
const SeverityBadge = React.forwardRef<HTMLSpanElement, SeverityBadgeProps>(
  ({ severity, className, ...props }, ref) => {
    const [containerClasses, dotClasses] = getSeverityColors(severity);

    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center gap-1 rounded px-1.5 py-0.5",
          "font-mono text-[10px] font-semibold uppercase tracking-wider",
          "ring-1 ring-inset",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          containerClasses,
          className,
        )}
        {...props}
      >
        <span
          className={cn("h-1.5 w-1.5 rounded-full", dotClasses)}
          aria-hidden="true"
        />
        {severity}
      </span>
    );
  },
);
SeverityBadge.displayName = "SeverityBadge";

export { SeverityBadge, getSeverityColors };
