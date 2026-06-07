"use client";

import { useCurrentUser } from "@/hooks/use-auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Server, Activity, Zap, TrendingUp } from "lucide-react";

const stats = [
  {
    title: "Active Servers",
    value: "0",
    icon: Server,
    description: "No servers deployed yet",
  },
  {
    title: "Total Calls",
    value: "0",
    icon: Activity,
    description: "No API calls this month",
  },
  {
    title: "AI Enhancements",
    value: "3",
    icon: Zap,
    description: "Free credits remaining",
  },
  {
    title: "Plan",
    value: "Free",
    icon: TrendingUp,
    description: "Upgrade for more features",
  },
];

export default function DashboardPage() {
  const { data: user } = useCurrentUser();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome{user?.display_name ? `, ${user.display_name}` : ""}
        </h1>
        <p className="text-sm text-muted-foreground">
          Here&apos;s an overview of your MCPForge workspace.
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {stat.title}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">
                {stat.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick start */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Start</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Get started by creating your first MCP server. You&apos;ll paste
            your OpenAPI spec, configure authentication, and get a hosted
            endpoint.
          </p>
          <ol className="list-inside list-decimal space-y-2 text-sm text-muted-foreground">
            <li>Click &quot;Create Server&quot; in the sidebar</li>
            <li>Paste your OpenAPI spec URL or upload a file</li>
            <li>Configure authentication and deploy</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
