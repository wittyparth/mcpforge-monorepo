import type { APIRequestContext, Page } from "@playwright/test";

export const API_BASE = process.env.E2E_API_URL ?? "http://localhost:8000";
export const APP_BASE = process.env.E2E_APP_URL ?? "http://localhost:3000";

let userCounter = 0;

// ── CSRF token handling ─────────────────────────────────────────────────────
//
// The backend enforces double-submit cookie CSRF protection: every state-changing
// POST/PUT/PATCH/DELETE request must include an X-CSRF-Token header whose value
// matches the csrf_token cookie set by the server on a prior response.
//
// We cache the token module-wide and refresh it via a lightweight GET when empty.

let _csrfToken = "";

function _extractCsrfToken(setCookieHeader: string | string[] | undefined): string {
  if (!setCookieHeader) return "";
  const cookieStrings = Array.isArray(setCookieHeader) ? setCookieHeader : [setCookieHeader];
  for (const cs of cookieStrings) {
    // Playwright concatenates multiple Set-Cookie headers without any delimiter.
    // Use regex to find csrf_token=value before the next ; or end-of-string.
    const match = cs.match(/csrf_token=([^;]+)/);
    if (match && match[1]) return match[1];
  }
  return "";
}

/**
 * Ensure a CSRF token is available. Makes a lightweight GET to /health if
 * no token has been cached yet, extracting the csrf_token from the response.
 */
export async function ensureCsrf(request: APIRequestContext): Promise<string> {
  if (_csrfToken) return _csrfToken;
  const res = await request.get(`${API_BASE}/health`);
  _csrfToken = _extractCsrfToken(res.headers()["set-cookie"]);
  return _csrfToken;
}

/**
 * Extract the csrf_token from a response's set-cookie header and cache it.
 * Call this from registerUser, loginUser, and any other function that makes
 * requests whose responses may set a CSRF cookie.
 */
function _cacheCsrfFromResponse(res: { headers: () => Record<string, string> }): void {
  const setCookie = res.headers()["set-cookie"];
  if (!setCookie) return;
  // The raw set-cookie may contain MULTIPLE csrf_token entries (one from the route
  // handler, another from attach_csrf_cookie middleware). The cookie jar stores the
  // LAST one (last Set-Cookie wins for duplicate names), so we find the LAST match.
  const allMatches = Array.from(String(setCookie).matchAll(/csrf_token=([^;]+)/g));
  if (allMatches.length > 0) {
    const lastMatch = allMatches[allMatches.length - 1];
    if (lastMatch && lastMatch[1]) {
      _csrfToken = lastMatch[1];
    }
  }
}

/**
 * Return CSRF-related headers: X-CSRF-Token header only.
 * The Cookie header is NOT set here because Playwright's request fixture
 * automatically persists cookies (access_token, refresh_token, csrf_token)
 * from previous responses in its cookie jar. Manually overriding Cookie
 * would strip the auth cookies needed for authenticated endpoints.
 */
function _csrfHeaders(): Record<string, string> {
  return _csrfToken
    ? { "X-CSRF-Token": _csrfToken }
    : {};
}

/**
 * Public accessor for CSRF headers (X-CSRF-Token + Cookie).
 * Call ensureCsrf() before using.
 */
export function csrfHeaders(): Record<string, string> {
  return { ..._csrfHeaders() };
}

/**
 * Convenience wrapper for CSRF-protected POST requests.
 * Ensures a CSRF token is available, then makes the POST with the token header.
 */
async function csrfPost(
  request: APIRequestContext,
  url: string,
  options: { data?: unknown; headers?: Record<string, string> } = {},
) {
  await ensureCsrf(request);
  return request.post(url, {
    data: options.data,
    headers: { ..._csrfHeaders(), ...options.headers },
  });
}

/**
 * Convenience wrapper for CSRF-protected DELETE requests.
 */
async function csrfDelete(
  request: APIRequestContext,
  url: string,
  options: { headers?: Record<string, string> } = {},
) {
  await ensureCsrf(request);
  return request.delete(url, { headers: { ..._csrfHeaders(), ...options.headers } });
}

/**
 * Convenience wrapper for CSRF-protected PUT requests.
 */
async function csrfPut(
  request: APIRequestContext,
  url: string,
  options: { data?: unknown; headers?: Record<string, string> } = {},
) {
  await ensureCsrf(request);
  return request.put(url, {
    data: options.data,
    headers: { ..._csrfHeaders(), ...options.headers },
  });
}

