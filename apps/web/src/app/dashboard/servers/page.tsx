"use client";

import Link from "next/link";
import { Plus, Server } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ServerCard } from "@/components/dashboard/server-card";
import { useServers } from "@/hooks/use-servers";

export default function ServersPage() {
  const { data, isLoading, isError, error } = useServers();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Servers</h1>
          <p className="text-sm text-muted-foreground">
            Manage your MCP servers
          </p>
        </div>
        <Button asChild>
          <Link href="/dashboard/servers/new">
            <Plus className="mr-2 h-4 w-4" />
            Create Server
          </Link>
        </Button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full rounded-xl" />
          ))}
        </div>
      )}

      {/* Error state */}
      {isError && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-sm text-destructive">
              Failed to load servers:{" "}
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => window.location.reload()}
            >
              Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {data && data.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Server className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-medium">No servers yet</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Create your first MCP server to get started. Paste an OpenAPI spec
              and get a hosted endpoint in seconds.
            </p>
            <Button asChild className="mt-6">
              <Link href="/dashboard/servers/new">
                <Plus className="mr-2 h-4 w-4" />
                Create Server
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Server list */}
      {data && data.length > 0 && (
        <div className="space-y-4">
          {data.map((server) => (
            <ServerCard key={server.id} server={server} />
          ))}
        </div>
      )}
    </div>
  );
}
