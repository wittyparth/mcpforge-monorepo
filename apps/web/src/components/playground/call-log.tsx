"use client";

import * as React from "react";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Trash2,
  RotateCcw,
} from "lucide-react";

import type { CallLogEntry } from "@/hooks/use-playground";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

export interface CallLogProps {
  /** List of call log entries */
  entries: CallLogEntry[];
  /** Called to clear all log entries */
  onClear: () => void;
  /** Called when user clicks an entry to reload it into the form */
  onReplayEntry: (entry: CallLogEntry) => void;
}

function formatTimestamp(ts: number): string {
  return new Date(ts).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/**
 * Right panel: call history for the current playground session.
 *
 * Each entry shows timestamp, tool name, status, and allows re-loading
 * the call parameters back into the form.
 */
function CallLog({ entries, onClear, onReplayEntry }: CallLogProps) {
  return (
    <Card className="flex h-full flex-col overflow-hidden border-0 rounded-none border-l border-border/50">
      <CardHeader className="p-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            Call Log
            {entries.length > 0 && (
              <Badge variant="secondary" className="text-[10px] tabular-nums">
                {entries.length}
              </Badge>
            )}
          </CardTitle>
          {entries.length > 0 && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onClear}
              aria-label="Clear call log"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </CardHeader>

      <Separator />

      <ScrollArea className="flex-1">
        <div className="space-y-0.5 px-1.5 py-2" role="list" aria-label="Call history">
          {entries.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-12 text-center text-xs text-muted-foreground">
              <Clock className="h-5 w-5" />
              <span>No calls yet</span>
              <span className="text-[10px]">Call a tool to see results here</span>
            </div>
          )}

          {entries.map((entry) => {
            const isError = entry.response?.isError === true;
            const hasResponse = !!entry.response;

            return (
              <div
                key={entry.id}
                role="listitem"
                className={cn(
                  "group relative flex flex-col gap-1 rounded-md px-2.5 py-2 text-xs transition-colors",
                  "hover:bg-accent/50",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    {hasResponse &&
                      (isError ? (
                        <XCircle className="h-3 w-3 shrink-0 text-destructive" />
                      ) : (
                        <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-500" />
                      ))}
                    <span className="truncate font-medium font-mono text-[11px]">
                      {entry.toolName}
                    </span>
                  </div>
                  <span className="shrink-0 text-[10px] text-muted-foreground tabular-nums">
                    {formatTimestamp(entry.timestamp)}
                  </span>
                </div>

                {/* Arguments preview */}
                {Object.keys(entry.arguments).length > 0 && (
                  <p className="truncate text-[10px] text-muted-foreground font-mono">
                    {JSON.stringify(entry.arguments)}
                  </p>
                )}

                {/* Replay button */}
                <Button
                  variant="ghost"
                  size="sm"
                  className="absolute right-1 top-1 h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => onReplayEntry(entry)}
                  aria-label={`Replay ${entry.toolName} call`}
                >
                  <RotateCcw className="h-3 w-3" />
                </Button>
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </Card>
  );
}

export { CallLog };
