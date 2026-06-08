"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface QualityScoreBreakdownProps {
  /** Functionality score (0–100). */
  functionality: number;
  /** Accuracy score (0–100). */
  accuracy: number;
  /** Completeness score (0–100). */
  completeness: number;
  /** Context score (0–100). */
  context: number;
  /** Optional size variant. */
  size?: "sm" | "default";
}

interface Dimension {
  key: string;
  label: string;
  value: number;
  color: string;
}

/**
 * Horizontal bar chart showing four quality dimensions.
 *
 * Each dimension fills a bar proportionally (0–100%) with a distinct
 * color that stays readable in light and dark modes.
 */
const QualityScoreBreakdown = React.forwardRef<HTMLDivElement, QualityScoreBreakdownProps>(
  ({ functionality, accuracy, completeness, context, size = "default" }, ref) => {
    const dimensions: Dimension[] = [
      {
        key: "functionality",
        label: "Functionality",
        value: functionality,
        color: "bg-blue-500",
      },
      {
        key: "accuracy",
        label: "Accuracy",
        value: accuracy,
        color: "bg-emerald-500",
      },
      {
        key: "completeness",
        label: "Completeness",
        value: completeness,
        color: "bg-violet-500",
      },
      {
        key: "context",
        label: "Context",
        value: context,
        color: "bg-amber-500",
      },
    ];

    return (
      <div ref={ref} className="space-y-2">
        {dimensions.map((dim) => (
          <div key={dim.key} className="flex items-center gap-3">
            <span
              className={cn(
                "shrink-0 font-medium text-muted-foreground",
                size === "sm" ? "w-20 text-[11px]" : "w-24 text-xs",
              )}
            >
              {dim.label}
            </span>
            <div
              className={cn(
                "relative flex-1 overflow-hidden rounded-full bg-muted",
                size === "sm" ? "h-1.5" : "h-2",
              )}
            >
              <div
                className={cn(
                  "absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out",
                  dim.color,
                )}
                style={{ width: `${Math.min(100, Math.max(0, dim.value))}%` }}
              />
            </div>
            <span
              className={cn(
                "shrink-0 font-mono tabular-nums text-muted-foreground",
                size === "sm" ? "w-8 text-[11px] text-right" : "w-8 text-xs text-right",
              )}
            >
              {dim.value}
            </span>
          </div>
        ))}
      </div>
    );
  },
);
QualityScoreBreakdown.displayName = "QualityScoreBreakdown";

export { QualityScoreBreakdown };
