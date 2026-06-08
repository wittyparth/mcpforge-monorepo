"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { toast } from "sonner";

export function useConnectPanel(serverId: string) {
  return useQuery({
    queryKey: ["server", serverId, "connect-panel"],
    queryFn: () => api.servers.getConnectPanel(serverId),
    enabled: serverId.length > 0,
  });
}

export function useTestConnection(serverId: string) {
  return useMutation({
    mutationFn: () => api.servers.testConnection(serverId),
    onSuccess: (data: any) => {
      if (data?.success) {
        toast.success("Connection successful!");
      } else {
        toast.error(data?.error ?? "Connection test failed");
      }
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Connection test failed");
    },
  });
}

export function usePauseServer(serverId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.servers.pause(serverId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["server", serverId] });
      toast.success("Server paused");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Failed to pause server");
    },
  });
}

export function useResumeServer(serverId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.servers.resume(serverId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["server", serverId] });
      toast.success("Server resumed");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Failed to resume server");
    },
  });
}

export function useDeployServer(serverId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.servers.deploy(serverId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["server", serverId] });
      toast.success("Deploy started");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) toast.error(error.message);
      else toast.error("Deploy failed");
    },
  });
}
