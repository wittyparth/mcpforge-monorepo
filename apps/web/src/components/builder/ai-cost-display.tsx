"use client";

import * as React from "react";
import { DollarSign } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AiCostDisplayProps {
  /** Cost in cents (e.g., 4 means $0.04). */
  costCents: number;
  /** Whether this is an estimated cost (vs. actual). */
  estimated?: boolean;
  /** Optional size variant. */
  size?: "sm" | "default";
}

/**
 * Displays a cost value formatted as US dollars.
 *
 * Converts cents to dollars and renders in a compact, monospaced style.
 * When `estimated` is true, a subtle "~" prefix indicates the value is
 * approximate.
 */
const AiCostDisplay = React.forwardRef<HTMLDivElement, AiCostDisplayProps>(
  ({ costCents, estimated = false, size = "default" }, ref) => {
    const dollars = (costCents / 100).toFixed(2);

    return (
      <div
        ref={ref}
        className={cn(
          "inline-flex items-center gap-1 font-mono tabular-nums",
          "text-muted-foreground",
          size === "sm" ? "text-[11px]" : "text-xs",
        )}
      >
        <DollarSign className="shrink-0 opacity-50" style={{ width: size === "sm" ? 10 : 12, height: size === "sm" ? 10 : 12 }} />
        <span>
          {estimated && <span className="mr-px opacity-50">~</span>}
          {dollars}
        </span>
      </div>
    );
  },
);
AiCostDisplay.displayName = "AiCostDisplay";

export { AiCostDisplay };
