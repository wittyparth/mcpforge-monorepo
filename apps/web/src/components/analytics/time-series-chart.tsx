"use client";

import { format } from "date-fns";
import {
  LineChart,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Line,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import type { TimeSeriesPoint } from "@/types/api";

interface TimeSeriesChartProps {
  data: TimeSeriesPoint[] | undefined;
  isLoading: boolean;
  granularity: "hour" | "day";
}

/**
 * Line chart showing call volume and error count over time.
 * Uses the project's chart-1 (calls) and chart-2 (errors) CSS variables.
 */
export function TimeSeriesChart({
  data,
  isLoading,
  granularity,
}: TimeSeriesChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[320px] w-full rounded-lg" />
        </CardContent>
      </Card>
    );
  }

  const points = data ?? [];

  if (points.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold">
            Calls Over Time
          </CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            title="No time-series data"
            description="No calls recorded in this period."
          />
        </CardContent>
      </Card>
    );
  }

  const formatXAxis = (value: string) => {
    const d = new Date(value);
    if (granularity === "hour") return format(d, "MMM d, HH:mm");
    return format(d, "MMM d");
  };

  const formatTooltip = (value: string) => {
    const d = new Date(value);
    if (granularity === "hour") return format(d, "MMM d, yyyy HH:mm");
    return format(d, "MMM d, yyyy");
  };

  const chartData = points.map((p) => ({
    ...p,
    time: p.bucket_start,
  }));

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">
          Calls Over Time
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" />
            <XAxis
              dataKey="time"
              tickFormatter={formatXAxis}
              tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
              allowDecimals={false}
            />
            <Tooltip
              labelFormatter={formatTooltip}
              formatter={(value: number, name: string) => [
                new Intl.NumberFormat("en-US").format(value),
                name,
              ]}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="call_count"
              name="Calls"
              stroke="var(--color-chart-1)"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="error_count"
              name="Errors"
              stroke="var(--color-chart-2)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
