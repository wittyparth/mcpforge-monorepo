"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface QualityScoreBadgeProps {
  /** The numeric quality score (0–100). */
  score: number;
  /** The human-readable badge label. */
  badge: "Excellent" | "Good" | "Fair" | "Poor";
  /** Optional size variant. */
  size?: "sm" | "default";
}

const badgeStyles: Record<
  QualityScoreBadgeProps["badge"],
  { bg: string; text: string; border: string; ring: string }
> = {
  Excellent: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-700 dark:text-emerald-400",
    border: "border-emerald-500/30",
    ring: "ring-emerald-500/20",
  },
  Good: {
    bg: "bg-amber-500/10",
    text: "text-amber-700 dark:text-amber-400",
    border: "border-amber-500/30",
    ring: "ring-amber-500/20",
  },
  Fair: {
    bg: "bg-orange-500/10",
    text: "text-orange-700 dark:text-orange-400",
    border: "border-orange-500/30",
    ring: "ring-orange-500/20",
  },
  Poor: {
    bg: "bg-red-500/10",
    text: "text-red-700 dark:text-red-400",
    border: "border-red-500/30",
    ring: "ring-red-500/20",
  },
};

/**
 * Color-coded badge that displays a numeric quality score alongside
 * its human-readable label (Excellent / Good / Fair / Poor).
 *
 * Each badge level has a distinct color palette that remains accessible
 * in both light and dark modes.
 */
const QualityScoreBadge = React.forwardRef<HTMLDivElement, QualityScoreBadgeProps>(
  ({ score, badge, size = "default" }, ref) => {
    const styles = badgeStyles[badge];

    return (
      <div
        ref={ref}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border font-medium ring-1 ring-inset",
          styles.bg,
          styles.text,
          styles.border,
          styles.ring,
          size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
        )}
      >
        <span className="font-mono font-bold tabular-nums">{score}</span>
        <span className="opacity-70">·</span>
        <span>{badge}</span>
      </div>
    );
  },
);
QualityScoreBadge.displayName = "QualityScoreBadge";

export { QualityScoreBadge };
