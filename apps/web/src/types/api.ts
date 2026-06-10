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
 * using Server-Sent Events. The AI Description Engine emits events with
 * `event` field (start, ai_progress, tool_enhanced, tool_failed, ai_complete,
 * error, done). The hook normalizes these to a `stage` for the UI stepper.
 */
export interface BuildStatusEvent {
  /** Normalized pipeline stage for UI stepper (derived from event if needed) */
  stage?: BuildStage;
  /** Raw event type from backend */
  event?: string;
  /** Progress percentage (0–100) or tool index */
  progress?: number;
  /** Total number of tools (for AI progress events) */
  total?: number;
  /** Tool name (AI events) */
  tool_name?: string;
  /** Human-readable status message */
  message?: string;
  /** Quality score for AI-enhanced tool (0–100) */
  quality_score?: number;
  /** Cost in cents for this tool enhancement */
  cost_cents?: number;
  /** Error message for failed events */
  error?: string;
  /** Number of successful enhancements */
  successful?: number;
  /** Number of failed enhancements */
  failed?: number;
  /** Server ID */
  server_id?: string;
  /** Timestamp */
  timestamp?: string;
}

// ── F2: AI Description Engine Types ─────────────────────────────

/** Quality score for an AI-enhanced tool description */
export interface AIQualityScore {
  functionality: number;
  accuracy: number;
  completeness: number;
  context: number;
  total: number;
  badge: "Excellent" | "Good" | "Fair" | "Poor";
}

/** An improvement made by the AI enhancement */
export interface AIImprovementItem {
  field: string;
  current: string;
  proposed: string;
  rationale: string;
}

/** AI-enhanced version of a single tool */
export interface AIEnhancedTool {
  name: string;
  original_description: string;
  enhanced_description: string;
  enhanced_name?: string | null;
  enhanced_parameters?: Record<string, unknown>[];
  enhanced_return_description?: string | null;
  quality_score: AIQualityScore;
  improvements?: AIImprovementItem[];
  cost_cents: number;
  model: string;
  enhanced_at: string;
}

/** Request to initiate AI enhancement */
export interface AIEnhancementRequest {
  tool_names?: string[];
  force?: boolean;
}

/** Response from enhancement job submission */
export interface AIEnhancementResponse {
  job_id: string;
  estimated_cost_cents: number;
  estimated_duration_seconds: number;
  remaining_credits: number | null;
}

/** Accept/reject AI enhancement results */
export interface ToolAcceptRequest {
  accepted_tools: string[];
  rejected_tools?: string[];
  custom_edits?: Record<string, Record<string, unknown>>;
}

/** SSE event during build pipeline */
export interface BuildEvent {
  event:
    | "connected"
    | "start"
    | "ai_progress"
    | "tool_enhanced"
    | "tool_failed"
    | "ai_complete"
    | "done"
    | "error";
  server_id: string;
  tool_name?: string;
  progress?: number;
  total?: number;
  quality_score?: number;
  cost_cents?: number;
  error?: string;
  timestamp: string;
}

// ── F4: MCP Gateway Types ──────────────────────────────────────────

export interface ConnectPanelData {
  server_slug: string;
  gateway_url: string;
  transport_modes: ("sse" | "streamable_http")[];
  claude_desktop_config: Record<string, unknown>;
  cursor_config: Record<string, unknown>;
  test_connection_endpoint: string;
}

export interface TestConnectionResult {
  success: boolean;
  response_time_ms: number;
  tools_count: number | null;
  error: string | null;
}

export interface PauseResult {
  server_id: string;
  status: "paused" | "active";
  paused_at: string | null;
  estimated_propagation_seconds: number;
}

// ── F5: Security Scanner Types ──────────────────────────────────

/** Finding ID (stable rule identifier) */
export type FindingId =
  | "SSRF_URL_PARAM"
  | "NO_AUTH_DELETE"
  | "CREDENTIAL_IN_RESPONSE"
  | "PROMPT_INJECTION_DESC"
  | "NO_AUTH_WRITES"
  | "UNTAGGED_ENDPOINTS"
  | "DEPRECATED_HTTP_METHODS"
  | "LARGE_TOOL_SET";

/** Finding severity levels */
export type FindingSeverity = "critical" | "high" | "medium" | "info";

/** A single security finding from the scanner */
export interface Finding {
  id: string;
  severity: FindingSeverity;
  title: string;
  description: string;
  affected_tools: string[];
  remediation: string;
  references: string[];
}

/** Response from triggering a scan */
export interface ScanTriggerResponse {
  scan_id: string;
  scan_status: string;
  message: string;
}

/** Response from GET /api/v1/servers/{id}/security/latest */
export interface ScanResultResponse {
  id: string;
  server_id: string;
  scan_status: "running" | "completed" | "failed";
  findings: Finding[];
  critical_count: number;
  high_count: number;
  medium_count: number;
  info_count: number;
  scanned_at: string;
  scan_duration_ms: number | null;
}

/** Response from GET /api/v1/servers/{id}/security (paginated) */
export interface ScanHistoryResponse {
  items: ScanResultResponse[];
  total: number;
  page: number;
  page_size: number;
  next_page: number | null;
}

/** Request body for acknowledge */
export interface AcknowledgeRequest {
  note?: string | null;
}

/** Response from acknowledge endpoint */
export interface AcknowledgeResponse {
  server_id: string;
  finding_id: string;
  acknowledged_at: string;
}

/** Response from acknowledgment list */
export interface AckListResponse {
  items: AcknowledgeResponse[];
  total: number;
}

