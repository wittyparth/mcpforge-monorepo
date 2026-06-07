"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { CredentialCreateRequest, CredentialTestRequest } from "@/types/api";
import { toast } from "sonner";

/**
 * Fetch all credentials for a server by serverId.
 */
export function useCredentials(serverId: string) {
  return useQuery({
    queryKey: ["server", serverId, "credentials"],
    queryFn: () => api.servers.credentials.list(serverId),
    enabled: serverId.length > 0,
  });
}

/**
 * Create a new credential for a server.
 *
 * On success, invalidates the credentials query and shows a success toast.
 */
export function useCreateCredential(serverId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CredentialCreateRequest) =>
      api.servers.credentials.create(serverId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", serverId, "credentials"],
      });
      toast.success("Credential created successfully");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to create credential. Please try again.");
      }
    },
  });
}

/**
 * Test a credential by performing a dry-run request.
 *
 * Shows the result (success or failure) in a toast. Does NOT invalidate
 * queries since the test does not change server state.
 */
export function useTestCredential(serverId: string) {
  return useMutation({
    mutationFn: (input: CredentialTestRequest) =>
      api.servers.credentials.test(serverId, input),
    onSuccess: (result) => {
      if (result.success) {
        toast.success(`Connection successful (${result.latency_ms}ms)`);
      } else {
        toast.error(result.error ?? "Connection test failed");
      }
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to test credential. Please try again.");
      }
    },
  });
}

/**
 * Delete a credential from a server.
 *
 * Variables: the `envVarName` to delete.
 * On success, invalidates the credentials query and shows a success toast.
 */
export function useDeleteCredential(serverId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (envVarName: string) =>
      api.servers.credentials.delete(serverId, envVarName),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", serverId, "credentials"],
      });
      toast.success("Credential deleted successfully");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to delete credential. Please try again.");
      }
    },
  });
}
