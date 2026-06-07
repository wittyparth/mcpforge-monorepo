"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { useCallback, useEffect, useRef, useState } from "react";
import type { BuildStatusEvent } from "@/types/api";
import { toast } from "sonner";

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
 * - `status`: The latest `BuildStatusEvent` (null before any event)
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
      for await (const event of api.servers.build.getStatus(
        serverId,
        controller.signal,
      )) {
        setStatus(event);

        if (event.stage === "complete") {
          setIsStreaming(false);
          toast.success("Build completed successfully");
        } else if (event.stage === "error") {
          setIsStreaming(false);
          toast.error(event.message || "Build failed");
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
