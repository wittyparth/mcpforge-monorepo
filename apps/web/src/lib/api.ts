/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Auto-generated API client — thin re-export of SDK.
 *
 * Regenerate with: ``pnpm generate-client``
 */

import "@/lib/sdk-setup";

export { ApiError as ApiClientError } from "../client/core/ApiError";

import {
  AuthService,
  ServersService,
  SpecsService,
  ToolsService,
  CredentialsService,
  BuildService,
} from "../client/sdk.gen";

export {
  AuthService,
  ServersService,
  SpecsService,
  ToolsService,
  CredentialsService,
  BuildService,
};

export type {
  UserResponse,
  AuthResponse,
  MCPServerResponse,
  SpecUploadResponse,
  CredentialResponse,
  CredentialListResponse,
  CredentialTestResponse,
  ToolListResponse,
} from "../client/types.gen";

import type { BuildStatusEvent } from "@/types/api";
import { attemptTokenRefresh } from "./auth-refresh";

/**
 * Read a cookie value by name.
 */
function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1] ?? "") : null;
}

const CSRF_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Thin wrapper around `fetch` that:
 * 1. Attaches the CSRF token header to state-changing methods
 * 2. Auto-retries on 401 by attempting a token refresh first
 *
 * Use this instead of raw `fetch()` for any request that bypasses the
 * generated SDK (SSE is excluded — it uses its own reader).
 *
 * The generated SDK (`sdk.gen.ts`) handles CSRF via its own interceptor
 * in `sdk-setup.ts`. This helper is for raw fetch calls only.
 */
async function fetchWithCSRF(
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers ?? {});

  if (CSRF_METHODS.has(method)) {
    const csrf = getCookie("csrf_token");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  let response = await fetch(url, { ...init, headers });

  if (response.status === 401) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      response = await fetch(url, { ...init, headers });
    }
  }

  return response;
}

/**
 * SSE build-status stream.
 * The SDK doesn't natively support SSE endpoints, so we use the Fetch API.
 */
