"use client";

import { format } from "date-fns";
import { Sparkles, User, RotateCcw, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import type { DescriptionPerformance } from "@/types/api";

interface DescriptionPerformancePanelProps {
  data: DescriptionPerformance[] | undefined;
  isLoading: boolean;
}

function getEditSourceConfig(
  source: DescriptionPerformance["edit_source"],
): { label: string; variant: "default" | "secondary" | "outline"; icon: typeof Sparkles } {
  switch (source) {
    case "ai":
      return { label: "AI", variant: "default", icon: Sparkles };
    case "user":
      return { label: "User", variant: "secondary", icon: User };
    case "revert":
      return { label: "Revert", variant: "outline", icon: RotateCcw };
    default:
      return { label: "Unknown", variant: "outline", icon: Minus };
  }
}

function DeltaIndicator({ delta }: { delta: number | null }) {
  if (delta === null || delta === undefined) {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
        <Minus className="h-3.5 w-3.5" />
        —
      </span>
    );
  }

  if (delta > 0) {
    return (
      <span className="inline-flex items-center gap-1 text-sm font-medium text-emerald-600 dark:text-emerald-400">
        <ArrowUpRight className="h-3.5 w-3.5" />
        +{delta.toFixed(1)}%
      </span>
    );
  }

  if (delta < 0) {
    return (
      <span className="inline-flex items-center gap-1 text-sm font-medium text-red-600 dark:text-red-400">
        <ArrowDownRight className="h-3.5 w-3.5" />
        {delta.toFixed(1)}%
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
      <Minus className="h-3.5 w-3.5" />
      0%
    </span>
  );
}

/**
 * Panel showing description edit history and impact on call rates.
 * Each tool card shows edit source, before/after counts, delta, and message.
 */
export function DescriptionPerformancePanel({
  data,
  isLoading,
}: DescriptionPerformancePanelProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-56" />
        </CardHeader>
        <CardContent className="space-y-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  const items = data ?? [];

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">
          Description Performance
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {items.length === 0 ? (
          <div className="px-6 pb-6">
            <EmptyState
              icon={Sparkles}
              title="No description edits tracked yet"
              description="Edit a tool description to start measuring impact."
            />
          </div>
        ) : (
          <div className="divide-y divide-border/50">
            {items.map((item) => {
              const sourceConfig = getEditSourceConfig(item.edit_source);

              return (
                <div
                  key={item.tool_name}
                  className="space-y-3 px-4 py-4 sm:px-6"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-medium">
                        {item.tool_name}
                      </h4>
                      <Badge variant={sourceConfig.variant} className="text-[10px]">
                        <sourceConfig.icon className="mr-1 h-2.5 w-2.5" />
                        {sourceConfig.label}
                      </Badge>
                    </div>
                    {item.edited_at && (
                      <span className="text-xs text-muted-foreground">
                        {format(new Date(item.edited_at), "MMM d, yyyy")}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-6 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">Before:</span>
                      <span className="font-mono tabular-nums">
                        {new Intl.NumberFormat("en-US").format(
                          item.before_call_count,
                        )}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">After:</span>
                      <span className="font-mono tabular-nums">
                        {new Intl.NumberFormat("en-US").format(
                          item.after_call_count,
                        )}
                      </span>
                    </div>
                    <DeltaIndicator delta={item.delta_pct} />
                  </div>

                  {item.message && (
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {item.message}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
