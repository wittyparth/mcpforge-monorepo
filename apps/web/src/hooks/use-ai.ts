"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { toast } from "sonner";

/**
 * Trigger AI enhancement of all (or specified) tool descriptions.
 *
 * Sends a request to the AI Description Engine to rewrite tool descriptions
 * for maximum LLM selection probability. Optionally specify which tools
 * to enhance and whether to force re-enhancement.
 */
export function useEnhanceTools(serverId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data?: { tool_names?: string[]; force?: boolean }) =>
      api.servers.tools.enhance(serverId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", serverId, "tools"],
      });
      toast.success("AI enhancement started");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        if (error.status === 402) toast.error("Insufficient AI credits");
        else if (error.status === 409)
          toast.error("Enhancement already in progress");
        else toast.error(error.message);
      } else {
        toast.error("Failed to start AI enhancement");
      }
    },
  });
}

/**
 * Trigger AI enhancement of a single tool by name.
 *
 * Rewrites the description for one specific tool without affecting others.
 */
export function useEnhanceSingleTool(serverId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (toolName: string) =>
      api.servers.tools.enhanceSingle(serverId, toolName),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", serverId, "tools"],
      });
      toast.success("Tool enhancement started");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Failed to enhance tool");
    },
  });
}

/**
 * Accept AI-enhanced tool descriptions (all or subset).
 *
 * After reviewing AI proposals, accept the ones you want and optionally
 * reject or provide custom edits for others.
 */
export function useAcceptTools(serverId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      accepted_tools: string[];
      rejected_tools?: string[];
      custom_edits?: Record<string, Record<string, unknown>>;
    }) => api.servers.tools.accept(serverId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", serverId, "tools"],
      });
      void queryClient.invalidateQueries({ queryKey: ["server", serverId] });
      toast.success("Tool descriptions updated");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Failed to accept tools");
    },
  });
}
