"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { useCallback, useEffect, useRef, useState } from "react";
import type { BuildStatusEvent, BuildStage } from "@/types/api";
import { toast } from "sonner";

/**
 * Map a raw backend event name to a UI BuildStage.
 *
 * The AI Description Engine emits:
 *   start, ai_progress, tool_enhanced, tool_failed, ai_complete, done, error
 *
 * We map these to the legacy pipeline stages so the stepper works:
 *   parsing    → fetching spec / starting
 *   generating → AI enhancement (ai_progress, tool_enhanced, tool_failed)
 *   testing    → AI complete / quality review
 *   deploying  → finalizing / done
 *   complete   → finished
 *   error      → error
 */
function eventToStage(event: string): BuildStage {
  switch (event) {
    case "start":
      return "parsing";
    case "ai_progress":
    case "tool_enhanced":
    case "tool_failed":
      return "generating";
    case "ai_complete":
      return "testing";
    case "done":
      return "deploying";
    case "complete":
      return "complete";
    case "error":
      return "error";
    default:
      return "parsing";
  }
}

/**
 * Generate a human-readable message for an event if the backend didn't provide one.
 */
function deriveMessage(ev: BuildStatusEvent): string {
  const e = ev.event ?? "";
  const tool = ev.tool_name ? ` "${ev.tool_name}"` : "";
  switch (e) {
    case "start":
      return `Starting AI enhancement for ${ev.total ?? 0} tools…`;
    case "ai_progress":
      return `Enhancing tool${tool} (${ev.progress ?? 0} of ${ev.total ?? 0})…`;
    case "tool_enhanced":
      return `Enhanced tool${tool} (quality score: ${ev.quality_score ?? "N/A"})`;
    case "tool_failed":
      return `Failed to enhance tool${tool}: ${ev.error ?? "Unknown error"}`;
    case "ai_complete":
      return `AI enhancement complete: ${ev.successful ?? 0} successful, ${ev.failed ?? 0} failed`;
    case "done":
      return "Finalizing server deployment…";
    case "error":
      return ev.error ?? ev.message ?? "An error occurred during the build";
    default:
      return ev.message ?? `Event: ${e}`;
  }
}

/**
 * Compute a 0–100 progress percentage from an event.
 */
function computeProgress(ev: BuildStatusEvent): number {
  const e = ev.event ?? "";
  const total = ev.total ?? 0;
  const progress = ev.progress ?? 0;

  if (e === "start" || e === "parsing") return 5;
  if (e === "ai_progress" || e === "tool_enhanced" || e === "tool_failed") {
    if (total > 0) return Math.min(95, Math.round((progress / total) * 90));
    return 50;
  }
  if (e === "ai_complete") return 95;
  if (e === "done" || e === "deploying") return 98;
  if (e === "complete") return 100;
  if (e === "error") return 0;
  return ev.progress ?? 0;
}

/**
 * Normalize a raw SSE event into a fully-populated BuildStatusEvent.
 */
function normalizeEvent(raw: BuildStatusEvent): BuildStatusEvent {
  const event = raw.event ?? raw.stage ?? "";
  const stage = raw.stage ?? eventToStage(event);
  const progress = raw.progress !== undefined ? raw.progress : computeProgress(raw);
  const message = raw.message ?? deriveMessage(raw);

  return {
    ...raw,
    stage,
    event,
    progress: computeProgress({ ...raw, stage, event, progress }),
    message,
  };
}

/**
 * Start a server build.
 *
 * On success, invalidates server-level queries and shows a success toast.
 */
export function useStartBuild(serverId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.servers.build.start(serverId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["server", serverId] });
      toast.success("Build started");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to start build. Please try again.");
      }
    },
  });
}

/**
 * Subscribe to SSE build status updates for a server.
 *
 * This hook does NOT auto-start on mount. The component must call `start()`
 * when the user triggers a build. The `stop()` function or unmounting
 * cancels the subscription by aborting the underlying fetch.
 *
 * Returns:
 * - `status`: The latest normalized BuildStatusEvent (null before any event)
 * - `isStreaming`: Whether the SSE connection is active
 * - `error`: Any connection error
 * - `start`: Call to begin listening for status events
 * - `stop`: Call to abort the subscription
 */
export function useBuildStatus(serverId: string) {
  const [status, setStatus] = useState<BuildStatusEvent | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    setIsStreaming(true);
    setError(null);
    setStatus(null);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const rawEvent of api.servers.build.getStatus(
        serverId,
        controller.signal,
      )) {
        const normalized = normalizeEvent(rawEvent);
        setStatus(normalized);

        const eventType = normalized.event ?? "";
        if (
          eventType === "complete" ||
          eventType === "ai_complete" ||
          eventType === "done"
        ) {
          setIsStreaming(false);
          toast.success("Build completed successfully");
        } else if (eventType === "error") {
          setIsStreaming(false);
          toast.error(normalized.message || "Build failed");
        }
      }
    } catch (e) {
      if (!controller.signal.aborted) {
        setError(e as Error);
        setIsStreaming(false);
        toast.error("Build status connection lost");
      }
    }
  }, [serverId]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { status, isStreaming, error, start, stop };
}
