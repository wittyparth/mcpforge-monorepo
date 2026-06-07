import * as React from "react";

import { cn } from "@/lib/utils";
import type { HttpMethod } from "@/types/api";

/**
 * Maps an HTTP method to Tailwind color classes for a subtle pill badge.
 *
 * Returns a tuple of [containerClasses, dotClasses].
 */
function getHttpMethodColors(method: HttpMethod): [string, string] {
  switch (method) {
    case "GET":
      return [
        "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-emerald-500/20",
        "bg-emerald-500",
      ];
    case "POST":
      return [
        "bg-blue-500/10 text-blue-700 dark:text-blue-300 ring-blue-500/20",
        "bg-blue-500",
      ];
    case "PUT":
      return [
        "bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-amber-500/20",
        "bg-amber-500",
      ];
    case "PATCH":
      return [
        "bg-yellow-500/10 text-yellow-700 dark:text-yellow-300 ring-yellow-500/20",
        "bg-yellow-500",
      ];
    case "DELETE":
      return [
        "bg-red-500/10 text-red-700 dark:text-red-300 ring-red-500/20",
        "bg-red-500",
      ];
    case "HEAD":
    case "OPTIONS":
      return [
        "bg-zinc-500/10 text-zinc-700 dark:text-zinc-300 ring-zinc-500/20",
        "bg-zinc-500",
      ];
  }
}

export interface HttpMethodBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  /** The HTTP method to display. */
  method: HttpMethod;
}

/**
 * A compact, color-coded pill badge for HTTP methods.
 *
 * Renders a small monospace label (e.g. "GET", "POST") with a
 * semantic color scheme and a colored dot prefix. Designed to fit
 * inline with surrounding text.
 */
const HttpMethodBadge = React.forwardRef<HTMLSpanElement, HttpMethodBadgeProps>(
  ({ method, className, ...props }, ref) => {
    const [containerClasses, dotClasses] = getHttpMethodColors(method);

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
        {method}
      </span>
    );
  },
);
HttpMethodBadge.displayName = "HttpMethodBadge";

export { HttpMethodBadge, getHttpMethodColors };
