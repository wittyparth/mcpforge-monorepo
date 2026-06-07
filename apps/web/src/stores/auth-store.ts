import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  /** The current authenticated user, or null if not logged in */
  user: User | null;
  /** Whether we've checked the auth status with the backend */
  isLoaded: boolean;
  /** Whether a login/register request is in flight */
  isLoading: boolean;

  setUser: (user: User | null) => void;
  setLoaded: (loaded: boolean) => void;
  setLoading: (loading: boolean) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  isLoaded: false,
  isLoading: false,

  setUser: (user) => set({ user, isLoaded: true }),
  setLoaded: (loaded) => set({ isLoaded: loaded }),
  setLoading: (loading) => set({ isLoading: loading }),
  clear: () => set({ user: null, isLoaded: true, isLoading: false }),
}));
