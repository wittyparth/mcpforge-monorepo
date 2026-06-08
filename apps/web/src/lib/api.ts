import type {
  User,
  McpServer,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  CreateServerRequest,
  ApiError,
} from "@/types";
import type {
  SpecFetchRequest,
  SpecUploadResponse,
  SpecSource,
  SpecToolListResponse,
  ToolSelectionRequest,
  ToolListResponse,
  ToolUpdateRequest,
  CredentialCreateRequest,
  CredentialInfo,
  CredentialListResponse,
  CredentialTestRequest,
  CredentialTestResponse,
  BuildStatusEvent,
} from "@/types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiClientError extends Error {
  public status: number;
  public code: string | undefined;
  public field: string | undefined;

  constructor(message: string, status: number, code?: string, field?: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorBody: ApiError | null = null;
    try {
      errorBody = (await response.json()) as ApiError;
    } catch {
      // Response body is not JSON
    }

    const message =
      errorBody?.detail ?? `Request failed with status ${response.status}`;
    throw new ApiClientError(
      message,
      response.status,
      errorBody?.code,
      errorBody?.field,
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestInit,
): Promise<T> {
  const url = `${API_URL}${path}`;

  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  };

  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    method,
    headers,
    credentials: "include",
    body:
      body instanceof FormData
        ? body
        : body !== undefined
          ? JSON.stringify(body)
          : undefined,
    ...options,
  });

  return handleResponse<T>(response);
}

// API client with typed methods matching the backend endpoints
async function* buildStatusStream(
  id: string,
  signal?: AbortSignal,
): AsyncIterable<BuildStatusEvent> {
  const url = `${API_URL}/api/v1/servers/${id}/build-status`;
  const response = await fetch(url, { credentials: "include", signal });

  if (!response.ok) {
    let errorBody: ApiError | null = null;
    try {
      errorBody = (await response.json()) as ApiError;
    } catch {
      // Response body is not JSON
    }
    throw new ApiClientError(
      errorBody?.detail ?? `SSE connection failed with status ${response.status}`,
      response.status,
      errorBody?.code,
      errorBody?.field,
    );
  }

  if (!response.body) {
    throw new ApiClientError("SSE response has no body", 0);
  }

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
          const data = line.slice(6);
          try {
            const event = JSON.parse(data) as BuildStatusEvent;
            yield event;
          } catch {
            // No-op: skip malformed SSE data
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export const api = {
  auth: {
    register: (data: RegisterRequest) =>
      request<AuthResponse>("POST", "/api/v1/auth/register", data),

    login: (data: LoginRequest) =>
      request<AuthResponse>("POST", "/api/v1/auth/login", data),

    logout: () => request<void>("POST", "/api/v1/auth/logout"),

    me: () => request<User>("GET", "/api/v1/auth/me"),

    refresh: () => request<AuthResponse>("POST", "/api/v1/auth/refresh"),
  },

  servers: {
    list: (page = 1, pageSize = 20) =>
      request<McpServer[]>(
        "GET", `/api/v1/servers?page=${page}&page_size=${pageSize}`
      ),

    get: (id: string) => request<McpServer>("GET", `/api/v1/servers/${id}`),

    create: (data: CreateServerRequest) =>
      request<McpServer>("POST", "/api/v1/servers", data),

    update: (id: string, data: Partial<CreateServerRequest>) =>
      request<McpServer>("PATCH", `/api/v1/servers/${id}`, data),

    delete: (id: string) => request<void>("DELETE", `/api/v1/servers/${id}`),

    tools: {
      list: (id: string) =>
        request<ToolListResponse>("GET", `/api/v1/servers/${id}/tools`),
      update: (id: string, toolName: string, updates: ToolUpdateRequest) =>
        request<Record<string, unknown>>(
          "PATCH",
          `/api/v1/servers/${id}/tools/${toolName}`,
          updates,
        ),
      enhance: (id: string) =>
        request<void>("POST", `/api/v1/servers/${id}/tools/enhance`),
    },

    credentials: {
      create: (id: string, input: CredentialCreateRequest) =>
        request<CredentialInfo>(
          "POST",
          `/api/v1/servers/${id}/credentials`,
          input,
        ),
      list: (id: string) =>
        request<CredentialListResponse>(
          "GET",
          `/api/v1/servers/${id}/credentials`,
        ),
      test: (id: string, input: CredentialTestRequest) =>
        request<CredentialTestResponse>(
          "POST",
          `/api/v1/servers/${id}/credentials/test`,
          input,
        ),
      delete: (id: string, envVarName: string) =>
        request<void>(
          "DELETE",
          `/api/v1/servers/${id}/credentials/${envVarName}`,
        ),
    },

    build: {
      start: (id: string) =>
        request<McpServer>("POST", `/api/v1/servers/${id}/build`),
      getStatus: (id: string, signal?: AbortSignal) =>
        buildStatusStream(id, signal),
    },
  },

  specs: {
    fetch: (input: SpecFetchRequest) =>
      request<SpecUploadResponse>("POST", "/api/v1/specs/fetch", input),
    upload: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return request<SpecUploadResponse>(
        "POST",
        "/api/v1/specs/upload",
        formData,
      );
    },
    getById: (specId: string) =>
      request<SpecSource>("GET", `/api/v1/specs/${specId}`),
    getTools: (specId: string) =>
      request<SpecToolListResponse>("GET", `/api/v1/specs/${specId}/tools`),
    delete: (specId: string) =>
      request<void>("DELETE", `/api/v1/specs/${specId}`),
    selectTools: (specId: string, selection: ToolSelectionRequest) =>
      request<McpServer>(
        "POST",
        `/api/v1/specs/${specId}/select-tools`,
        selection,
      ),
  },
};
