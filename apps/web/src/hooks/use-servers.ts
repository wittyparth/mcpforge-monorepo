"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, ApiClientError } from "@/lib/api";
import type { CreateServerRequest } from "@/types";
import { toast } from "sonner";

const SERVERS_KEY = ["servers"] as const;

/**
 * Fetch paginated server list.
 */
export function useServers(page = 1) {
  return useQuery({
    queryKey: [...SERVERS_KEY, page],
    queryFn: () => api.servers.list(page),
  });
}

/**
 * Fetch a single server by ID.
 */
export function useServer(id: string) {
  return useQuery({
    queryKey: [...SERVERS_KEY, id],
    queryFn: () => api.servers.get(id),
    enabled: id.length > 0,
  });
}

/**
 * Create a new server mutation.
 * On success, invalidates the server list and redirects to the new server.
 */
export function useCreateServer() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: (data: CreateServerRequest) => api.servers.create(data),
    onSuccess: (// eslint-disable-next-line @typescript-eslint/no-explicit-any
  server: any) => {
      void queryClient.invalidateQueries({ queryKey: SERVERS_KEY });
      toast.success("Server created successfully!");
      router.push(`/dashboard/servers/${server.id}`);
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to create server. Please try again.");
      }
    },
  });
}

/**
 * Update a server mutation.
 * On success, invalidates the server query and shows a success toast.
 */
export function useUpdateServer(serverId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.servers.update(serverId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...SERVERS_KEY, serverId] });
      void queryClient.invalidateQueries({ queryKey: SERVERS_KEY });
      toast.success("Server configuration updated");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to update server. Please try again.");
      }
    },
  });
}

export function useDuplicateServer() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: { new_name: string; new_slug?: string | null };
    }) => api.servers.duplicate(id, data),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onSuccess: (server: any) => {
      void queryClient.invalidateQueries({ queryKey: SERVERS_KEY });
      toast.success("Server duplicated successfully!");
      router.push(`/dashboard/servers/${server.id}`);
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to duplicate server. Please try again.");
      }
    },
  });
}

export function useVersions(
  serverId: string,
  params?: { skip?: number; limit?: number },
) {
  return useQuery({
    queryKey: ["server-versions", serverId, params],
    queryFn: () => api.servers.listVersions(serverId, params),
    enabled: !!serverId,
  });
}

export function useRollback(serverId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { version: number }) =>
      api.servers.rollback(serverId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [...SERVERS_KEY, serverId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["server-versions", serverId],
      });
      toast.success("Server rolled back successfully!");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Failed to rollback server. Please try again.");
      }
    },
  });
}
