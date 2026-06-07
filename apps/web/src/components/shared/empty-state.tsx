import * as React from "react";
import { Inbox, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Optional icon to render above the title. Defaults to a muted Inbox icon. */
  icon?: LucideIcon;
  /** Heading text for the empty state. */
  title: string;
  /** Optional supporting description shown below the title. */
  description?: string;
  /** Optional action element (e.g. a button or link) shown below the description. */
  action?: React.ReactNode;
}

/**
 * A centered empty-state placeholder used when a list, search result,
 * or dashboard section has no data to display.
 *
 * Renders an optional icon, a title, an optional description, and an
 * optional call-to-action element. Defaults to a subtle Inbox icon if
 * none is provided.
 */
const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  ({ icon: Icon = Inbox, title, description, action, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex flex-col items-center justify-center gap-3 py-12 text-center",
          className,
        )}
        {...props}
      >
        <div className="text-muted-foreground/50" aria-hidden="true">
          <Icon className="h-12 w-12" strokeWidth={1.5} />
        </div>
        <div className="flex flex-col items-center gap-1">
          <h3 className="text-lg font-medium">{title}</h3>
          {description && (
            <p className="max-w-md text-sm text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        {action && <div className="mt-1">{action}</div>}
      </div>
    );
  },
);
EmptyState.displayName = "EmptyState";

export { EmptyState };
