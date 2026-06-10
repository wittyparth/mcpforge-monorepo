"use client";

import { PhoneCall, AlertCircle, Users, Gauge } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { AnalyticsOverview } from "@/types/api";

interface OverviewCardsProps {
  data: AnalyticsOverview | undefined;
  isLoading: boolean;
}

function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

function formatLatency(ms: number): string {
  if (ms < 1) return "<1ms";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function getErrorRateColor(rate: number): string {
  if (rate < 0.05) return "text-emerald-600 dark:text-emerald-400";
  if (rate <= 0.15) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-4" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-8 w-20" />
      </CardContent>
    </Card>
  );
}

/**
 * Four stat cards showing top-line analytics: Total Calls, Error Rate,
 * Unique Clients, and Average Latency.
 */
export function OverviewCards({ data, isLoading }: OverviewCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (!data || data.total_calls === 0) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="col-span-full">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <PhoneCall className="h-10 w-10 text-muted-foreground/30" />
            <h3 className="mt-3 text-sm font-medium">No calls yet</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Call your MCP server to start seeing analytics data here.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const stats = [
    {
      title: "Total Calls",
      value: formatNumber(data.total_calls),
      icon: PhoneCall,
      colorClass: "text-foreground",
    },
    {
      title: "Error Rate",
      value: `${(data.error_rate * 100).toFixed(1)}%`,
      icon: AlertCircle,
      colorClass: getErrorRateColor(data.error_rate),
    },
    {
      title: "Unique Clients",
      value: formatNumber(data.unique_clients),
      icon: Users,
      colorClass: "text-foreground",
    },
    {
      title: "Avg Latency",
      value: formatLatency(data.avg_latency_ms),
      icon: Gauge,
      colorClass: "text-foreground",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.title}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {stat.title}
            </CardTitle>
            <stat.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-semibold ${stat.colorClass}`}>
              {stat.value}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