export function testUser() {
  userCounter++;
  const ts = Date.now();
  return {
    email: `e2e-test-${ts}-${userCounter}@example.com`,
    password: "E2eTestPass123!",
    displayName: `E2E Test User ${ts}`,
  };
}

export function testServer() {
  return {
    name: `E2E Test Server ${Date.now()}`,
    slug: `e2e-test-${Date.now()}`,
    specUrl: "https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml",
    baseUrl: "https://petstore.swagger.io/v2",
    description: "E2E test server created by Playwright",
  };
}

export function uniqueId(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// ── Auth ──────────────────────────────────────────────────────────────

export async function registerUser(
  request: APIRequestContext,
  user?: { email: string; password: string; displayName: string },
) {
  const u = user ?? testUser();
  const res = await request.post(`${API_BASE}/api/v1/auth/register`, {
    data: {
      email: u.email,
      password: u.password,
      display_name: u.displayName,
    },
  });
  const body = await res.json();
  _cacheCsrfFromResponse(res);
  return { ...u, response: res, body, userId: body?.id ?? null };
}

export async function loginUser(
  request: APIRequestContext,
  email: string,
  password: string,
) {
  const res = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { email, password },
  });
  const cookies = res.headers()["set-cookie"] ?? "";
  _cacheCsrfFromResponse(res);
  return { response: res, cookies };
}

export async function getMe(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/v1/auth/me`);
  const body = await res.json();
  return { response: res, body };
}

export async function logoutUser(request: APIRequestContext) {
  return request.post(`${API_BASE}/api/v1/auth/logout`);
}

export async function refreshTokens(request: APIRequestContext) {
  return request.post(`${API_BASE}/api/v1/auth/refresh`);
}

// ── Auth — cookie injection ───────────────────────────────────────────

export async function loginViaApiAndSetCookies(
  request: APIRequestContext,
  page: Page,
  email: string,
  password: string,
) {
  const res = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { email, password },
  });
  const setCookieHeader = res.headers()["set-cookie"];
  if (!setCookieHeader) throw new Error("No set-cookie header in login response");

  // Playwright concatenates multiple Set-Cookie headers without any delimiter.
  // Use regex to extract all known cookie name=value pairs.
  const allHeaders = Array.isArray(setCookieHeader) ? setCookieHeader : [setCookieHeader];
  const cookieRegex = /(access_token|refresh_token|csrf_token)=([^;]+)/g;
  const cookies: { name: string; value: string; domain: string; path: string }[] = [];
  for (const h of allHeaders) {
    let m: RegExpExecArray | null;
    while ((m = cookieRegex.exec(h)) !== null) {
      if (m[1] && m[2]) {
        cookies.push({ name: m[1], value: m[2], domain: "localhost", path: "/" });
      }
    }
  }

  if (cookies.length > 0) {
    await page.context().addCookies(cookies);
  }

  return { response: res, cookies };
}

// ── Servers ───────────────────────────────────────────────────────────

export async function fetchSpec(
  request: APIRequestContext,
  specUrl: string,
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/specs/fetch`, {
    data: { url: specUrl },
  });
  const body = await maybeJson(res);
  if (!res.ok()) {
    console.log(`[DEBUG fetchSpec] status=${res.status()} body=${JSON.stringify(body).slice(0, 200)}`);
  }
  return { response: res, body };
}

export async function uploadSpec(
  request: APIRequestContext,
  fileContent: string,
  fileName = "spec.yaml",
) {
  await ensureCsrf(request);
  const res = await request.post(`${API_BASE}/api/v1/specs/upload`, {
    multipart: {
      file: {
        name: fileName,
        mimeType: "application/x-yaml",
        buffer: Buffer.from(fileContent),
      },
    },
    headers: { ..._csrfHeaders() },
  });
  return { response: res, body: await maybeJson(res) };
}

export async function selectToolsAndCreateServer(
  request: APIRequestContext,
  specId: string,
  config: {
    name: string;
    slug: string;
    baseUrl: string;
    authScheme?: string;
    toolNames?: string[];
    transportMode?: string;
    description?: string | null;
  },
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/specs/${specId}/select-tools`, {
    data: {
      name: config.name,
      slug: config.slug,
      base_url: config.baseUrl,
      auth_scheme: config.authScheme ?? "none",
      selected_tool_names: config.toolNames ?? [],
      transport_mode: config.transportMode ?? "sse",
      description: config.description ?? null,
      customizations: null,
    },
  });
  const body = await maybeJson(res);
  if (!res.ok()) {
    console.log(`[DEBUG selectToolsAndCreateServer] status=${res.status()} body=${JSON.stringify(body).slice(0, 200)}`);
  }
  return { response: res, body };
}

export async function startBuild(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/servers/${serverId}/build`);
  return { response: res, body: await maybeJson(res) };
}

