"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiKeyCreateResponse, ApiKeyListResponse } from "@/types/api";

const API_KEYS_KEY = ["api-keys"] as const;

export function useApiKeys(params?: { include_revoked?: boolean }) {
  return useQuery({
    queryKey: [...API_KEYS_KEY, params],
    queryFn: () => api.apiKeys.list(params) as Promise<ApiKeyListResponse>,
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      name: string;
      scopes: string[];
      expires_in_days?: number | null;
    }) => api.apiKeys.create(data) as Promise<ApiKeyCreateResponse>,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_KEY });
    },
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.apiKeys.revoke(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: API_KEYS_KEY });
    },
  });
}
