"use client";

import Link from "next/link";
import { BarChart3 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface EmptyAnalyticsProps {
  serverId: string;
}

/**
 * Dashboard empty state shown when there's no analytics data yet.
 * Encourages the user to start making calls from a client.
 */
export function EmptyAnalytics({ serverId }: EmptyAnalyticsProps) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-16 text-center">
        <BarChart3 className="h-12 w-12 text-muted-foreground/30" strokeWidth={1.5} />
        <h3 className="mt-4 text-lg font-medium">No analytics data yet</h3>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">
          Call your MCP server from Claude Desktop, Cursor, or the playground
          to start seeing usage data here.
        </p>
        <Button asChild className="mt-6">
          <Link href={`/dashboard/servers/${serverId}/playground`}>
            Open Playground
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