export async function getBuildStatus(
  request: APIRequestContext,
  serverId: string,
) {
  // Use the server detail endpoint (returns JSON with status field)
  // instead of the SSE /build-status endpoint which streams indefinitely.
  const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}`);
  return { response: res, body: await maybeJson(res) };
}

export async function deleteServer(
  request: APIRequestContext,
  serverId: string,
) {
  return csrfDelete(request, `${API_BASE}/api/v1/servers/${serverId}`);
}

export async function createServer(
  request: APIRequestContext,
  data: {
    name: string;
    slug: string;
    base_url: string;
    tools_config?: Record<string, unknown>;
    description?: string | null;
    auth_scheme?: string;
    transport_mode?: string;
  },
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/servers`, { data });
  return { response: res, body: await maybeJson(res) };
}

export async function getServer(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}`);
  return { response: res, body: await maybeJson(res) };
}

export async function listServers(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/v1/servers`);
  return { response: res, body: await maybeJson(res) };
}

export async function pauseServer(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.post(`${API_BASE}/api/v1/servers/${serverId}/pause`);
  return { response: res, body: await maybeJson(res) };
}

export async function resumeServer(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.post(`${API_BASE}/api/v1/servers/${serverId}/resume`);
  return { response: res, body: await maybeJson(res) };
}

export async function testConnection(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.post(`${API_BASE}/api/v1/servers/${serverId}/connect/test`);
  return { response: res, body: await maybeJson(res) };
}

export async function getConnectPanel(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}/connect`);
  return { response: res, body: await maybeJson(res) };
}

// ── Tools ─────────────────────────────────────────────────────────────

export async function getTools(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}/tools`);
  return { response: res, body: await maybeJson(res) };
}

export async function updateTool(
  request: APIRequestContext,
  serverId: string,
  toolName: string,
  description: string,
) {
  const res = await csrfPut(request, `${API_BASE}/api/v1/servers/${serverId}/tools/${toolName}`, {
    data: { description },
  });
  return { response: res, body: await maybeJson(res) };
}

export async function enhanceTools(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/servers/${serverId}/tools/enhance`);
  return { response: res, body: await maybeJson(res) };
}

// ── Credentials ───────────────────────────────────────────────────────

export async function listCredentials(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}/credentials`);
  return { response: res, body: await maybeJson(res) };
}

export async function createCredential(
  request: APIRequestContext,
  serverId: string,
  data: { env_var_name: string; value: string; auth_scheme?: string },
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/servers/${serverId}/credentials`, {
    data,
  });
  return { response: res, body: await maybeJson(res) };
}

export async function deleteCredential(
  request: APIRequestContext,
  serverId: string,
  envVarName: string,
) {
  return csrfDelete(request, `${API_BASE}/api/v1/servers/${serverId}/credentials/${envVarName}`);
}

export async function testCredential(
  request: APIRequestContext,
  serverId: string,
  data: { env_var_name: string; test_value: string },
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/servers/${serverId}/credentials/test`, {
    data,
  });
  return { response: res, body: await maybeJson(res) };
}

// ── API Keys ──────────────────────────────────────────────────────────

export async function listApiKeys(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/v1/api-keys`);
  return { response: res, body: await maybeJson(res) };
}

export async function createApiKey(
  request: APIRequestContext,
  data: { name: string; scopes: string[]; expires_at?: string | null },
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/api-keys`, { data });
  return { response: res, body: await maybeJson(res) };
}

export async function revokeApiKey(
  request: APIRequestContext,
  keyId: string,
) {
  return csrfDelete(request, `${API_BASE}/api/v1/api-keys/${keyId}`);
}

// ── Team ──────────────────────────────────────────────────────────────

export async function getTeam(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/v1/team`);
  return { response: res, body: await maybeJson(res) };
}

export async function createTeam(
  request: APIRequestContext,
  name: string,
) {
  const res = await request.post(`${API_BASE}/api/v1/team`, { data: { name } });
  return { response: res, body: await maybeJson(res) };
}

export async function getTeamMembers(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/v1/team/members`);
  return { response: res, body: await maybeJson(res) };
}

