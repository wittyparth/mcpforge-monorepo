// Auth helpers for server components and middleware
// The actual auth state lives in the Zustand store (client-side).
// This module provides helpers for checking auth in server components.

import type { User } from "@/types";
import { api } from "./api";

/**
 * Fetch the current user from the backend.
 * Can be called from server components because fetch with
 * `credentials: 'include'` will forward cookies.
 *
 * Returns the user or null if not authenticated.
 */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const user = await api.auth.me();
    return user;
  } catch {
    return null;
  }
}

/**
 * Check if the user is authenticated.
 * Used in layout components to gate access to dashboard routes.
 */
export async function isAuthenticated(): Promise<boolean> {
  const user = await getCurrentUser();
  return user !== null;
}
