"use client";

import * as React from "react";
import { RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export interface RevertFieldButtonProps {
  /** Called when the user clicks the revert button. */
  onRevert: () => void;
  /** The original value before any edits. */
  original: string;
  /** The current (potentially edited) value. */
  current: string;
  /** Optional size variant. */
  size?: "sm" | "default";
  /** Optional label override. */
  label?: string;
}

/**
 * Button that reverts a field to its original value.
 *
 * Only renders when `original` differs from `current`. Uses a ghost
 * button style with a revert icon to minimize visual noise.
 */
const RevertFieldButton = React.forwardRef<HTMLDivElement, RevertFieldButtonProps>(
  ({ onRevert, original, current, size = "default", label = "Revert to original" }, ref) => {
    if (original === current) return null;

    return (
      <div ref={ref}>
        <Button
          type="button"
          variant="ghost"
          size={size}
          onClick={onRevert}
          className={cn(
            "gap-1 text-muted-foreground hover:text-orange-600 dark:hover:text-orange-400",
            size === "sm" ? "h-7 px-2 text-[11px]" : "h-8 px-2.5 text-xs",
          )}
        >
          <RotateCcw className="shrink-0" style={{ width: size === "sm" ? 10 : 12, height: size === "sm" ? 10 : 12 }} />
          {label}
        </Button>
      </div>
    );
  },
);
RevertFieldButton.displayName = "RevertFieldButton";

export { RevertFieldButton };
