// API response types for MCPForge backend

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  plan: "free" | "pro" | "team";
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface McpServer {
  id: string;
  user_id: string;
  slug: string;
  name: string;
  description: string | null;
  status: "building" | "active" | "paused" | "error";
  spec_url: string | null;
  base_url: string;
  auth_scheme: "none" | "api_key" | "bearer" | "basic" | "oauth2";
  tools_config: unknown;
  transport_mode: "sse" | "streamable_http" | "both";
  total_calls: number;
  monthly_calls: number;
  last_call_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ApiError {
  detail: string;
  code?: string;
  field?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  next_page: number | null;
}

// Auth request/response types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name?: string;
}

export interface AuthResponse {
  user: User;
  message?: string;
}

// Server request types
export interface CreateServerRequest {
  name: string;
  slug: string;
  base_url: string;
  auth_scheme: "none" | "api_key" | "bearer" | "basic" | "oauth2";
  description?: string;
  spec_url?: string;
}
