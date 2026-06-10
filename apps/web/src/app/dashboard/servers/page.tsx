/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Server, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ServerCard } from "@/components/dashboard/server-card";
import { DuplicateServerDialog } from "@/components/server/duplicate-server-dialog";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { useServers } from "@/hooks/use-servers";
import { api, ApiClientError } from "@/lib/api";
import type { McpServer } from "@/types/api";

export default function ServersPage() {
  const { data, isLoading, isError, error } = useServers();
  const qc = useQueryClient();
  const [duplicateTarget, setDuplicateTarget] = useState<McpServer | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<McpServer | null>(null);

  const deleteSrv = useMutation({
    mutationFn: (id: string) => api.servers.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["servers"] });
      toast.success("Server deleted");
      setDeleteTarget(null);
    },
    onError: (e: unknown) => {
      toast.error(e instanceof ApiClientError ? e.message : "Failed to delete server");
    },
  });

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
          {data.map((server: any) => (
            <ServerCard
              key={server.id}
              server={server}
              onDuplicate={(s) => setDuplicateTarget(s)}
              onDelete={(s) => setDeleteTarget(s)}
            />
          ))}
        </div>
      )}

      {duplicateTarget && (
        <DuplicateServerDialog
          open={!!duplicateTarget}
          onOpenChange={(o) => { if (!o) setDuplicateTarget(null); }}
          serverId={duplicateTarget.id}
          currentName={duplicateTarget.name}
          prefillName={duplicateTarget.name}
        />
      )}

      {/* ── Delete server confirmation ── */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="h-4 w-4 text-destructive" />
              Delete server
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <strong>{deleteTarget?.name}</strong>?
              This action cannot be undone. All associated data will be permanently removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteTarget) deleteSrv.mutate(deleteTarget.id);
              }}
              disabled={deleteSrv.isPending}
            >
              {deleteSrv.isPending ? (
                <>
                  <LoadingSpinner size="sm" />
                  Deleting...
                </>
              ) : (
                "Delete server"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
