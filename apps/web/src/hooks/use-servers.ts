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
    onSuccess: (server) => {
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
