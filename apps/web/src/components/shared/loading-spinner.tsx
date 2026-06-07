import * as React from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

const spinnerSizeMap = {
  sm: "h-3 w-3",
  default: "h-4 w-4",
  lg: "h-6 w-6",
} as const;

export interface LoadingSpinnerProps
  extends React.HTMLAttributes<HTMLDivElement> {
  /** Size variant for the spinner icon. */
  size?: keyof typeof spinnerSizeMap;
  /** Optional label rendered inline next to the spinner (e.g. "Loading..."). */
  label?: string;
}

/**
 * An accessible loading spinner with configurable size and an optional
 * inline label.
 *
 * Uses Lucide's `Loader2` icon with a CSS spin animation. The default
 * colour is `text-muted-foreground` and can be overridden via `className`.
 */
const LoadingSpinner = React.forwardRef<HTMLDivElement, LoadingSpinnerProps>(
  ({ size = "default", label, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="status"
        aria-label="Loading"
        className={cn(
          "inline-flex items-center gap-2 text-muted-foreground",
          className,
        )}
        {...props}
      >
        <Loader2
          className={cn("animate-spin", spinnerSizeMap[size])}
          aria-hidden="true"
        />
        {label && (
          <span className="text-sm">{label}</span>
        )}
      </div>
    );
  },
);
LoadingSpinner.displayName = "LoadingSpinner";

export { LoadingSpinner, spinnerSizeMap };