export async function inviteTeamMember(
  request: APIRequestContext,
  email: string,
  role = "member",
) {
  const res = await request.post(`${API_BASE}/api/v1/team/invite`, {
    data: { email, role },
  });
  return { response: res, body: await maybeJson(res) };
}

export async function removeTeamMember(
  request: APIRequestContext,
  userId: string,
) {
  return csrfDelete(request, `${API_BASE}/api/v1/team/members/${userId}`);
}

export async function updateMemberRole(
  request: APIRequestContext,
  userId: string,
  role: string,
) {
  const res = await csrfPut(request, `${API_BASE}/api/v1/team/members/${userId}/role`, {
    data: { role },
  });
  return { response: res, body: await maybeJson(res) };
}

export async function leaveTeam(request: APIRequestContext) {
  return csrfPost(request, `${API_BASE}/api/v1/team/leave`);
}

export async function getAuditLog(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/v1/team/audit-log`);
  return { response: res, body: await maybeJson(res) };
}

// ── Billing ───────────────────────────────────────────────────────────

export async function getPlans(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/v1/billing/plans`);
  return { response: res, body: await maybeJson(res) };
}

export async function getSubscription(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/api/v1/billing/subscription`);
  const body = await maybeJson(res);
  return { response: res, body };
}

export async function subscribeToPlan(
  request: APIRequestContext,
  data: { plan: string; billing_period: string; seats?: number },
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/billing/subscribe`, { data });
  return { response: res, body: await maybeJson(res) };
}

export async function openBillingPortal(
  request: APIRequestContext,
  returnUrl?: string,
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/billing/portal`, {
    data: { return_url: returnUrl ?? `${APP_BASE}/dashboard/billing` },
  });
  return { response: res, body: await maybeJson(res) };
}

export async function getInvoices(
  request: APIRequestContext,
  params?: { skip?: number; limit?: number },
) {
  const search = new URLSearchParams();
  if (params?.skip) search.set("skip", String(params.skip));
  if (params?.limit) search.set("limit", String(params.limit));
  const qs = search.toString();
  const res = await request.get(`${API_BASE}/api/v1/billing/invoices${qs ? `?${qs}` : ""}`);
  return { response: res, body: await maybeJson(res) };
}

// ── Security Scanner ──────────────────────────────────────────────────

export async function getLatestScan(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}/security/latest`);
  return { response: res, body: await maybeJson(res) };
}

export async function triggerScan(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/servers/${serverId}/security/scan`);
  return { response: res, body: await maybeJson(res) };
}

export async function getScanHistory(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}/security`);
  return { response: res, body: await maybeJson(res) };
}

export async function acknowledgeFinding(
  request: APIRequestContext,
  serverId: string,
  findingId: string,
) {
  const res = await csrfPost(request, `${API_BASE}/api/v1/servers/${serverId}/security/acknowledge`, {
    data: { finding_id: findingId },
  });
  return { response: res, body: await maybeJson(res) };
}

export async function getAcknowledgments(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}/security/acknowledgments`);
  return { response: res, body: await maybeJson(res) };
}

// ── Gateway / MCP ─────────────────────────────────────────────────────

export async function getGatewaySSE(
  request: APIRequestContext,
  slug: string,
) {
  const res = await request.get(`${API_BASE}/mcp/v1/${slug}/sse`);
  return { response: res, body: await res.text() };
}

export async function sendMcpMessage(
  request: APIRequestContext,
  slug: string,
  body: Record<string, unknown>,
) {
  const res = await request.post(`${API_BASE}/mcp/v1/${slug}/message`, {
    data: body,
    headers: { "content-type": "application/json" },
  });
  return { response: res, body: await maybeJson(res) };
}

// ── Playground (WebSocket) ────────────────────────────────────────────

export function playgroundWsUrl(slug: string): string {
  const apiUrl = API_BASE.replace(/^http/, "ws");
  return `${apiUrl}/ws/playground/${slug}`;
}

// ── Health ────────────────────────────────────────────────────────────

export async function healthCheck(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/health`);
  return { response: res, body: await maybeJson(res) };
}

export async function readinessCheck(request: APIRequestContext) {
  const res = await request.get(`${API_BASE}/health/ready`);
  return { response: res, body: await maybeJson(res) };
}

// ── Utilities ─────────────────────────────────────────────────────────

async function maybeJson(res: { status: () => number; text: () => Promise<string> }) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function csrfTokenFromCookies(page: Page): Promise<string | null> {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((c: { name: string }) => c.name === "csrf_token");
  return csrf?.value ?? null;
}
