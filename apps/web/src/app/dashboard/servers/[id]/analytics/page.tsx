"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, BarChart3 } from "lucide-react";

import { AnalyticsPage } from "@/components/analytics/analytics-page";
import { Skeleton } from "@/components/ui/skeleton";

export default function AnalyticsRoutePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/servers/${id}`}
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to server
      </Link>

      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
          <BarChart3 className="h-5 w-5 text-muted-foreground" />
        </div>
        <p className="text-sm text-muted-foreground">
          Track how AI clients use your MCP server, with privacy-preserving
          per-tool breakdown and description performance insights.
        </p>
      </div>

      {/* SSR-friendly boundary — the page itself manages data fetching. */}
      <AnalyticsShell serverId={id} />
    </div>
  );
}

function AnalyticsShell({ serverId }: { serverId: string }) {
  // The AnalyticsPage component is a "use client" composition; rendering
  // it directly here keeps the route a thin shell. A Skeleton shows
  // while client-side hooks resolve.
  return (
    <>
      <div className="hidden">
        <Skeleton className="h-5 w-32" />
      </div>
      <AnalyticsPage serverId={serverId} />
    </>
  );
}
