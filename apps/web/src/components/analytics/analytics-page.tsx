"use client";

import { useState } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { DateRangePicker } from "@/components/analytics/date-range-picker";
import { OverviewCards } from "@/components/analytics/overview-cards";
import { TimeSeriesChart } from "@/components/analytics/time-series-chart";
import { ToolBreakdownTable } from "@/components/analytics/tool-breakdown-table";
import { ClientBreakdownPie } from "@/components/analytics/client-breakdown-pie";
import { ErrorLog } from "@/components/analytics/error-log";
import { DescriptionPerformancePanel } from "@/components/analytics/description-performance-panel";
import { CsvExportButton } from "@/components/analytics/csv-export-button";
import { EmptyAnalytics } from "@/components/analytics/empty-analytics";

import {
  useAnalyticsOverview,
  useTimeSeries,
  useToolBreakdown,
  useErrorLog,
  useClientBreakdown,
  useDescriptionPerformance,
} from "@/hooks/use-analytics";
import type { AnalyticsRange } from "@/hooks/use-analytics";

interface AnalyticsPageProps {
  serverId: string;
}

/**
 * Main analytics dashboard page. Composes all analytics sub-components
 * into a single scrollable layout with date range selection.
 */
export function AnalyticsPage({ serverId }: AnalyticsPageProps) {
  const [range, setRange] = useState<AnalyticsRange>("7d");

  const overview = useAnalyticsOverview(serverId, range);
  const timeSeries = useTimeSeries(
    serverId,
    range,
    range === "7d" ? "hour" : "day",
  );
  const toolBreakdown = useToolBreakdown(serverId, range);
  const errorLog = useErrorLog(serverId, range);
  const clientBreakdown = useClientBreakdown(serverId, range);
  const descriptionPerformance = useDescriptionPerformance(serverId);

  const isLoading = overview.isLoading;
  const isError = overview.isError;
  const error = overview.error;

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
          <Skeleton className="h-9 w-[160px]" />
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[104px] w-full rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-[360px] w-full rounded-xl" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Skeleton className="h-[300px] w-full rounded-xl lg:col-span-2" />
          <Skeleton className="h-[300px] w-full rounded-xl" />
        </div>
        <Skeleton className="h-[300px] w-full rounded-xl" />
        <Skeleton className="h-[200px] w-full rounded-xl" />
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
          <p className="text-sm text-muted-foreground">
            Track how AI clients use your MCP server.
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <AlertTriangle className="h-12 w-12 text-destructive/50" />
            <h3 className="mt-4 text-lg font-medium">
              Failed to load analytics
            </h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              {error instanceof Error
                ? error.message
                : "An unexpected error occurred"}
            </p>
            <Button
              variant="outline"
              className="mt-6"
              onClick={() => overview.refetch()}
            >
              <RotateCw className="h-4 w-4" />
              Try again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Empty state: no calls at all
  const hasNoCalls =
    overview.data === undefined || overview.data.total_calls === 0;

  if (hasNoCalls) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
            <p className="text-sm text-muted-foreground">
              Track how AI clients use your MCP server.
            </p>
          </div>
          <DateRangePicker value={range} onChange={setRange} />
        </div>
        <EmptyAnalytics serverId={serverId} />
      </div>
    );
  }

  // Full dashboard
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
          <p className="text-sm text-muted-foreground">
            Track how AI clients use your MCP server.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <CsvExportButton serverId={serverId} range={range} />
          <DateRangePicker value={range} onChange={setRange} />
        </div>
      </div>

      {/* Overview cards */}
      <OverviewCards data={overview.data} isLoading={overview.isLoading} />

      {/* Time series */}
      <TimeSeriesChart
        data={timeSeries.data}
        isLoading={timeSeries.isLoading}
        granularity={range === "7d" ? "hour" : "day"}
      />

      {/* Two-column: Tool breakdown + Client pie */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ToolBreakdownTable
            data={toolBreakdown.data}
            isLoading={toolBreakdown.isLoading}
          />
        </div>
        <div>
          <ClientBreakdownPie
            data={clientBreakdown.data}
            isLoading={clientBreakdown.isLoading}
          />
        </div>
      </div>

      {/* Error log */}
      <ErrorLog data={errorLog.data} isLoading={errorLog.isLoading} />

      {/* Description performance */}
      <DescriptionPerformancePanel
        data={descriptionPerformance.data}
        isLoading={descriptionPerformance.isLoading}
      />
    </div>
  );
}
