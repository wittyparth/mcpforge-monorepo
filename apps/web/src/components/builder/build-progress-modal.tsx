"use client";

import * as React from "react";
import {
  AlertCircle,
  Loader2,
  RotateCcw,
  Sparkles,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useBuildStatus, useStartBuild } from "@/hooks/use-build-status";
import type { BuildStage, BuildStatusEvent } from "@/types/api";
import { BuildStepIndicator } from "./build-step-indicator";

// ── Stage badge colour map ────────────────────────────────────────

const stageBadgeColors: Record<
  BuildStage,
  { bg: string; text: string; border: string }
> = {
  parsing: {
    bg: "bg-blue-500/10",
    text: "text-blue-600 dark:text-blue-400",
    border: "border-blue-500/20",
  },
  generating: {
    bg: "bg-purple-500/10",
    text: "text-purple-600 dark:text-purple-400",
    border: "border-purple-500/20",
  },
  testing: {
    bg: "bg-amber-500/10",
    text: "text-amber-600 dark:text-amber-400",
    border: "border-amber-500/20",
  },
  deploying: {
    bg: "bg-cyan-500/10",
    text: "text-cyan-600 dark:text-cyan-400",
    border: "border-cyan-500/20",
  },
  complete: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-600 dark:text-emerald-400",
    border: "border-emerald-500/20",
  },
  error: {
    bg: "bg-destructive/10",
    text: "text-destructive",
    border: "border-destructive/30",
  },
};

// ── Event row ─────────────────────────────────────────────────────

interface EventRowProps {
  event: BuildStatusEvent;
  index: number;
}

function EventRow({ event, index }: EventRowProps) {
  const colors = stageBadgeColors[event.stage];

  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted/50",
        event.stage === "error" && "bg-destructive/5",
      )}
    >
      {/* Index / timestamp placeholder */}
      <span className="mt-px shrink-0 font-mono text-[11px] leading-4 text-muted-foreground/60 w-6 text-right">
        {index + 1}
      </span>

      {/* Stage badge */}
      <Badge
        variant="outline"
        className={cn(
          "shrink-0 text-[10px] uppercase font-bold leading-none px-1.5 py-0.5 tracking-wider border",
          colors.bg,
          colors.text,
          colors.border,
        )}
      >
        {event.stage}
      </Badge>

      {/* Message */}
      <span className="flex-1 leading-5 text-foreground/80 break-words">
        {event.message}
      </span>

      {/* Progress */}
      <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
        {event.progress}%
      </span>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────

interface BuildProgressModalProps {
  /** Whether the modal is visible */
  open: boolean;
  /** Called when the modal wants to open or close */
  onOpenChange: (open: boolean) => void;
  /** Server slug to build */
  slug: string;
  /** Called when the build completes successfully (1s delay) */
  onComplete: () => void;
  /** Called immediately when a build error is received */
  onError: (error: string) => void;
}

/**
 * Full-sized modal that drives the SSE-based server build pipeline.
 *
 * Orchestrates `useStartBuild` and `useBuildStatus` hooks to start a
 * build and stream progress events in real-time. Displays a step
 * indicator, live event log with auto-scroll, and contextual footer
 * actions (cancel / retry / view server).
 */
const BuildProgressModal = React.forwardRef<
  HTMLDivElement,
  BuildProgressModalProps
