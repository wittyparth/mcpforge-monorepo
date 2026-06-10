"use client";

import { format } from "date-fns";
import { AlertTriangle } from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import type { ErrorLogItem } from "@/types/api";

interface ErrorLogProps {
  data: ErrorLogItem[] | undefined;
  isLoading: boolean;
}

function truncate(str: string, max: number): string {
  if (str.length <= max) return str;
  return `${str.slice(0, max)}…`;
}

function getErrorTypeColor(type: string): "destructive" | "secondary" | "outline" {
  const lower = type.toLowerCase();
  if (lower.includes("timeout")) return "outline";
  if (lower.includes("auth") || lower.includes("forbidden")) return "destructive";
  return "secondary";
}

/**
 * Error log table showing up to 50 rows of recent errors with timestamp,
 * tool name, error type badge, message, and client.
 */
export function ErrorLog({ data, isLoading }: ErrorLogProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-28" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  const errors = (data ?? []).slice(0, 50);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">Error Log</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {errors.length === 0 ? (
          <div className="px-6 pb-6">
            <EmptyState
              icon={AlertTriangle}
              title="No errors in this period"
              description="All tool calls completed successfully."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2">Time</th>
                  <th className="px-4 py-2">Tool</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Message</th>
                  <th className="px-4 py-2">Client</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {errors.map((item, idx) => (
                  <tr
                    key={`${item.called_at}-${item.tool_name}-${idx}`}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    <td className="whitespace-nowrap px-4 py-2.5 text-xs text-muted-foreground">
                      {format(new Date(item.called_at), "MMM d, HH:mm")}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 font-medium">
                      {item.tool_name}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5">
                      <Badge
                        variant={getErrorTypeColor(item.error_type)}
                        className="text-[10px]"
                      >
                        {item.error_type}
                      </Badge>
                    </td>
                    <td className="max-w-xs truncate px-4 py-2.5 text-muted-foreground">
                      {truncate(item.error_msg, 200)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">
                      {item.client_name ?? "—"}
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
