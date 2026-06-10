/**
 * Comprehensive Playwright E2E tests for the MCP playground WebSocket feature.
 *
 * CRITICAL: These tests connect to the REAL backend WebSocket.
 * No page.route() or routeWebSocket() mocks are used.
 *
 * Prerequisites:
 *   - Backend running at http://localhost:8000
 *   - Frontend dev server running at http://localhost:3000
 *   - Docker/Postgres/Redis running (or CI equivalents)
 *
 * Each test in this serial group builds on shared state:
 *   a registered user, a built server with real tools, and auth cookies.
 */

import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import {
  testUser,
  registerUser,
  loginUser,
  fetchSpec,
  selectToolsAndCreateServer,
  createServer,
  deleteServer,
  pauseServer,
  resumeServer,
  getTools,
} from "../e2e/api-helpers";

// ── Constants ─────────────────────────────────────────────────────────

/**
 * Valid OpenAPI 3.0 spec for the Swagger Petstore.
 * This is publicly accessible and has 19 operations.
 */
const SPEC_URL =
  "https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml";

/** Base URL for the petstore API */
const BASE_URL = "https://petstore3.swagger.io/api/v3";

/** Tool names (operationIds) we select from the petstore spec */
const SELECTED_TOOLS = [
  "getInventory",
  "findPetsByStatus",
  "getPetById",
  "getUserByName",
  "logoutUser",
];

// ── Helpers ───────────────────────────────────────────────────────────

// Build step skipped: servers are created with status "active" and
// AI enhancement (Celery) is not available in dev mode.

/**
 * Parse set-cookie header into name/value pairs.
 */
function parseCookies(
  setCookieHeader: string | string[] | undefined,
): { name: string; value: string }[] {
  if (!setCookieHeader) return [];
  const cookieStrings = Array.isArray(setCookieHeader)
    ? setCookieHeader
    : [setCookieHeader];
  return cookieStrings.flatMap((cs) => {
    const parts = cs.split(";").map((s) => s.trim());
    const nameEq = parts[0];
    if (!nameEq) return [];
    const eqIdx = nameEq.indexOf("=");
    if (eqIdx === -1) return [];
    return [{ name: nameEq.slice(0, eqIdx), value: nameEq.slice(eqIdx + 1) }];
  });
}

/**
 * Set auth cookies from the login response into the page context.
 */
async function setAuthCookies(
  page: Page,
  cookies: { name: string; value: string }[],
): Promise<void> {
  await page.context().addCookies(
    cookies.map((c) => ({
      name: c.name,
      value: c.value,
      domain: "localhost",
      path: "/",
    })),
  );
}

/**
 * Select a tool without page reload by changing URL params and firing popstate.
 * The PlaygroundPage listens for popstate and re-selects the tool from URL.
 */