export async function* buildStatusStream(
  id: string,
  signal?: AbortSignal,
): AsyncIterable<BuildStatusEvent> {
  const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/build-status`;
  const response = await fetch(url, { credentials: "include", signal });
  if (!response.ok) throw new Error(`SSE failed: ${response.status}`);
  if (!response.body) throw new Error("SSE: no body");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try { yield JSON.parse(line.slice(6)) as BuildStatusEvent; }
          catch { /* skip malformed */ }
        }
      }
    }
  } finally { reader.releaseLock(); }
}

/**
 * Convenience namespace for call sites that prefer ``api.xxx.yyy()``
 * syntax over static-method imports.  Every method here delegates
 * directly to the generated SDK.
 */
export const api = {
  auth: {
    login: (data: any) => AuthService.login({ requestBody: data }) as any,
    register: (data: any) => AuthService.register({ requestBody: data }) as any,
    logout: () => AuthService.logout({}) as any,
    me: () => AuthService.getMe({}) as any,
    refresh: () => AuthService.refreshToken({}) as any,
    forgotPassword: (email: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/forgot-password`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to send reset email");
          });
        }
      });
    },
    resetPassword: (token: string, password: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/reset-password`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to reset password");
          });
        }
      });
    },
    verifyEmail: (token: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/verify-email`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to verify email");
          });
        }
        return r.json();
      });
    },
    resendVerification: () => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/resend-verification`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to resend verification email");
          });
        }
      });
    },
  },
  servers: {
    list: (page = 1, pageSize = 20) =>
      ServersService.listServers({ skip: (page - 1) * pageSize, limit: pageSize } as any) as any,
    get: (id: string) => ServersService.getServer({ serverId: id } as any) as any,
    create: (data: any) => ServersService.createServer({ requestBody: data } as any) as any,
    update: (id: string, data: any) => ServersService.updateServer({ serverId: id, requestBody: data } as any) as any,
    delete: (id: string) => ServersService.deleteServer({ serverId: id } as any) as any,
    tools: {
      list: (id: string) => ToolsService.listTools({ serverId: id } as any) as any,
      update: (id: string, tn: string, u: any) => ToolsService.updateTool({ serverId: id, toolName: tn, requestBody: u } as any) as any,
      enhance: (id: string, data?: { tool_names?: string[]; force?: boolean }) =>
        ToolsService.enhanceTools({ serverId: id, requestBody: data ?? {} } as any) as any,
      enhanceSingle: (id: string, name: string) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/tools/${encodeURIComponent(name)}/enhance`;
        return fetchWithCSRF(url, { method: "POST", credentials: "include" }).then((r) => {
          if (!r.ok) throw new Error(`Enhance failed: ${r.status}`);
          return r.json();
        });
      },
      accept: (id: string, data: { accepted_tools: string[]; rejected_tools?: string[]; custom_edits?: Record<string, Record<string, unknown>> }) =>
        BuildService.acceptAiEnhancements({ serverId: id, requestBody: data } as any) as any,
    },
    credentials: {
      create: (id: string, i: any) => CredentialsService.addCredential({ serverId: id, requestBody: i } as any) as any,
      list: (id: string) => CredentialsService.listCredentials({ serverId: id } as any) as any,
      test: (id: string, i: any) => CredentialsService.testCredential({ serverId: id, requestBody: i } as any) as any,
      delete: (id: string, e: string) => CredentialsService.deleteCredential({ serverId: id, envVarName: e } as any) as any,
    },
    build: {
      start: (id: string) => BuildService.startBuild({ serverId: id } as any) as any,
      getStatus: (id: string, signal?: AbortSignal) => buildStatusStream(id, signal),
    },
    duplicate: (id: string, data: { new_name: string; new_slug?: string | null }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/duplicate`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to duplicate server");
          });
        }
        return r.json();
      });
    },
    listVersions: (id: string, params?: { skip?: number; limit?: number }) => {
      const searchParams = new URLSearchParams();
      if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
      if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
      const qs = searchParams.toString();
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/versions${qs ? `?${qs}` : ""}`;
      return fetch(url, { credentials: "include" }).then((r) => {
        if (!r.ok) throw new Error(`list versions failed: ${r.status}`);
        return r.json();
      });
    },
    rollback: (id: string, data: { version: number }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/rollback`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to rollback server");
          });
        }
        return r.json();
      });
    },
    getConnectPanel: (id: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/connect`;
      return fetch(url, { credentials: "include" }).then(r => { if (!r.ok) throw new Error(`connect panel failed: ${r.status}`); return r.json(); });
    },
    testConnection: (id: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/connect/test`;
      return fetchWithCSRF(url, { method: "POST", credentials: "include" }).then(r => { if (!r.ok) throw new Error(`test connection failed: ${r.status}`); return r.json(); });
    },
    deploy: (id: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/deploy`;
      return fetchWithCSRF(url, { method: "POST", credentials: "include" }).then(r => { if (!r.ok) throw new Error(`deploy failed: ${r.status}`); return r.json(); });
    },
    pause: (id: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/pause`;
      return fetchWithCSRF(url, { method: "POST", credentials: "include" }).then(r => { if (!r.ok) throw new Error(`pause failed: ${r.status}`); return r.json(); });
    },
    resume: (id: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${id}/resume`;
      return fetchWithCSRF(url, { method: "POST", credentials: "include" }).then(r => { if (!r.ok) throw new Error(`resume failed: ${r.status}`); return r.json(); });
    },
    security: {
      scan: (serverId: string) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/security/scan`;
        return fetchWithCSRF(url, { method: "POST", credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`scan failed: ${r.status}`);
          return r.json();
        });
      },
      getLatest: (serverId: string) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/security/latest`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`latest scan failed: ${r.status}`);
          return r.json();
        });
      },
      getHistory: (serverId: string, page = 1, pageSize = 20) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/security/scans?page=${page}&page_size=${pageSize}`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`scan history failed: ${r.status}`);
          return r.json();
        });
      },
      acknowledge: (serverId: string, findingId: string, note?: string | null) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/security/${encodeURIComponent(findingId)}/acknowledge`;
        return fetchWithCSRF(url, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note }) }).then(r => {
          if (!r.ok) throw new Error(`acknowledge failed: ${r.status}`);
          return r.json();
        });
      },
      removeAcknowledge: (serverId: string, findingId: string) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/security/${encodeURIComponent(findingId)}/acknowledge`;
        return fetchWithCSRF(url, { method: "DELETE", credentials: "include" }).then(r => {
          if (!r.ok && r.status !== 204) throw new Error(`remove acknowledge failed: ${r.status}`);
          return r.status === 204 ? null : r.json();
        });
      },
      getAcks: (serverId: string) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/security/acknowledgments`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`get acks failed: ${r.status}`);
          return r.json();
        });
      },
      exportReport: (serverId: string) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/security/report.json`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`export report failed: ${r.status}`);
          return r.json();
        });
      },
    },
    playground: {
      shareTest: (slug: string, data: { tool_name: string; parameters: Record<string, any> }) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${slug}/playground/share`;
        return fetchWithCSRF(url, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }).then(r => {
          if (!r.ok) {
            return r.json().then((body: { detail?: string }) => {
              throw new Error(body.detail ?? "Failed to share playground test");
            });
          }
          return r.json();
        });
      },
    },
    analytics: {
      overview: (serverId: string, range: "7d" | "30d" | "90d" = "7d") => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/analytics?range=${range}`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`overview failed: ${r.status}`);
          return r.json();
        });
      },
      tools: (serverId: string, range: "7d" | "30d" | "90d" = "7d") => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/analytics/tools?range=${range}`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`tools breakdown failed: ${r.status}`);
          return r.json();
        });
      },
      errors: (serverId: string, range: "7d" | "30d" | "90d" = "7d", limit = 100, offset = 0) => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/analytics/errors?range=${range}&limit=${limit}&offset=${offset}`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`errors failed: ${r.status}`);
          return r.json();
        });
      },
      clients: (serverId: string, range: "7d" | "30d" | "90d" = "7d") => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/analytics/clients?range=${range}`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`clients failed: ${r.status}`);
          return r.json();
        });
      },
      timeseries: (serverId: string, range: "7d" | "30d" | "90d" = "7d", granularity: "hour" | "day" = "hour") => {
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/analytics/timeseries?range=${range}&granularity=${granularity}`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`timeseries failed: ${r.status}`);
          return r.json();
        });
      },
      exportCsvUrl: (serverId: string, range: "7d" | "30d" | "90d" = "7d") =>
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/analytics/export.csv?range=${range}`,
      descriptionPerformance: (serverId: string, toolName?: string) => {
        const params = new URLSearchParams();
        if (toolName) params.set("tool_name", toolName);
        const qs = params.toString();
        const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/servers/${serverId}/analytics/description-performance${qs ? `?${qs}` : ""}`;
        return fetch(url, { credentials: "include" }).then(r => {
          if (!r.ok) throw new Error(`description performance failed: ${r.status}`);
          return r.json();
        });
      },
    },
  },
  specs: {
    fetch: (d: any) => SpecsService.fetchSpec({ requestBody: d } as any) as any,
    upload: (f: File) => SpecsService.uploadSpec({ formData: { file: f } } as any) as any,
    getById: (id: string) => SpecsService.getSpec({ specId: id } as any) as any,
    getTools: (id: string) => SpecsService.getSpecTools({ specId: id } as any) as any,
    delete: (id: string) => SpecsService.deleteSpec({ specId: id } as any) as any,
    selectTools: (id: string, s: any) => SpecsService.selectTools({ specId: id, requestBody: s } as any) as any,
  },
  team: {
    get: () => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team`;
      return fetch(url, { credentials: "include" }).then((r) => {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error(`get team failed: ${r.status}`);
        return r.json();
      });
    },
    create: (data: { name: string }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) throw new Error(`create team failed: ${r.status}`);
        return r.json();
      });
    },
    update: (data: { name?: string }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team`;
      return fetchWithCSRF(url, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) throw new Error(`update team failed: ${r.status}`);
        return r.json();
      });
    },
    invite: (data: { email: string; role: string }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team/invite`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) throw new Error(`invite failed: ${r.status}`);
        return r.json();
      });
    },
    accept: (data: { token: string }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team/accept`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) throw new Error(`accept invitation failed: ${r.status}`);
        return r.json();
      });
    },
    listMembers: () => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team/members`;
      return fetch(url, { credentials: "include" }).then((r) => {
        if (!r.ok) throw new Error(`list members failed: ${r.status}`);
        return r.json();
      });
    },
    updateMember: (userId: string, data: { role: string }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team/members/${userId}`;
      return fetchWithCSRF(url, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) throw new Error(`update member failed: ${r.status}`);
        return r.json();
      });
    },
    removeMember: (userId: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team/members/${userId}`;
      return fetchWithCSRF(url, {
        method: "DELETE",
        credentials: "include",
      }).then((r) => {
        if (!r.ok && r.status !== 204) throw new Error(`remove member failed: ${r.status}`);
      });
    },
    auditLog: (params?: { skip?: number; limit?: number; action?: string }) => {
      const searchParams = new URLSearchParams();
      if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
      if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
      if (params?.action) searchParams.set("action", params.action);
      const qs = searchParams.toString();
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/team/audit-log${qs ? `?${qs}` : ""}`;
      return fetch(url, { credentials: "include" }).then((r) => {
        if (!r.ok) throw new Error(`audit log failed: ${r.status}`);
        return r.json();
      });
    },
  },
  apiKeys: {
    list: (params?: { include_revoked?: boolean }) => {
      const searchParams = new URLSearchParams();
      if (params?.include_revoked !== undefined) {
        searchParams.set("include_revoked", String(params.include_revoked));
      }
      const qs = searchParams.toString();
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/api-keys${qs ? `?${qs}` : ""}`;
      return fetch(url, { credentials: "include" }).then((r) => {
        if (!r.ok) throw new Error(`list api keys failed: ${r.status}`);
        return r.json();
      });
    },
    create: (data: {
      name: string;
      scopes: string[];
      expires_in_days?: number | null;
    }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/api-keys`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to create API key");
          });
        }
        return r.json();
      });
    },
    revoke: (id: string) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/api-keys/${id}`;
      return fetchWithCSRF(url, {
        method: "DELETE",
        credentials: "include",
      }).then((r) => {
        if (!r.ok && r.status !== 204) {
          throw new Error(`revoke api key failed: ${r.status}`);
        }
      });
    },
  },
  billing: {
    listPlans: () => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/billing/plans`;
      return fetch(url, { credentials: "include" }).then((r) => {
        if (!r.ok) throw new Error(`list plans failed: ${r.status}`);
        return r.json();
      });
    },
    getSubscription: () => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/billing/subscription`;
      return fetch(url, { credentials: "include" }).then((r) => {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error(`get subscription failed: ${r.status}`);
        return r.json();
      });
    },
    listInvoices: (params?: { skip?: number; limit?: number }) => {
      const searchParams = new URLSearchParams();
      if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
      if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
      const qs = searchParams.toString();
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/billing/invoices${qs ? `?${qs}` : ""}`;
      return fetch(url, { credentials: "include" }).then((r) => {
        if (!r.ok) throw new Error(`list invoices failed: ${r.status}`);
        return r.json();
      });
    },
    subscribe: (data: {
      plan: "pro" | "team";
      billing_period: "monthly" | "yearly";
      seats?: number;
    }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/billing/subscribe`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to create checkout session");
          });
        }
        return r.json();
      });
    },
    openPortal: (data?: { return_url?: string }) => {
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/billing/portal`;
      return fetchWithCSRF(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data ?? {}),
      }).then((r) => {
        if (!r.ok) {
          return r.json().then((body: { detail?: string }) => {
            throw new Error(body.detail ?? "Failed to open billing portal");
          });
        }
        return r.json();
      });
    },
  },
};
