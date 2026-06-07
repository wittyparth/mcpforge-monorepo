import Link from "next/link";
import { Globe, Activity } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { McpServer } from "@/types";

const statusColors: Record<
  McpServer["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  building: "secondary",
  active: "default",
  paused: "outline",
  error: "destructive",
};

interface ServerCardProps {
  server: McpServer;
}

export function ServerCard({ server }: ServerCardProps) {
  return (
    <Link href={`/dashboard/servers/${server.slug}`}>
      <Card className="transition-colors hover:bg-accent/50 cursor-pointer">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base font-medium">{server.name}</CardTitle>
          <Badge variant={statusColors[server.status]}>{server.status}</Badge>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <Globe className="h-3.5 w-3.5" />
              {server.base_url}
            </span>
            <span className="flex items-center gap-1">
              <Activity className="h-3.5 w-3.5" />
              {server.monthly_calls} calls this month
            </span>
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            Created {new Date(server.created_at).toLocaleDateString()}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
