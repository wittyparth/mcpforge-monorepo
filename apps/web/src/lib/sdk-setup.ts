/**
 * Configure the generated SDK (base URL, credentials, CSRF token, auth refresh).
 *
 * Import this file once at the app entry point or in the API client module
 * to set up the OpenAPI config BEFORE making any SDK calls.
 */

import { OpenAPI } from "../client/core/OpenAPI";
import type { AxiosRequestConfig, AxiosResponse } from "axios";
import { attemptTokenRefresh } from "./auth-refresh";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

OpenAPI.BASE = API_URL;
OpenAPI.VERSION = "0.1.0";
OpenAPI.WITH_CREDENTIALS = true;
OpenAPI.CREDENTIALS = "include";

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1] ?? "") : null;
}

const CSRF_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

OpenAPI.interceptors.request.use(async (config: AxiosRequestConfig) => {
  if (config.method && CSRF_METHODS.has(config.method.toUpperCase())) {
    const csrf = getCookie("csrf_token");
    if (csrf) {
      config.headers = { ...config.headers, "X-CSRF-Token": csrf };
    }
  }
  return config;
});

// ── Response interceptor: auto-refresh on 401 ─────────────────────────
// When any SDK call returns 401, try to refresh the access token via
// POST /api/v1/auth/refresh. If the refresh succeeds, the backend sets
// new cookies and we dispatch a "auth:refreshed" event so the app can
// re-fetch the current user. If the refresh fails, dispatch "auth:expired".
//
// NOTE: The SDK's response interceptor is read-only — it cannot retry the
// original request. Callers should use TanStack Query's `retry` option or
// handle the retry at the hook level. The interceptor ensures the token is
// fresh before the retry happens.
OpenAPI.interceptors.response.use(async (response: AxiosResponse) => {
  if (response.status === 401) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("auth:refreshed"));
      }
    }
  }
  return response;
});
