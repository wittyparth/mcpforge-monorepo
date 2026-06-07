import type {
  User,
  McpServer,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  CreateServerRequest,
  PaginatedResponse,
  ApiError,
} from "@/types";

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
      request<PaginatedResponse<McpServer>>(
        "GET",
        `/api/v1/servers?page=${page}&page_size=${pageSize}`,
      ),

    get: (id: string) => request<McpServer>("GET", `/api/v1/servers/${id}`),

    create: (data: CreateServerRequest) =>
      request<McpServer>("POST", "/api/v1/servers", data),

    update: (id: string, data: Partial<CreateServerRequest>) =>
      request<McpServer>("PATCH", `/api/v1/servers/${id}`, data),

    delete: (id: string) => request<void>("DELETE", `/api/v1/servers/${id}`),
  },
};
