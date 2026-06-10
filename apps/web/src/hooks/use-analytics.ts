"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  AnalyticsOverview,
  ClientBreakdownItem,
  DescriptionPerformance,
  ErrorLogItem,
  TimeSeriesPoint,
  ToolBreakdownItem,
} from "@/types/api";

export type AnalyticsRange = "7d" | "30d" | "90d";

/**
 * Top-line analytics numbers for a server. Backed by the rollup
 * tables so the response is fast even with many months of history.
 */
export function useAnalyticsOverview(serverId: string, range: AnalyticsRange) {
  return useQuery<AnalyticsOverview>({
    queryKey: ["server", serverId, "analytics", "overview", range],
    queryFn: () => api.servers.analytics.overview(serverId, range),
    enabled: serverId.length > 0,
    staleTime: 60_000,
  });
}

/**
 * Per-tool breakdown (call counts, error counts, selection rate).
 * Returns an empty list rather than throwing for a fresh server.
 */
export function useToolBreakdown(serverId: string, range: AnalyticsRange) {
  return useQuery<ToolBreakdownItem[]>({
    queryKey: ["server", serverId, "analytics", "tools", range],
    queryFn: () => api.servers.analytics.tools(serverId, range),
    enabled: serverId.length > 0,
    staleTime: 60_000,
  });
}

/**
 * Paginated error log, newest first. Reads directly from raw
 * ``tool_calls`` (not the rollup) so error messages are preserved.
 */
export function useErrorLog(
  serverId: string,
  range: AnalyticsRange,
  limit = 100,
  offset = 0,
) {
  return useQuery<ErrorLogItem[]>({
    queryKey: ["server", serverId, "analytics", "errors", range, limit, offset],
    queryFn: () => api.servers.analytics.errors(serverId, range, limit, offset),
    enabled: serverId.length > 0,
    staleTime: 30_000,
  });
}

/**
 * Per-client breakdown (Claude Desktop, Cursor, Unknown, etc).
 */
export function useClientBreakdown(serverId: string, range: AnalyticsRange) {
  return useQuery<ClientBreakdownItem[]>({
    queryKey: ["server", serverId, "analytics", "clients", range],
    queryFn: () => api.servers.analytics.clients(serverId, range),
    enabled: serverId.length > 0,
    staleTime: 60_000,
  });
}

/**
 * Time-series data for charts. ``granularity`` defaults to ``"hour"``
 * — pass ``"day"`` for 30d/90d ranges to keep the chart readable.
 */
export function useTimeSeries(
  serverId: string,
  range: AnalyticsRange,
  granularity: "hour" | "day" = "hour",
) {
  return useQuery<TimeSeriesPoint[]>({
    queryKey: [
      "server",
      serverId,
      "analytics",
      "timeseries",
      range,
      granularity,
    ],
    queryFn: () => api.servers.analytics.timeseries(serverId, range, granularity),
    enabled: serverId.length > 0,
    staleTime: 60_000,
  });
}

/**
 * Description-performance panel. When ``toolName`` is omitted,
 * returns one row per tool that has edit history.
 */
export function useDescriptionPerformance(
  serverId: string,
  toolName?: string,
) {
  return useQuery<DescriptionPerformance[]>({
    queryKey: [
      "server",
      serverId,
      "analytics",
      "description-performance",
      toolName ?? "all",
    ],
    queryFn: () => api.servers.analytics.descriptionPerformance(serverId, toolName),
    enabled: serverId.length > 0,
    staleTime: 5 * 60_000,
  });
}
