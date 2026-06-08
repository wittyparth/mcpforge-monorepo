/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, ApiClientError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { LoginRequest, RegisterRequest } from "@/types";
import { toast } from "sonner";

const CURRENT_USER_KEY = ["current-user"] as const;

/**
 * Fetch the current user on mount and sync with Zustand store.
 * Returns the same query result for use in components.
 */
export function useCurrentUser() {
  const { setUser, clear } = useAuthStore();

  const query = useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: async () => {
      try {
        const user = await api.auth.me();
        setUser(user);
        return user;
      } catch (error) {
        clear();
        throw error;
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  return query;
}

/**
 * Login mutation. On success, invalidates the current user query
 * and redirects to the dashboard.
 */
export function useLogin() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { setUser } = useAuthStore();

  return useMutation({
    mutationFn: (data: LoginRequest) => api.auth.login(data),
    onSuccess: (response) => {
      setUser(response as any);
      void queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY });
      toast.success("Welcome back!");
      router.push("/dashboard");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Login failed. Please try again.");
      }
    },
  });
}

/**
 * Register mutation. On success, invalidates the current user query
 * and redirects to the dashboard.
 */
export function useRegister() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { setUser } = useAuthStore();

  return useMutation({
    mutationFn: (data: RegisterRequest) => api.auth.register(data),
    onSuccess: (response) => {
      setUser(response as any);
      void queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY });
      toast.success("Account created successfully!");
      router.push("/dashboard");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
      } else {
        toast.error("Registration failed. Please try again.");
      }
    },
  });
}

/**
 * Logout mutation. On success, clears auth state and redirects to home.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { clear } = useAuthStore();

  return useMutation({
    mutationFn: () => api.auth.logout(),
    onSettled: () => {
      clear();
      void queryClient.invalidateQueries({ queryKey: CURRENT_USER_KEY });
      void queryClient.clear();
      toast.success("Logged out successfully");
      router.push("/");
    },
  });
}
