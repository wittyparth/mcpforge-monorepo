"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface CopyToClipboardProps
  extends React.HTMLAttributes<HTMLButtonElement> {
  /** The text value to copy to the clipboard. */
  value: string;
  /** Human-readable label for the copied content (used in the toast message). */
  label?: string;
}

/**
 * A compact icon button that copies a value to the clipboard.
 *
 * Shows a brief Check icon animation on success and displays a
 * Sonner toast confirming the action. Falls back to an error toast
 * if the clipboard API rejects the write.
 */
const CopyToClipboard = React.forwardRef<
  HTMLButtonElement,
  CopyToClipboardProps
>(({ value, label, className, ...props }, ref) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast.success(`Copied ${label ?? "to clipboard"}`);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy");
    }
  }, [value, label]);

  return (
    <Button
      ref={ref}
      type="button"
      variant="ghost"
      size="icon"
      className={cn("h-7 w-7", className)}
      onClick={handleCopy}
      aria-label={`Copy ${label ?? "value"} to clipboard`}
      {...props}
    >
      <div className="relative h-4 w-4">
        <Copy
          className={cn(
            "absolute inset-0 h-4 w-4 transition-all duration-200",
            copied ? "scale-0 opacity-0" : "scale-100 opacity-100",
          )}
        />
        <Check
          className={cn(
            "absolute inset-0 h-4 w-4 text-emerald-500 transition-all duration-200",
            copied ? "scale-100 opacity-100" : "scale-0 opacity-0",
          )}
        />
      </div>
    </Button>
  );
});
CopyToClipboard.displayName = "CopyToClipboard";

export { CopyToClipboard };
