"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
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
import type { ClientBreakdownItem } from "@/types/api";

interface ClientBreakdownPieProps {
  data: ClientBreakdownItem[] | undefined;
  isLoading: boolean;
}

const PIE_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
];

/**
 * Pie chart showing tool call distribution by client name.
 * Uses Recharts with the project's chart CSS variables for colors.
 */
export function ClientBreakdownPie({
  data,
  isLoading,
}: ClientBreakdownPieProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[300px] w-full rounded-lg" />
        </CardContent>
      </Card>
    );
  }

  const items = data ?? [];

  if (items.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold">
            Client Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            title="No client data"
            description="No calls recorded in this period."
          />
        </CardContent>
      </Card>
    );
  }

  const chartData = items.map((item) => ({
    name: item.client_name,
    value: item.call_count,
  }));

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">
          Client Breakdown
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={90}
              paddingAngle={3}
              dataKey="value"
              nameKey="name"
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={PIE_COLORS[index % PIE_COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [
                new Intl.NumberFormat("en-US").format(value),
                "Calls",
              ]}
            />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
