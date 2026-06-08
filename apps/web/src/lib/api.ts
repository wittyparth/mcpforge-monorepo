/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Auto-generated API client — thin re-export of SDK.
 *
 * Regenerate with: ``pnpm generate-client``
 */

import "../client/setup";

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
  },
  servers: {
    list: (page = 1, pageSize = 20) =>
      ServersService.listServers({ skip: (page - 1) * pageSize, limit: pageSize } as any) as any,
    get: (id: string) => ServersService.getServer({ server_id: id } as any) as any,
    create: (data: any) => ServersService.createServer({ requestBody: data } as any) as any,
    update: (id: string, data: any) => ServersService.updateServer({ server_id: id, requestBody: data } as any) as any,
    delete: (id: string) => ServersService.deleteServer({ server_id: id } as any) as any,
    tools: {
      list: (id: string) => ToolsService.listTools({ server_id: id } as any) as any,
      update: (id: string, tn: string, u: any) => ToolsService.updateTool({ server_id: id, tool_name: tn, requestBody: u } as any) as any,
      enhance: (id: string) => ToolsService.enhanceTools({ server_id: id } as any) as any,
    },
    credentials: {
      create: (id: string, i: any) => CredentialsService.addCredential({ server_id: id, requestBody: i } as any) as any,
      list: (id: string) => CredentialsService.listCredentials({ server_id: id } as any) as any,
      test: (id: string, i: any) => CredentialsService.testCredential({ server_id: id, requestBody: i } as any) as any,
      delete: (id: string, e: string) => CredentialsService.deleteCredential({ server_id: id, env_var_name: e } as any) as any,
    },
    build: {
      start: (id: string) => BuildService.startBuild({ server_id: id } as any) as any,
      getStatus: (id: string, signal?: AbortSignal) => buildStatusStream(id, signal),
    },
  },
  specs: {
    fetch: (d: any) => SpecsService.fetchSpec(d as any) as any,
    upload: (f: File) => SpecsService.uploadSpec({ formData: { file: f } } as any) as any,
    getById: (id: string) => SpecsService.getSpec({ spec_id: id } as any) as any,
    getTools: (id: string) => SpecsService.getSpecTools({ spec_id: id } as any) as any,
    delete: (id: string) => SpecsService.deleteSpec({ spec_id: id } as any) as any,
    selectTools: (id: string, s: any) => SpecsService.selectTools({ spec_id: id, requestBody: s } as any) as any,
  },
};
