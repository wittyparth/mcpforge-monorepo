"use client";

import { Wrench } from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import type { ToolBreakdownItem } from "@/types/api";

interface ToolBreakdownTableProps {
  data: ToolBreakdownItem[] | undefined;
  isLoading: boolean;
}

function formatLatency(ms: number): string {
  if (ms < 1) return "<1ms";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Table showing per-tool breakdown: name, calls, errors, avg latency,
 * and a selection-rate progress bar. Sorted by call count descending.
 */
export function ToolBreakdownTable({
  data,
  isLoading,
}: ToolBreakdownTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  const items = (data ?? [])
    .slice()
    .sort((a, b) => b.call_count - a.call_count)
    .slice(0, 10);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">
          Tool Breakdown
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {items.length === 0 ? (
          <div className="px-6 pb-6">
            <EmptyState
              icon={Wrench}
              title="No tool data"
              description="No tool calls recorded in this period."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2">Tool Name</th>
                  <th className="px-4 py-2 text-right">Calls</th>
                  <th className="px-4 py-2 text-right">Errors</th>
                  <th className="px-4 py-2 text-right">Avg Latency</th>
                  <th className="px-4 py-2 text-right">Selection Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {items.map((item) => (
                  <tr
                    key={item.tool_name}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    <td className="whitespace-nowrap px-4 py-2.5 font-medium">
                      {item.tool_name}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums">
                      {new Intl.NumberFormat("en-US").format(item.call_count)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums">
                      {item.error_count > 0 ? (
                        <span className="text-red-600 dark:text-red-400">
                          {new Intl.NumberFormat("en-US").format(
                            item.error_count,
                          )}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums text-muted-foreground">
                      {formatLatency(item.avg_latency_ms)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {(item.selection_rate * 100).toFixed(0)}%
                        </span>
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-chart-1 transition-all"
                            style={{
                              width: `${Math.round(item.selection_rate * 100)}%`,
                            }}
                          />
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
