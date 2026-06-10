"use client";

import Link from "next/link";
import { Globe, Activity, MoreVertical, Copy, Trash2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
  onDuplicate?: (server: McpServer) => void;
  onDelete?: (server: McpServer) => void;
}

export function ServerCard({ server, onDuplicate, onDelete }: ServerCardProps) {
  return (
    <Link href={`/dashboard/servers/${server.id}`}>
      <Card className="transition-colors hover:bg-accent/50 cursor-pointer">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base font-medium">{server.name}</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant={statusColors[server.status]}>{server.status}</Badge>
            {(onDuplicate || onDelete) && (
              <DropdownMenu>
                <DropdownMenuTrigger
                  asChild
                  onClick={(e) => e.preventDefault()}
                >
                  <button className="rounded-md p-1 text-muted-foreground hover:text-foreground focus:outline-none focus:ring-1 focus:ring-ring">
                    <MoreVertical className="h-4 w-4" />
                    <span className="sr-only">Actions</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {onDuplicate && (
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.preventDefault();
                        onDuplicate(server);
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" />
                      Duplicate
                    </DropdownMenuItem>
                  )}
                  {onDelete && (
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.preventDefault();
                        onDelete(server);
                      }}
                      className="text-destructive focus:text-destructive"
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
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