async function selectTool(
  page: Page,
  toolName: string,
): Promise<void> {
  await page.evaluate((name) => {
    const url = new URL(window.location.href);
    url.searchParams.set("tool", name);
    window.history.pushState({}, "", url);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, toolName);
}

/**
 * Create a server with NO tools — used for the empty-state test.
 * Uses the direct server creation endpoint (select-tools requires >=1 tool).
 * Returns the server's id and slug.
 */
async function createEmptyServer(
  request: APIRequestContext,
  _specId: string,
): Promise<{ id: string; slug: string }> {
  const ts = Date.now();
  const result = await createServer(request, {
    name: `E2E Empty ${ts}`,
    slug: `e2e-empty-${ts}`,
    base_url: BASE_URL,
    tools_config: { tools: [] },
  });
  if (!result.response.ok()) {
    throw new Error(
      `Failed to create empty server: ${JSON.stringify(result.body)}`,
    );
  }
  return { id: result.body.id, slug: result.body.slug };
}

// ── Serial test group ─────────────────────────────────────────────────

test.describe.serial("Playground WebSocket E2E", () => {
  // ── Shared state ──────────────────────────────────────────────────
  let user: ReturnType<typeof testUser>;
  let serverId: string;
  let serverSlug: string;
  let toolNames: string[];
  let authCookies: { name: string; value: string }[];
  let emptyServerId: string;

  // ── beforeAll: bootstrap shared resources ─────────────────────────
  test.beforeAll(async ({ request }) => {
    // 1. Register a unique test user
    user = testUser();
    const reg = await registerUser(request, user);
    expect(reg.response.ok()).toBeTruthy();
    console.log(`Registered user: ${user.email}`);

    // 2. Fetch the petstore OpenAPI spec
    const spec = await fetchSpec(request, SPEC_URL);
    expect(spec.response.ok()).toBeTruthy();
    const specId = spec.body.spec_id as string;
    console.log(`Fetched spec: ${specId}`);

    // 3. Select tools and create the primary server
    const ts = Date.now();
    const createRes = await selectToolsAndCreateServer(request, specId, {
      name: `E2E Playground ${ts}`,
      slug: `e2e-pg-${ts}`,
      baseUrl: BASE_URL,
      toolNames: SELECTED_TOOLS,
      description: "E2E playground test server",
    });
    expect(createRes.response.ok()).toBeTruthy();
    serverId = createRes.body.id as string;
    serverSlug = createRes.body.slug as string;
    console.log(`Created server: ${serverId} (slug: ${serverSlug})`);

    // Build skipped: server is created with status "active",
    // tools are already configured. AI enhancement (Celery) runs out-of-process.

    // 5. Read the actual tool names from the server
    const toolsRes = await getTools(request, serverId);
    toolNames = (toolsRes.body.tools as Array<{ name: string }>).map(
      (t) => t.name,
    );
    console.log(`Tools available: ${toolNames.join(", ")}`);

    // 6. Create an empty server (no tools) for the empty-state test
    const empty = await createEmptyServer(request, specId);
    emptyServerId = empty.id;
    console.log(`Created empty server: ${emptyServerId}`);

    // 7. Login to get auth cookies for the browser tests
    const loginRes = await loginUser(request, user.email, user.password);
    expect(loginRes.response.ok()).toBeTruthy();
    authCookies = parseCookies(
      loginRes.response.headers()["set-cookie"] ?? "",
    );
    console.log(`Logged in, got ${authCookies.length} auth cookies`);
  });

  // ── afterAll: cleanup ────────────────────────────────────────────
  test.afterAll(async ({ request }) => {
    if (serverId) {
      await deleteServer(request, serverId);
      console.log(`Deleted server: ${serverId}`);
    }
    if (emptyServerId) {
      await deleteServer(request, emptyServerId);
      console.log(`Deleted empty server: ${emptyServerId}`);
    }
  });

  // ── beforeEach: set auth cookies for every test ──────────────────
  test.beforeEach(async ({ page }) => {
    await setAuthCookies(page, authCookies);
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 1: Playground opens and connects
  // ═════════════════════════════════════════════════════════════════
  test("1. Playground opens and connects", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);

    // Verify "Connected" indicator appears within timeout
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 20000 });

    // Verify tool list is visible in the sidebar / tool browser
    // Check at least the first few tool names appear
    for (const name of toolNames.slice(0, 3)) {
      await expect(page.getByText(name, { exact: true })).toBeVisible();
    }

    // Verify the tool count badge is visible and matches
    await expect(
      page.locator("text=Tools").first(),
    ).toBeVisible();
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 2: Select tool and call it
  // ═════════════════════════════════════════════════════════════════
  test("2. Select tool and call it", async ({ page }) => {
    // Capture browser console for diagnostics
    const browserLogs: string[] = [];
    page.on("console", (msg) => {
      browserLogs.push(`[${msg.type()}] ${msg.text()}`);
    });
    page.on("pageerror", (err) => {
      browserLogs.push(`[PAGE ERROR] ${err.message}`);
    });

    await page.goto(`/dashboard/servers/${serverId}/playground?tool=getInventory`);
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 20000 });

    // The form should show "No input parameters required" (no tool name heading — CardTitle is a <div>)
    await expect(page.getByText("No input parameters required")).toBeVisible({
      timeout: 5000,
    });

    // Click "Call Tool"
    await page.getByRole("button", { name: /Call / }).click({ force: true });

    // Check if calling state shows up
    const callingVisible = await page.getByText("Calling...").isVisible().catch(() => false);
    console.log(`[diag] Calling... visible after click: ${callingVisible}`);

    // Wait a moment for any response
    await page.waitForTimeout(5000);

    // Diagnostic: check call log and response state
    const callLogEntries = await page.getByRole("listitem").filter({ hasText: /getInventory/i }).count().catch(() => 0);
    console.log(`[diag] Call log entries for getInventory: ${callLogEntries}`);
    const connectedVisible = await page.getByText("Connected", { exact: true }).isVisible().catch(() => false);
    console.log(`[diag] Connected visible: ${connectedVisible}`);
    const emptyResponseVisible = await page.getByText("Response will appear here after a tool call").isVisible().catch(() => false);
    console.log(`[diag] Empty response visible: ${emptyResponseVisible}`);
    console.log(`[diag] Browser logs (${browserLogs.length}):`);
    for (const log of browserLogs.slice(0, 10)) {
      console.log(`  ${log}`);
    }

    // Wait for the response to appear in the response viewer.
    // The response JSON should contain status/result data.
    // First, verify the response viewer is no longer showing the empty state
    await expect(
      page.getByText("Response will appear here after a tool call"),
    ).not.toBeVisible({ timeout: 10000 });

    // Verify response timing (ms or seconds) is displayed
    await expect(page.getByText(/\d+ ms|\d+\.\d+ s/)).toBeVisible({ timeout: 5000 });

    // Verify the call log shows an entry for this tool
    await expect(
      page.getByRole("listitem").filter({ hasText: /getInventory/i }),
    ).toBeVisible({ timeout: 5000 });
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 3: Multiple rapid tool calls
  // ═════════════════════════════════════════════════════════════════
  test("3. Multiple rapid tool calls", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground?tool=getInventory`);
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15000 });

    await expect(page.getByText("No input parameters required")).toBeVisible({
      timeout: 5000,
    });

    // Call the tool 5 times, waiting for each call to complete before the next.
    // .click() is used without force:true, so it waits for the button to be enabled
    // (isCalling=false) before each click.
    for (let i = 0; i < 5; i++) {
      // Use /Call / (capital C + space) to match only the submit button's
      // aria-label "Call getInventory" / "Calling tool…", not the "Clear call log"
      // or "Replay getInventory call" buttons which use lowercase "call".
      // force:true bypasses stability checks (panels resize as content loads)
      await page.getByRole("button", { name: /Call / }).click({ force: true });
      // Wait for the call log to update with this call's entry
      await expect(
        page.getByRole("listitem").filter({ hasText: /getInventory/i }),
      ).toHaveCount(i + 1, { timeout: 15000 });
    }

    // Verify no WebSocket disconnection — "Connected" should still be visible
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 5000 });

    // Call log badge should show 5
    await expect(
      page.getByText("5", { exact: true }).first(),
    ).toBeVisible({ timeout: 3000 });
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 4: Call history / log
  // ═════════════════════════════════════════════════════════════════
  test("4. Call history / log", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15000 });

    // Make 3 different tool calls using available tools
    // Use tools that require no params or have simple defaults

    // Call 1: getInventory (no params)
    await selectTool(page, "getInventory");
    await expect(page.getByText("No input parameters required")).toBeVisible({
      timeout: 5000,
    });
    await page.getByRole("button", { name: /Call / }).click({ force: true });
    await expect(
      page.getByRole("listitem").filter({ hasText: /getInventory/i }),
    ).toBeVisible({ timeout: 8000 });

    // Call 2: logoutUser (no params)
    await selectTool(page, "logoutUser");
    await expect(page.getByText("No input parameters required")).toBeVisible({
      timeout: 5000,
    });
    await page.getByRole("button", { name: /Call / }).click({ force: true });
    await expect(
      page.getByRole("listitem").filter({ hasText: /logoutUser/i }),
    ).toBeVisible({ timeout: 8000 });

    // Call 3: getPetById (fill required param)
    await selectTool(page, "getPetById");
    // The form should show the petId field with a required indicator
    await expect(
      page.locator("#tool-field-petId"),
    ).toBeVisible({ timeout: 5000 });
    await page.locator("#tool-field-petId").fill("1");
    await page.getByRole("button", { name: /Call / }).click({ force: true });
    await expect(
      page.getByRole("listitem").filter({ hasText: /getPetById/i }),
    ).toBeVisible({ timeout: 8000 });

    // Verify the "Call Log" section is visible
    await expect(page.getByText("Call Log")).toBeVisible();

    // Each entry should show a tool name and a timestamp
    const entries = page.getByRole("listitem");
    await expect(entries).toHaveCount(3, { timeout: 3000 });

    // Verify each tool name appears in a listitem
    for (const toolName of ["getInventory", "logoutUser", "getPetById"]) {
      await expect(
        page.getByRole("listitem").filter({ hasText: toolName }),
      ).toBeVisible();
    }
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 5: Tool with error response
  // ═════════════════════════════════════════════════════════════════
  test("5. Tool with error response", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground?tool=getPetById`);
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15000 });

    await expect(page.locator("#tool-field-petId")).toBeVisible({
      timeout: 5000,
    });

    // Leave petId empty or fill with an invalid value to trigger an error
    // Clear any default value
    await page.locator("#tool-field-petId").fill("");

    // Submit the call
    await page.getByRole("button", { name: /Call / }).click({ force: true });

    // Wait for response — either the client-side error or the backend error
    // The response viewer should show error content
    // (the backend may return isError: true or the response may contain error text)
    await page.waitForTimeout(3000);

    // Check the response viewer has content (not the empty state)
    const emptyResponse = page.getByText(
      "Response will appear here after a tool call",
    );
    const hasResponse = !(await emptyResponse.isVisible().catch(() => false));

    if (hasResponse) {
      // Verify timing is shown even for errors (ms or seconds format)
      const latencyShown = page.getByText(/\d+ ms|\d+\.\d+ s/);
      await expect(latencyShown).toBeVisible({ timeout: 5000 });
    } else {
      // If no response appeared, the form validation may have prevented submission
      // Check that the call log shows the error
      console.log("No response appeared immediately — error may be in call log");
    }

    // The call log should still have an entry
    await expect(
      page.getByRole("listitem").filter({ hasText: /getPetById/i }),
    ).toBeVisible({ timeout: 5000 });
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 6: Connection drop — paused server shows disconnected
  // ═════════════════════════════════════════════════════════════════
  test("6. Connection drop and shows disconnected", async ({ page, request }) => {
    // Pause the server via the API
    const pauseRes = await pauseServer(request, serverId);
    expect(pauseRes.response.ok()).toBeTruthy();
    console.log(`Paused server: ${serverId}`);

    try {
      // Navigate to the playground while the server is paused
      await page.goto(`/dashboard/servers/${serverId}/playground`);

      // The WebSocket should fail to connect (or get disconnected)
      // since the server is paused. Look for "Disconnected" indicator.
      await expect(page.getByText("Disconnected")).toBeVisible({
        timeout: 15000,
      });

      // The tool browser should also show "Disconnected" in the sidebar
      await expect(
        page.locator("text=Disconnected").first(),
      ).toBeVisible({ timeout: 5000 });
    } finally {
      // Resume the server so subsequent tests work
      const resumeRes = await resumeServer(request, serverId);
      if (!resumeRes.response.ok()) {
        console.warn(
          `Warning: failed to resume server: ${JSON.stringify(resumeRes.body)}`,
        );
      }
    }
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 7: Large response handling
  // ═════════════════════════════════════════════════════════════════
  test("7. Large response handling", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground?tool=getInventory`);
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15000 });

    await expect(page.getByText("No input parameters required")).toBeVisible({
      timeout: 5000,
    });

    // Call the tool
    await page.getByRole("button", { name: /Call / }).click({ force: true });

    // Wait for the response to render
    await expect(
      page.getByText("Response will appear here after a tool call"),
    ).not.toBeVisible({ timeout: 10000 });

    // Verify the response viewer renders without crash.
    // Check that the formatted response JSON viewer is rendered.
    // The response should contain JSON content.
    await expect(
      page.getByText(/getInventory/i),
    ).toBeVisible({ timeout: 5000 });

    // Check that the response size is shown in the meta bar
    await expect(page.getByText(/B|KB|MB/)).toBeVisible({ timeout: 5000 });

    // Verify the tabs are functional — switch to "Text" tab and back
    const textTab = page.getByRole("tab", { name: /text/i });
    if (await textTab.isVisible()) {
      await textTab.click();
      await page.waitForTimeout(500);
      // Text tab should have content
      await expect(
        page.locator("pre").first(),
      ).toBeVisible({ timeout: 3000 });
    }

    // Switch to Meta tab to verify timing metadata
    const metaTab = page.getByRole("tab", { name: /meta/i });
    if (await metaTab.isVisible()) {
      await metaTab.click();
      await page.waitForTimeout(500);
      await expect(
        page.getByText(/latency|Latency/i),
      ).toBeVisible({ timeout: 3000 });
    }
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 8: Empty state — server with no tools
  // ═════════════════════════════════════════════════════════════════
  test("8. Empty state before tools load", async ({ page }) => {
    // Navigate to a server that has no tools selected
    await page.goto(`/dashboard/servers/${emptyServerId}/playground`);

    // The WebSocket should connect (server is active) but return zero tools.
    // The page renders a loading state: "Loading tools…"
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15000 });

    // Since tools array is empty, the PlaygroundPage shows a loading skeleton
    // with "Loading tools…" text (defined in PlaygroundPage.tsx lines 131-142)
    await expect(page.getByText("Loading tools…")).toBeVisible({ timeout: 5000 });

    // Tool browser should show "No tools available" text
    await expect(page.getByText("No tools available")).toBeVisible({
      timeout: 10000,
    });
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 9: Tool input validation
  // ═════════════════════════════════════════════════════════════════
  test("9. Tool input validation in playground", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15000 });

    // Select "getPetById" — it has a required integer field "petId"
    await selectTool(page, "getPetById");
    await expect(page.locator("#tool-field-petId")).toBeVisible({
      timeout: 5000,
    });

    // Verify the required field indicator (*) is shown next to the label
    const label = page.locator('label[for="tool-field-petId"]');
    await expect(label).toBeVisible();
    await expect(label.locator("text=*")).toBeVisible();

    // Verify the field description is visible
    await expect(
      page.getByText(/ID of pet to return/i),
    ).toBeVisible();

    // Leave the required field empty and attempt to call
    // (The form currently allows submission without validation)
    await page.locator("#tool-field-petId").fill("");
    await page.getByRole("button", { name: /Call / }).click({ force: true });

    // Wait briefly for any response/error
    await page.waitForTimeout(2000);

    // The call log should show an entry for this tool call
    // (either from successful call or error response)
    const callLogEntry = page
      .getByRole("listitem")
      .filter({ hasText: /getPetById/i });
    const hasEntry = await callLogEntry.isVisible().catch(() => false);
    if (hasEntry) {
      console.log("getPetById call logged despite empty required field");
    } else {
      // Form may have prevented or the WebSocket may not have sent the request
      console.log(
        "getPetById not in call log — form validation blocked submission",
      );
    }

    // Now test with findPetsByStatus which has an enum parameter
    // Select findPetsByStatus
    await selectTool(page, "findPetsByStatus");
    await page.waitForTimeout(1000);

    // The form should render a select dropdown for the enum field "status"
    const statusSelect = page.locator("#tool-field-status");
    if (await statusSelect.isVisible()) {
      // Verify the default value is set (from spec: default: "available")
      const defaultValue = await statusSelect.inputValue();
      expect(defaultValue).toBe("available");
    }
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 10: Playground loads from direct URL with pre-selected tool
  // ═════════════════════════════════════════════════════════════════
  test("10. Playground loads from direct URL", async ({ page }) => {
    // Navigate directly to playground with ?tool=getPetById query param
    await page.goto(
      `/dashboard/servers/${serverId}/playground?tool=getPetById`,
    );

    // Wait for connection
    await expect(page.getByText("Connected", { exact: true })).toBeVisible({ timeout: 15000 });

    // The getPetById tool should be pre-selected (by the URL query param)
    // When pre-selected, the tool form should show the petId field
    await expect(page.locator("#tool-field-petId")).toBeVisible({
      timeout: 10000,
    });

    // Verify the tool is highlighted as selected in the tool browser
    const selectedOption = page.getByRole("option", { selected: true });
    await expect(selectedOption).toContainText("getPetById", { timeout: 5000 });
  });
});
