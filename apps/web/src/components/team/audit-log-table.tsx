"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/shared/empty-state";
import { useAuditLog } from "@/hooks/use-team";
import type { AuditLogResponse } from "@/types/api";

const ACTION_COLORS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  "team.create": "default",
  "team.update": "secondary",
  "team.member.invite": "secondary",
  "team.member.accept": "default",
  "team.member.remove": "destructive",
  "team.member.role_change": "outline",
};

const ACTION_OPTIONS = [
  { value: "all", label: "All actions" },
  { value: "team.create", label: "Team created" },
  { value: "team.update", label: "Team updated" },
  { value: "team.member.invite", label: "Member invited" },
  { value: "team.member.accept", label: "Invitation accepted" },
  { value: "team.member.remove", label: "Member removed" },
  { value: "team.member.role_change", label: "Role changed" },
];

const PAGE_SIZE = 20;

export function AuditLogTable() {
  const [skip, setSkip] = useState(0);
  const [actionFilter, setActionFilter] = useState<string>("all");

  const { data, isLoading } = useAuditLog({
    skip,
    limit: PAGE_SIZE,
    action: actionFilter === "all" ? undefined : actionFilter,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1;

  const handlePrev = () => setSkip(Math.max(0, skip - PAGE_SIZE));
  const handleNext = () => setSkip(skip + PAGE_SIZE);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-48" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Select value={actionFilter} onValueChange={(v) => { setActionFilter(v); setSkip(0); }}>
          <SelectTrigger className="w-[180px]" aria-label="Filter by action">
            <SelectValue placeholder="Filter by action" />
          </SelectTrigger>
          <SelectContent>
            {ACTION_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">
          {total} {total === 1 ? "entry" : "entries"}
        </span>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No audit log entries"
          description="Team activity will appear here."
        />
      ) : (
        <>
          <div className="rounded-lg border">
            <div className="divide-y divide-border/50">
              {items.map((entry: AuditLogResponse) => (
                <div
                  key={entry.id}
                  className="flex items-center justify-between gap-4 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant={ACTION_COLORS[entry.action] ?? "secondary"}>
                        {entry.action}
                      </Badge>
                      <span className="text-sm font-medium truncate">
                        {entry.user_email}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{entry.resource_type}</span>
                      {entry.ip_address && (
                        <>
                          <span aria-hidden="true">&middot;</span>
                          <span>{entry.ip_address}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {new Date(entry.created_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrev}
                disabled={skip === 0}
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNext}
                disabled={currentPage >= totalPages}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
