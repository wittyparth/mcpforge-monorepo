"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { toast } from "sonner";

export function useScan(serverId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.servers.security.scan(serverId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", serverId, "security"],
      });
      toast.success("Security scan started");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Failed to start security scan");
    },
  });
}

export function useLatestScan(serverId: string) {
  return useQuery({
    queryKey: ["server", serverId, "security", "latest"],
    queryFn: () => api.servers.security.getLatest(serverId),
    enabled: serverId.length > 0,
    staleTime: 30_000,
  });
}

export function useAcknowledgeFinding(serverId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ findingId, note }: { findingId: string; note?: string }) =>
      api.servers.security.acknowledge(serverId, findingId, note),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", serverId, "security"],
      });
      toast.success("Finding acknowledged");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Failed to acknowledge finding");
    },
  });
}

export function useRemoveAcknowledgment(serverId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (findingId: string) =>
      api.servers.security.removeAcknowledge(serverId, findingId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["server", serverId, "security"],
      });
      toast.success("Acknowledgment removed");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Failed to remove acknowledgment");
    },
  });
}

export function useScanHistory(serverId: string, page = 1) {
  return useQuery({
    queryKey: ["server", serverId, "security", "history", page],
    queryFn: () => api.servers.security.getHistory(serverId, page),
    enabled: serverId.length > 0,
  });
}

export function useAcknowledgmentList(serverId: string) {
  return useQuery({
    queryKey: ["server", serverId, "security", "acks"],
    queryFn: () => api.servers.security.getAcks(serverId),
    enabled: serverId.length > 0,
  });
}
