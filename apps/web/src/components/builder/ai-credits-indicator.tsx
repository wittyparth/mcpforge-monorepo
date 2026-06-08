"use client";

import * as React from "react";
import { Coins, Infinity } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AiCreditsIndicatorProps {
  /** Number of credits remaining, or null for unlimited. */
  remaining: number | null;
  /** The user's subscription plan name (e.g., "free", "pro"). */
  plan: string;
  /** Optional size variant. */
  size?: "sm" | "default";
}

/**
 * Shows remaining AI enhancement credits based on the user's plan.
 *
 * Free plan users see a numeric count ("12 remaining this month").
 * Pro/Enterprise users see "Unlimited". The component is purely
 * presentational — no API calls.
 */
const AiCreditsIndicator = React.forwardRef<HTMLDivElement, AiCreditsIndicatorProps>(
  ({ remaining, plan, size = "default" }, ref) => {
    const isUnlimited = remaining === null || plan !== "free";

    return (
      <div
        ref={ref}
        className={cn(
          "inline-flex items-center gap-1.5 text-muted-foreground",
          size === "sm" ? "text-[11px]" : "text-xs",
        )}
      >
        {isUnlimited ? (
          <>
            <Infinity className="shrink-0 opacity-50" style={{ width: size === "sm" ? 10 : 12, height: size === "sm" ? 10 : 12 }} />
            <span>Unlimited</span>
          </>
        ) : (
          <>
            <Coins className="shrink-0 opacity-50" style={{ width: size === "sm" ? 10 : 12, height: size === "sm" ? 10 : 12 }} />
            <span>
              <span className="font-mono tabular-nums font-medium text-foreground">
                {remaining}
              </span>{" "}
              remaining this month
            </span>
          </>
        )}
      </div>
    );
  },
);
AiCreditsIndicator.displayName = "AiCreditsIndicator";

export { AiCreditsIndicator };
