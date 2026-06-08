// API response types for MCPForge backend

export interface User {
  id: string;
  email: string;
  display_name?: string | null;
  avatar_url?: string | null;
  plan?: string;
  email_verified?: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface McpServer {
  id: string;
  user_id: string;
  slug: string;
  name: string;
  description?: string | null;
  status: string;
  spec_url?: string | null;
  base_url: string;
  auth_scheme: "none" | "api_key" | "bearer" | "basic" | "oauth2";
  tools_config: unknown;
  transport_mode: "sse" | "streamable_http" | "both";
  total_calls?: number;
  monthly_calls?: number;
  last_call_at?: string | null;
  version: number;
  created_at: string;
  updated_at?: string | null;
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

// ── F1: OpenAPI Spec Ingestion Types ──────────────────────────────

/** HTTP methods supported by OpenAPI operations */
export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "HEAD" | "OPTIONS";

/** Authentication schemes for MCP servers */
export type AuthScheme = "none" | "api_key" | "bearer" | "basic" | "oauth2";

/** Authentication schemes for stored credentials (excludes "none") */
export type CredentialAuthScheme = "bearer" | "api_key" | "basic" | "oauth2" | "header";

/** MCP transport modes */
export type TransportMode = "sse" | "streamable_http" | "both";

/** Build pipeline stages emitted as SSE events */
export type BuildStage = "parsing" | "generating" | "testing" | "deploying" | "complete" | "error";

// ── Spec Types ────────────────────────────────────────────────────

/** Request body for POST /api/v1/specs/fetch */
export interface SpecFetchRequest {
  url: string;
  headers?: Record<string, string> | null;
}

/** Response from GET /api/v1/specs/{id} — spec metadata */
export interface SpecSource {
  id: string;
  user_id: string;
  source_type: string;
  source_url: string | null;
  r2_key: string | null;
  title: string | null;
  version: string | null;
  openapi_version: string | null;
  endpoint_count: number | null;
  spec_size_bytes: number | null;
  fetch_status: string;
  fetch_error: string | null;
  created_at: string;
  updated_at: string | null;
}

/** Response from a successful spec fetch or upload */
export interface SpecUploadResponse {
  spec_id: string;
  title: string | null;
  version: string | null;
  openapi_version: string | null;
  endpoint_count: number;
  spec_size_bytes: number;
  tools?: ToolDefinition[];
}

/** A single validation error detail for a spec field */
export interface SpecValidationError {
  path: string;
  message: string;
  line?: number | null;
  column?: number | null;
}

/** Structured error response for spec fetch/validation failures */
export interface SpecFetchErrorResponse {
  error_code: string;
  message: string;
  details: SpecValidationError[];
  suggestion?: string | null;
}

/** Response from GET /api/v1/specs/{spec_id}/tools */
export interface SpecToolListResponse {
  spec_id: string;
  tools: ToolDefinition[];
}

// ── Tool Types ────────────────────────────────────────────────────

/** A single parameter extracted from an OpenAPI operation */
export interface ToolParameter {
  name: string;
  /** OpenAPI parameter location ("in" field, reserved-word-quoted) */
  "in": "path" | "query" | "header" | "cookie";
  required: boolean;
  description: string;
  /** JSON Schema for the parameter value (aliased from "schema" on the wire) */
  schema: Record<string, unknown>;
  example?: unknown;
}

/** A single MCP tool extracted from an OpenAPI operation */
export interface ToolDefinition {
  name: string;
  description: string;
  /** JSON Schema for the tool's input arguments */
  input_schema: Record<string, unknown>;
  /** Override the server base URL for this tool only */
  base_url_override: string | null;
  /** Original OpenAPI operationId, if any */
  operation_id: string | null;
  method: HttpMethod;
  path: string;
  original_operation_id: string | null;
  summary: string | null;
  tags: string[];
  parameters: ToolParameter[];
  /** JSON Schema for the request body */
  request_body_schema: Record<string, unknown> | null;
  /** Response schemas keyed by HTTP status code */
  response_schemas: Record<string, Record<string, unknown>>;
  security_requirements: Record<string, unknown>[];
  selected: boolean;
  warnings: string[];
}

/** Request body for POST /api/v1/specs/{id}/select-tools */
export interface ToolSelectionRequest {
  slug: string;
  name: string;
  base_url: string;
  description?: string | null;
  auth_scheme: string;
  auth_header_name?: string | null;
  /** Names of tools the user selected to include */
  selected_tool_names: string[];
  customizations?: Record<string, Record<string, unknown>> | null;
  transport_mode: string;
}

/** Response from GET /api/v1/servers/{id}/tools */
export interface ToolListResponse {
  server_id: string;
  tool_count: number;
  tools: Record<string, unknown>[];
}

/** Request body for PATCH /api/v1/servers/{id}/tools/{tool_name} */
export interface ToolUpdateRequest {
  description?: string | null;
  enabled?: boolean | null;
  name?: string | null;
}

// ── Credential Types ──────────────────────────────────────────────

/** Request body for POST /api/v1/servers/{id}/credentials */
export interface CredentialCreateRequest {
  env_var_name: string;
  value: string;
  auth_scheme: string;
  auth_header_name?: string | null;
}

/** A stored credential (value NEVER returned by the API). */
export interface CredentialInfo {
  id: string;
  env_var_name: string;
  auth_scheme: string;
  auth_header_name?: string | null;
  encryption_key_id?: string | null;
  rotated_at?: string | null;
  last_used_at?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface CredentialListResponse {
  server_id: string;
  credentials: CredentialInfo[];
  total: number;
}

export interface CredentialTestRequest {
  env_var_name: string;
  test_value: string;
}

export interface CredentialTestResponse {
  success: boolean;
  status_code?: number | null;
  latency_ms?: number | null;
  error?: string | null;
}

// ── Build Types ───────────────────────────────────────────────────

/** Request body for initiating a server build */
export interface BuildStartRequest {
  spec_source_id?: string;
  transport_mode?: TransportMode;
}

/**
 * An SSE event emitted during the server build pipeline.
 *
 * The backend emits these over `GET /api/v1/servers/{id}/build-status`
 * using Server-Sent Events with `data: {"stage":"...","progress":N,"message":"..."}`.
 */
export interface BuildStatusEvent {
  /** Current pipeline stage */
  stage: BuildStage;
  /** Progress percentage (0–100) */
  progress: number;
  /** Human-readable status message */
  message: string;
}
