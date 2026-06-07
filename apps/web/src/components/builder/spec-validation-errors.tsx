"use client";

import * as React from "react";
import { AlertCircle, ChevronDown, ChevronUp } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import type { SpecValidationError } from "@/types/api";

interface SpecValidationErrorsProps {
  /** The top-level error message, or null to hide */
  error: string | null;
  /** Optional structured validation error details */
  details?: SpecValidationError[];
  className?: string;
}

/**
 * Displays spec validation errors in a destructive Alert.
 * Collapses to 5 items if there are more, with a "Show all" toggle.
 */
const SpecValidationErrors = React.forwardRef<
  HTMLDivElement,
  SpecValidationErrorsProps
>(({ error, details, className }, ref) => {
  const [showAll, setShowAll] = React.useState(false);

  if (!error) {
    return null;
  }

  const hasManyDetails = details && details.length > 5;
  const visibleDetails =
    hasManyDetails && !showAll ? details.slice(0, 5) : details;

  return (
    <Alert
      variant="destructive"
      ref={ref}
      className={cn("", className)}
    >
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Couldn&apos;t parse this spec</AlertTitle>
      <AlertDescription>
        <p className="mt-1 text-sm">{error}</p>
        {visibleDetails && visibleDetails.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {visibleDetails.map((detail, idx) => (
              <li key={idx} className="text-xs leading-relaxed">
                <code className="rounded bg-destructive/10 px-1 py-0.5 font-mono text-xs">
                  {detail.path}
                </code>
                <span className="text-destructive/90">
                  : {detail.message}
                </span>
                {(detail.line != null || detail.column != null) && (
                  <span className="text-destructive/70">
                    {" "}
                    (Line {detail.line}
                    {detail.column != null ? `, column ${detail.column}` : ""})
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        {hasManyDetails && (
          <button
            type="button"
            onClick={() => setShowAll((prev) => !prev)}
            className="mt-2 flex items-center gap-1 text-xs font-medium text-destructive hover:text-destructive/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            {showAll ? (
              <>
                Show less
                <ChevronUp className="h-3 w-3" />
              </>
            ) : (
              <>
                Show all {details!.length} errors
                <ChevronDown className="h-3 w-3" />
              </>
            )}
          </button>
        )}
      </AlertDescription>
    </Alert>
  );
});
SpecValidationErrors.displayName = "SpecValidationErrors";

export { SpecValidationErrors };
export type { SpecValidationErrorsProps };
