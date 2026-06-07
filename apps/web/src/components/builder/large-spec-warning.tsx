"use client";

import * as React from "react";
import { AlertTriangle } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export interface LargeSpecWarningProps {
  /** Number of endpoints in the spec. */
  endpointCount: number;
  /** Controlled open state. */
  open: boolean;
  /** Called when the dialog open state changes (close / dismiss). */
  onOpenChange: (open: boolean) => void;
  /** Called when the user confirms they want to continue with all selected. */
  onConfirm: () => void;
}

const LargeSpecWarning = React.forwardRef<HTMLDivElement, LargeSpecWarningProps>(
  ({ endpointCount, open, onOpenChange, onConfirm }, ref) => {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          ref={ref}
          className={[
            "border-yellow-500/50",
            "bg-gradient-to-b from-yellow-500/5 to-transparent",
            "dark:from-yellow-500/10 dark:to-transparent",
          ].join(" ")}
        >
          <DialogHeader>
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-yellow-500/20">
                <AlertTriangle className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
              </div>
              <div className="space-y-2">
                <DialogTitle>Large spec detected</DialogTitle>
                <DialogDescription>
                  This spec has{" "}
                  <strong className="font-semibold text-foreground">
                    {endpointCount} endpoints
                  </strong>
                  . Selecting all of them will create a large, harder-to-navigate
                  tool list. We recommend selecting 10&ndash;30 key tools for best
                  results.
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                onConfirm();
                onOpenChange(false);
              }}
            >
              Continue with all selected
            </Button>
            <Button onClick={() => onOpenChange(false)}>
              Let me curate first
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  },
);
LargeSpecWarning.displayName = "LargeSpecWarning";

export { LargeSpecWarning };