>(({ open, onOpenChange, slug, onComplete, onError }, ref) => {
  const startBuild = useStartBuild(slug);
  const buildStatus = useBuildStatus(slug);
  const [events, setEvents] = React.useState<BuildStatusEvent[]>([]);
  const [hasBuiltOnce, setHasBuiltOnce] = React.useState(false);
  const [completed, setCompleted] = React.useState(false);
  const viewportRef = React.useRef<HTMLDivElement>(null);
  const startedRef = React.useRef(false);

  // ── Collect events ──────────────────────────────────────────────

  React.useEffect(() => {
    if (buildStatus.status) {
      setEvents((prev) => [...prev, buildStatus.status!]);
    }
  }, [buildStatus.status]);

  // ── Start / stop SSE on modal open / close ──────────────────────

  React.useEffect(() => {
    if (!open) {
      startedRef.current = false;
      setEvents([]);
      setHasBuiltOnce(false);
      setCompleted(false);
      buildStatus.stop();
      return;
    }

    // Guard against double-fires in Strict Mode
    if (startedRef.current) return;
    startedRef.current = true;

    setHasBuiltOnce(true);
    startBuild
      .mutateAsync()
      .then(() => {
        buildStatus.start();
      })
      .catch(() => {
        // Error is surfaced via `startBuild.error` or `buildStatus.error`
      });

    return () => {
      buildStatus.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, slug]);

  // ── Handle completion ───────────────────────────────────────────

  React.useEffect(() => {
    if (buildStatus.status?.stage === "complete" && !completed) {
      setCompleted(true);
      const timer = setTimeout(() => {
        onComplete();
      }, 1000);
      return () => clearTimeout(timer);
    }
    if (buildStatus.status?.stage === "error") {
      setCompleted(false);
      onError(buildStatus.status.message || "Build failed");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildStatus.status?.stage]);

  // ── Auto-scroll on new events ───────────────────────────────────

  React.useEffect(() => {
    if (viewportRef.current) {
      viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
    }
  }, [events]);

  // ── Derived state ───────────────────────────────────────────────

  const latestEvent = buildStatus.status;
  const isError = latestEvent?.stage === "error" || !!buildStatus.error;
  const isComplete = latestEvent?.stage === "complete";
  const isBuilding =
    hasBuiltOnce &&
    !isComplete &&
    !isError &&
    !(startBuild.isError && !startBuild.isPending);
  const isStartupError =
    startBuild.isError &&
    !startBuild.isPending &&
    events.length === 0;

  // ── Actions ─────────────────────────────────────────────────────

  const handleRetry = React.useCallback(() => {
    setEvents([]);
    setCompleted(false);
    setHasBuiltOnce(true);
    startBuild
      .mutateAsync()
      .then(() => {
        buildStatus.start();
      })
      .catch(() => {});
  }, [startBuild, buildStatus]);

  const handleCancel = React.useCallback(() => {
    buildStatus.stop();
    onOpenChange(false);
  }, [buildStatus, onOpenChange]);

  // ── Render ──────────────────────────────────────────────────────

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* Use max-w-2xl and flex column for full-height content */}
      <DialogContent
        ref={ref}
        className="sm:max-w-[640px] max-h-[90vh] flex flex-col gap-0 p-0"
      >
        {/* ── Header ── */}
        <div className="px-6 pt-6 pb-2">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl">
              <Sparkles className="h-5 w-5 text-primary" />
              Building your MCP server
            </DialogTitle>
            <DialogDescription>
              {isBuilding &&
                "Your server is being built. This usually takes a few seconds."}
              {isComplete && "Your MCP server is ready to use!"}
              {isError &&
                "Something went wrong during the build process."}
            </DialogDescription>
          </DialogHeader>
        </div>

        {/* ── Step indicator ── */}
        <div className="px-6 py-4 border-b border-border/50">
          <BuildStepIndicator currentStage={latestEvent?.stage} />
        </div>

        {/* ── Event log ── */}
        <ScrollArea className="max-h-[320px] min-h-[120px] flex-1 px-6 py-3">
          <div ref={viewportRef} className="space-y-0.5">
            {/* Empty / waiting state */}
            {events.length === 0 && isBuilding && (
              <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Waiting for build events...
              </div>
            )}

            {/* Startup error (before any SSE events) */}
            {isStartupError && (
              <Alert variant="destructive" className="mb-2">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Could not start build</AlertTitle>
                <AlertDescription>
                  {startBuild.error instanceof Error
                    ? startBuild.error.message
                    : "An unexpected error occurred. Please try again."}
                </AlertDescription>
              </Alert>
            )}

            {/* Events */}
            {events.map((event, idx) => (
              <EventRow key={idx} event={event} index={idx} />
            ))}
          </div>
        </ScrollArea>

        {/* ── Status alerts ── */}
        <div className="px-6 pb-1">
          {isError && events.length > 0 && !isStartupError && (
            <Alert variant="destructive" className="mb-2">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Build failed</AlertTitle>
              <AlertDescription>
                {latestEvent?.message ||
                  buildStatus.error?.message ||
                  "An unknown error occurred during the build."}
              </AlertDescription>
            </Alert>
          )}

          {isComplete && !isError && (
            <Alert
              variant="default"
              className="border-emerald-500/30 bg-emerald-500/5"
            >
              <Sparkles className="h-4 w-4 text-emerald-500" />
              <AlertTitle className="text-emerald-600 dark:text-emerald-400">
                Build complete
              </AlertTitle>
              <AlertDescription>
                Your MCP server is deployed and ready to use. You can now add
                it to any MCP-compatible client.
              </AlertDescription>
            </Alert>
          )}
        </div>

        {/* ── Footer ── */}
        <DialogFooter className="px-6 pb-6 pt-3">
          {isBuilding && (
            <Button variant="outline" onClick={handleCancel} className="gap-2">
              <AlertCircle className="h-4 w-4" />
              Cancel
            </Button>
          )}

          {isError && (
            <Button onClick={handleRetry} className="gap-2">
              <RotateCcw className="h-4 w-4" />
              Retry Build
            </Button>
          )}

          {isComplete && !isError && (
            <Button onClick={() => onOpenChange(false)} className="gap-2">
              <Sparkles className="h-4 w-4" />
              View Server
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});
BuildProgressModal.displayName = "BuildProgressModal";

export { BuildProgressModal };
export type { BuildProgressModalProps };
