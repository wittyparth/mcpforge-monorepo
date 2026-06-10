"use client";

import { useState } from "react";
import {
  History,
  Copy,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { DuplicateServerDialog } from "./duplicate-server-dialog";
import { RollbackDialog } from "./rollback-dialog";
import { useVersions, useServer } from "@/hooks/use-servers";
import type { ServerVersionResponse } from "@/types/api";

interface VersionsTabProps {
  serverId: string;
  serverName: string;
  currentVersion: number;
}

const PAGE_SIZE = 10;

function fmtDate(raw: string | null | undefined): string {
  if (!raw) return "\u2014";
  return new Date(raw).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function VersionsTab({ serverId, serverName, currentVersion }: VersionsTabProps) {
  const [page, setPage] = useState(1);
  const skip = (page - 1) * PAGE_SIZE;

  const { data: versionsData, isLoading } = useVersions(serverId, { skip, limit: PAGE_SIZE });
  const { data: server } = useServer(serverId);

  const [duplicateOpen, setDuplicateOpen] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState<ServerVersionResponse | null>(null);

  const items = versionsData?.items ?? [];
  const total = versionsData?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <History className="h-4 w-4" />
              Version History
            </CardTitle>
            <CardDescription>
              Current version: <Badge variant="secondary">v{currentVersion}</Badge>
            </CardDescription>
          </div>
          <Button size="sm" variant="outline" onClick={() => setDuplicateOpen(true)}>
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            Duplicate Server
          </Button>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <EmptyState
              title="No versions yet"
              description="Version history will appear here after your first update."
              icon={History}
            />
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-20">Version</TableHead>
                    <TableHead>Change Note</TableHead>
                    <TableHead className="hidden sm:table-cell">Changed By</TableHead>
                    <TableHead className="hidden sm:table-cell">Date</TableHead>
                    <TableHead className="w-32 text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((v: ServerVersionResponse) => {
                    const isCurrent = v.version === currentVersion;
                    return (
                      <TableRow key={v.id} className={isCurrent ? "bg-muted/30" : undefined}>
                        <TableCell>
                          <Badge variant={isCurrent ? "default" : "outline"}>
                            v{v.version}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-[240px] truncate text-sm">
                          {v.change_note || <span className="text-muted-foreground italic">No note</span>}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                          {v.changed_by_email ?? v.changed_by ?? "\u2014"}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                          {fmtDate(v.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          {isCurrent ? (
                            <span className="text-xs text-muted-foreground">Current</span>
                          ) : (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 gap-1"
                              onClick={() => setRollbackTarget(v)}
                            >
                              <RotateCcw className="h-3 w-3" />
                              Rollback
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Showing {skip + 1}\u2013{Math.min(skip + PAGE_SIZE, total)} of {total} versions
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-xs text-muted-foreground">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <DuplicateServerDialog
        open={duplicateOpen}
        onOpenChange={setDuplicateOpen}
        serverId={serverId}
        currentName={server?.name ?? serverName}
      />

      {rollbackTarget && (
        <RollbackDialog
          open={!!rollbackTarget}
          onOpenChange={(o) => { if (!o) setRollbackTarget(null); }}
          serverId={serverId}
          targetVersion={rollbackTarget.version}
          changeNote={rollbackTarget.change_note}
        />
      )}
    </div>
  );
}
