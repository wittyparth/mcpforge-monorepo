"use client";

import { Check, X } from "lucide-react";

import { LoadingSpinner } from "@/components/shared/loading-spinner";

type ScanStatus = "idle" | "scanning" | "completed" | "failed";

interface ScanProgressProps {
  status: ScanStatus;
  criticalCount?: number;
  highCount?: number;
  mediumCount?: number;
  infoCount?: number;
}

/**
 * Displays the current state of a security scan with appropriate
 * visual feedback for each status.
 *
 * - idle: renders nothing
 * - scanning: animated spinner with progress text
 * - completed: green checkmark with count summary
 * - failed: red X with error message
 */
export function ScanProgress({
  status,
  criticalCount,
  highCount,
  mediumCount,
  infoCount,
}: ScanProgressProps) {
  if (status === "idle") return null;

  if (status === "scanning") {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
        <LoadingSpinner size="sm" />
        <span className="text-sm font-medium text-primary">
          Security scan in progress...
        </span>
      </div>
    );
  }

  if (status === "completed") {
    const total = (criticalCount ?? 0) + (highCount ?? 0) + (mediumCount ?? 0) + (infoCount ?? 0);
    return (
      <div className="flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-800 dark:bg-emerald-950">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/10">
          <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
            Scan completed
          </span>
          {total > 0 && (
            <span className="text-xs text-emerald-600/80 dark:text-emerald-400/80">
              {criticalCount} critical, {highCount} high, {mediumCount} medium,{" "}
              {infoCount} info
            </span>
          )}
          {total === 0 && (
            <span className="text-xs text-emerald-600/80 dark:text-emerald-400/80">
              No findings detected
            </span>
          )}
        </div>
      </div>
    );
  }

  // failed
  return (
    <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950">
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500/10">
        <X className="h-3.5 w-3.5 text-red-600 dark:text-red-400" />
      </div>
      <span className="text-sm font-medium text-red-700 dark:text-red-300">
        Scan failed
      </span>
    </div>
  );
}