/** Response when deploy is blocked by CRITICAL findings */
export interface DeployBlockedResponse {
  blocked: boolean;
  reason: string;
  critical_findings: Finding[];
  scan_id: string | null;
}

/** JSON report for export/download */
export interface SecurityReport {
  server_id: string;
  server_name: string;
  generated_at: string;
  scan: ScanResultResponse | null;
  acknowledgments: AcknowledgeResponse[];
  summary: string;
}

// ── F7: Team Types ────────────────────────────────────────────────

/** Team member roles */
export type TeamRole = "admin" | "editor" | "viewer";

/** Response from GET /api/v1/team */
export interface TeamResponse {
  id: string;
  name: string;
  owner_id: string;
  plan: string;
  created_at: string;
  member_count: number;
  current_user_role: TeamRole;
}

/** Response from GET /api/v1/team/members (single member) */
export interface TeamMemberResponse {
  user_id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  role: TeamRole;
  joined_at: string;
}

/** Response from POST /api/v1/team/invite */
export interface TeamInvitationCreateResponse {
  id: string;
  email: string;
  role: TeamRole;
  token: string;
  expires_at: string;
  created_at: string;
}

/** A single audit log entry */
export interface AuditLogResponse {
  id: string;
  user_id: string;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

/** Paginated audit log response */
export interface PaginatedAuditLogResponse {
  items: AuditLogResponse[];
  total: number;
  skip: number;
  limit: number;
}

// ── F7: Billing Types ────────────────────────────────────────────

export interface PlanInfo {
  id: string;
  name: string;
  price_cents: number;
  currency: string;
  period: "monthly" | "yearly";
  features: string[];
  popular: boolean;
  min_seats: number | null;
}

export interface PlansResponse {
  plans: PlanInfo[];
}

export interface SubscribeRequest {
  plan: "pro" | "team";
  billing_period: "monthly" | "yearly";
  seats?: number;
}

export interface CheckoutResponse {
  checkout_url: string;
  session_id: string;
}

export interface PortalRequest {
  return_url?: string;
}

export interface PortalResponse {
  portal_url: string;
}

export type SubscriptionStatus =
  | "active"
  | "trialing"
  | "past_due"
  | "canceled"
  | "incomplete"
  | "unpaid";

export interface SubscriptionResponse {
  id: string;
  plan: string;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  seats: number;
}

export interface InvoiceResponse {
  id: string;
  amount_cents: number;
  currency: string;
  status: "paid" | "open" | "uncollectible" | "void";
  invoice_pdf_url: string | null;
  hosted_invoice_url: string | null;
  created_at: string;
}

export interface InvoicesListResponse {
  items: InvoiceResponse[];
  total: number;
  skip: number;
  limit: number;
}

// ── F7: API Key Types ──────────────────────────────────────────────

/** API key scope values */
export type ApiKeyScope =
  | "servers:read"
  | "servers:write"
  | "analytics:read"
  | "admin";

/** A single API key (never includes plaintext after creation) */
export interface ApiKeyResponse {
  id: string;
  name: string;
  key_prefix: string;
  scopes: ApiKeyScope[];
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

/** Response from POST /api/v1/api-keys — plaintext shown ONCE */
export interface ApiKeyCreateResponse {
  key: ApiKeyResponse;
  plaintext_key: string;
}

/** Response from GET /api/v1/api-keys */
export interface ApiKeyListResponse {
  items: ApiKeyResponse[];
  total: number;
}

// ── F7: Server Management Types (Duplicate, Versions, Rollback) ────

/** Request body for POST /api/v1/servers/{id}/duplicate */
export interface DuplicateServerRequest {
  new_name: string;
  new_slug?: string | null;
}

/** A single server version entry */
export interface ServerVersionResponse {
  id: string;
  version: number;
  change_note: string | null;
  changed_by: string | null;
  changed_by_email: string | null;
  created_at: string;
}

/** Response from GET /api/v1/servers/{id}/versions (paginated) */
export interface ServerVersionsResponse {
  items: ServerVersionResponse[];
  total: number;
  skip: number;
  limit: number;
}

/** Request body for POST /api/v1/servers/{id}/rollback */
export interface RollbackRequest {
  version: number;
}

// ── F6: Analytics Types ────────────────────────────────────────────

/** Top-line numbers for a server in a time range. */
export interface AnalyticsOverview {
  server_id: string;
  range: "7d" | "30d" | "90d";
  total_calls: number;
  total_errors: number;
  error_rate: number; // 0-1
  unique_clients: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
}

/** Per-tool row in the breakdown table. */
export interface ToolBreakdownItem {
  tool_name: string;
  call_count: number;
  error_count: number;
  avg_latency_ms: number;
  selection_rate: number; // 0-1
}

/** A sanitized error row. */
export interface ErrorLogItem {
  called_at: string;
  tool_name: string;
  error_type: string;
  error_msg: string;
  client_name: string | null;
}

/** A single time-series bucket. */
export interface TimeSeriesPoint {
  bucket_start: string;
  call_count: number;
  error_count: number;
  avg_latency_ms: number | null;
}

/** A row in the client breakdown. */
export interface ClientBreakdownItem {
  client_name: string;
  call_count: number;
  last_seen: string;
}

/** Description performance panel row. */
export interface DescriptionPerformance {
  tool_name: string;
  edited_at: string | null;
  edit_source: "ai" | "user" | "revert" | null;
  before_call_count: number;
  after_call_count: number;
  delta_pct: number | null;
  message: string;
  no_edit: boolean;
}
