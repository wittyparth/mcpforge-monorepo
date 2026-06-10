/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { SpecFetchRequest, ToolSelectionRequest } from "@/types/api";
import { toast } from "sonner";

const SPEC_KEY = ["spec"] as const;

/**
 * Fetch a single spec by ID.
 * Returns SpecSource or null when no id is provided.
 */
export function useSpec(id?: string) {
  return useQuery({
    queryKey: [...SPEC_KEY, id],
    queryFn: () => api.specs.getById(id!),
    enabled: !!id,
  });
}

/**
 * Fetch tools for a spec by ID.
 * Returns SpecToolListResponse or null when no id is provided.
 */
export function useSpecTools(id?: string) {
  return useQuery({
    queryKey: [...SPEC_KEY, id, "tools"],
    queryFn: () => api.specs.getTools(id!),
    enabled: !!id,
  });
}

/**
 * Fetch a spec from a URL mutation.
 * On success, invalidates all ["spec"] prefixed queries.
 */
export function useFetchSpec() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: SpecFetchRequest) => api.specs.fetch(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SPEC_KEY });
      toast.success("Spec fetched successfully");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError && error.body) {
        const body =
          typeof error.body === "string"
            ? JSON.parse(error.body)
            : error.body;
        const detail = body?.error?.message ?? body?.detail ?? error.message;
        toast.error(detail);
      } else if (error instanceof Error) {
        toast.error(error.message);
      } else {
        toast.error("Failed to fetch spec. Please try again.");
      }
    },
  });
}

/**
 * Upload a spec file mutation (FormData).
 * On success, invalidates all ["spec"] prefixed queries.
 */
export function useUploadSpec() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => api.specs.upload(file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SPEC_KEY });
      toast.success("Spec uploaded successfully");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to upload spec. Please try again.");
      }
    },
  });
}

/**
 * Delete a spec by ID mutation.
 * On success, invalidates all ["spec"] prefixed queries.
 */
export function useDeleteSpec() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.specs.delete(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SPEC_KEY });
      toast.success("Spec deleted successfully");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to delete spec. Please try again.");
      }
    },
  });
}

/**
 * Select tools for a spec and create an MCP server mutation.
 * On success, invalidates the ["server", slug] query for the server slug
 * returned in the response.
 */
export function useSelectTools(specId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (selection: ToolSelectionRequest) =>
      api.specs.selectTools(specId, selection),
    onSuccess: (server: any) => {
      void queryClient.invalidateQueries({ queryKey: ["server", server.id] });
      toast.success("Tools selected successfully");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to select tools. Please try again.");
      }
    },
  });
}
