/**
 * Configure the generated SDK (base URL, credentials, CSRF token).
 *
 * Import this file once at the app entry point or in the API client module
 * to set up the OpenAPI config BEFORE making any SDK calls.
 */

import { OpenAPI } from "../client/core/OpenAPI";
import type { AxiosRequestConfig } from "axios";

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
