"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { ToolListResponse, ToolUpdateRequest } from "@/types/api";
import { toast } from "sonner";

/**
 * Fetch all tools for a server by slug.
 */
export function useTools(slug: string) {
  return useQuery({
    queryKey: ["server", slug, "tools"],
    queryFn: () => api.servers.tools.list(slug),
    enabled: slug.length > 0,
  });
}

/**
 * Update a single tool on a server.
 *
 * Variables: `{ name: string } & ToolUpdateRequest`
 * - `name` is the tool name (used in the URL path)
 * - The remaining fields are the update payload
 *
 * On success, invalidates the tools query and shows a success toast.
 */
export function useUpdateTool(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (variables: { name: string } & ToolUpdateRequest) => {
      const { name, ...updates } = variables;
      return api.servers.tools.update(slug, name, updates);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", slug, "tools"],
      });
      toast.success("Tool updated successfully");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to update tool. Please try again.");
      }
    },
  });
}

/**
 * Trigger AI-powered tool description enhancement (F2 stub).
 *
 * The backend returns 501 (NotImplementedFeatureError) — this is
 * handled gracefully with an info toast instead of an error.
 */
export function useEnhanceTools(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.servers.tools.enhance(slug),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", slug, "tools"],
      });
      toast.success("Tools enhanced successfully");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError && error.status === 501) {
        toast.info("AI enhancement coming soon");
      } else if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to enhance tools. Please try again.");
      }
    },
  });
}
