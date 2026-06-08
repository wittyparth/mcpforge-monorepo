"use client";

import * as React from "react";
import { Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AIImprovementItem } from "@/types/api";

export interface ImprovementsBadgesProps {
  /** List of improvements suggested by the AI engine. */
  improvements: AIImprovementItem[];
  /** Called when a user clicks on an improvement badge to view details. */
  onExpand?: (improvement: AIImprovementItem) => void;
  /** Maximum number of badges to show before a "+N more" overflow. */
  maxVisible?: number;
  /** Optional size variant. */
  size?: "sm" | "default";
}

/**
 * Renders a list of AI improvement suggestions as compact, clickable badges.
 *
 * Each badge shows the field name that was improved. When the list exceeds
 * `maxVisible`, a "+N more" badge is appended. Clicking a badge optionally
 * triggers `onExpand` with the full improvement details.
 */
const ImprovementsBadges = React.forwardRef<HTMLDivElement, ImprovementsBadgesProps>(
  ({ improvements, onExpand, maxVisible = 5, size = "sm" }, ref) => {
    const [showAll, setShowAll] = React.useState(false);

    if (improvements.length === 0) return null;

    const visible = showAll ? improvements : improvements.slice(0, maxVisible);
    const overflow = showAll ? 0 : improvements.length - maxVisible;

    return (
      <div ref={ref} className="flex flex-wrap gap-1.5">
        {visible.map((item, idx) => (
          <button
            key={`${item.field}-${idx}`}
            type="button"
            onClick={() => onExpand?.(item)}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border bg-orange-500/5 border-orange-500/20",
              "text-orange-700 dark:text-orange-400",
              "transition-colors hover:bg-orange-500/10",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/30 focus-visible:ring-offset-1",
              size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-[11px]",
            )}
          >
            <Wand2 className="shrink-0" style={{ width: size === "sm" ? 10 : 12, height: size === "sm" ? 10 : 12 }} />
            <span className="truncate font-medium">{item.field}</span>
          </button>
        ))}

        {overflow > 0 && (
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className={cn(
              "inline-flex items-center rounded-md border border-dashed border-muted-foreground/30",
              "text-muted-foreground transition-colors hover:bg-muted/50",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
              size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-[11px]",
            )}
          >
            +{overflow} more
          </button>
        )}
      </div>
    );
  },
);
ImprovementsBadges.displayName = "ImprovementsBadges";

export { ImprovementsBadges };
