"use client";

import * as React from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface OriginalVsEnhancedProps {
  /** The original text. */
  original: string;
  /** The AI-enhanced text. */
  enhanced: string;
  /** Optional title shown above the comparison. */
  title?: string;
}

/**
 * Side-by-side comparison panel for original vs. AI-enhanced text.
 *
 * Left panel shows the original content with a neutral/gray tint.
 * Right panel shows the enhanced content with a green tint. An arrow
 * separator sits between them. Both panels scroll independently
 * on overflow.
 */
const OriginalVsEnhanced = React.forwardRef<HTMLDivElement, OriginalVsEnhancedProps>(
  ({ original, enhanced, title }, ref) => {
    return (
      <div ref={ref} className="space-y-2">
        {title && (
          <h4 className="text-xs font-medium text-muted-foreground">
            {title}
          </h4>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_1fr]">
          {/* ── Original ── */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
              Original
            </span>
            <div
              className={cn(
                "max-h-40 overflow-y-auto rounded-md border border-border/50 bg-muted/30 p-3",
                "whitespace-pre-wrap break-words text-xs leading-relaxed text-muted-foreground",
              )}
            >
              {original || <span className="italic">No description</span>}
            </div>
          </div>

          {/* ── Arrow ── */}
          <div className="hidden items-center justify-center sm:flex">
            <ArrowRight className="h-4 w-4 text-muted-foreground/40" />
          </div>

          {/* ── Enhanced ── */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-medium uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              Enhanced
            </span>
            <div
              className={cn(
                "max-h-40 overflow-y-auto rounded-md border border-emerald-500/20 bg-emerald-500/5 p-3",
                "whitespace-pre-wrap break-words text-xs leading-relaxed text-foreground",
              )}
            >
              {enhanced || <span className="italic text-muted-foreground/50">No enhancement</span>}
            </div>
          </div>
        </div>
      </div>
    );
  },
);
OriginalVsEnhanced.displayName = "OriginalVsEnhanced";

export { OriginalVsEnhanced };
