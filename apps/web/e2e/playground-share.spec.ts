/**
 * Comprehensive Playwright E2E tests for the playground share feature.
 *
 * CRITICAL: These tests connect to the REAL backend WebSocket.
 * No page.route() or routeWebSocket() mocks are used.
 *
 * The share feature generates a client-side URL with tool name and params
 * encoded as query parameters, copies it to clipboard, and shows a toast.
 *
 * Prerequisites:
 *   - Backend running at http://localhost:8000
 *   - Frontend dev server running at http://localhost:3000
 *   - Docker/Postgres/Redis running (or CI equivalents)
 *
 * Each test in this serial group builds on shared state:
 *   a registered user, a built server with real tools, and auth cookies.
 */

import { test, expect, type Page } from "@playwright/test";
import {
  testUser,
  registerUser,
  loginUser,
  fetchSpec,
  selectToolsAndCreateServer,
  deleteServer,
  getTools,
  pauseServer,
  resumeServer,
  loginViaApiAndSetCookies,
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
  "getPetById",
  "findPetsByStatus",
  "logoutUser",
  "getUserByName",
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
 * Read clipboard text content (requires clipboard permissions).
 */
async function readClipboard(
  page: Page,
): Promise<string> {
  try {
    return await page.evaluate(() => navigator.clipboard.readText());
  } catch {
    return "";
  }
}

// ── Serial test group ─────────────────────────────────────────────────

test.describe.serial("Playground Share E2E", () => {
  // ── Shared state ──────────────────────────────────────────────────
  let user: ReturnType<typeof testUser>;
  let serverId: string;
  let serverSlug: string;
  let toolNames: string[];
  let authCookies: { name: string; value: string }[];

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

    // 3. Select tools and create the server
    const ts = Date.now();
    const createRes = await selectToolsAndCreateServer(request, specId, {
      name: `E2E Share ${ts}`,
      slug: `e2e-share-${ts}`,
      baseUrl: BASE_URL,
      toolNames: SELECTED_TOOLS,
      description: "E2E playground share test server",
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

    // 6. Login to get auth cookies for the browser tests
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
  });

  // ── beforeEach: set auth cookies + clipboard permissions ──────────
  test.beforeEach(async ({ page }) => {
    await setAuthCookies(page, authCookies);
    // Grant clipboard permissions so we can verify share URL content
    await page
      .context()
      .grantPermissions(["clipboard-read", "clipboard-write"])
      .catch(() => {
        // Non-critical — some browsers/environments may not support this
      });
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 1: Share button is disabled before any tool call
  // ═════════════════════════════════════════════════════════════════
  test("1. Share button is disabled before any tool call", async ({
    page,
  }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);

    // Wait for WebSocket connection and tools to load
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // Share button should be disabled initially — no successful call yet
    const shareButton = page.getByRole("button", { name: /share/i });
    await expect(shareButton).toBeDisabled();

    // Tooltip should indicate why
    await shareButton.hover();
    await expect(page.getByText(/complete a tool call first/i)).toBeVisible({
      timeout: 3000,
    });
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 2: Call a tool, then share
  // ═════════════════════════════════════════════════════════════════
  test("2. Call a tool, then share", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // Select getPetById (has a required integer param)
    await page.getByRole("option", { name: /getPetById/i }).click();
    await expect(page.locator("#tool-field-petId")).toBeVisible({
      timeout: 5000,
    });
    await page.locator("#tool-field-petId").fill("5");

    // Call the tool
    await page.getByRole("button", { name: /call tool/i }).click();

    // Wait for response — timing indicator means call completed
    await expect(page.getByText(/ms/)).toBeVisible({ timeout: 15000 });

    // Share button should now be enabled
    const shareButton = page.getByRole("button", { name: /share/i });
    await expect(shareButton).toBeEnabled();

    // Click Share
    await shareButton.click();

    // Read the clipboard to verify the share URL
    const shareUrl = await readClipboard(page);
    expect(shareUrl).toBeTruthy();
    expect(shareUrl).toContain("/dashboard/servers/");
    expect(shareUrl).toContain(serverSlug);
    expect(shareUrl).toContain("tool=getPetById");
    expect(shareUrl).toContain("params=");
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 3: Copied to clipboard notification
  // ═════════════════════════════════════════════════════════════════
  test("3. Copied to clipboard notification", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // Use getInventory (no params needed)
    await page.getByRole("option", { name: /getInventory/i }).click();
    await expect(page.getByText("No input parameters required")).toBeVisible({
      timeout: 5000,
    });
    await page.getByRole("button", { name: /call tool/i }).click();
    await expect(page.getByText(/ms/)).toBeVisible({ timeout: 15000 });

    // Click Share
    await page.getByRole("button", { name: /share/i }).click();

    // Verify the toast notification appears
    await expect(page.getByText(/share url copied/i)).toBeVisible({
      timeout: 3000,
    });
    await expect(page.getByText(/paste it in a browser/i)).toBeVisible({
      timeout: 3000,
    });
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 4: Share URL payload verification
  // ═════════════════════════════════════════════════════════════════
  test("4. Share URL contains correct tool name and parameters", async ({
    page,
  }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // Select findPetsByStatus and pick "sold"
    await page.getByRole("option", { name: /findPetsByStatus/i }).click();
    await page.waitForTimeout(1000);

    // findPetsByStatus has an enum select for status
    const statusSelect = page.locator("#tool-field-status");
    await expect(statusSelect).toBeVisible({ timeout: 5000 });
    await statusSelect.selectOption("sold");

    // Call the tool
    await page.getByRole("button", { name: /call tool/i }).click();
    await expect(page.getByText(/ms/)).toBeVisible({ timeout: 15000 });

    // Share
    await page.getByRole("button", { name: /share/i }).click();
    await expect(page.getByText(/share url copied/i)).toBeVisible({
      timeout: 3000,
    });

    // Verify clipboard URL contains correct tool and params
    const shareUrl = await readClipboard(page);
    expect(shareUrl).toContain("tool=findPetsByStatus");

    // Parse the params from URL and verify content
    const urlObj = new URL(shareUrl);
    const paramsJson = urlObj.searchParams.get("params");
    expect(paramsJson).not.toBeNull();

    const params = JSON.parse(paramsJson!);
    expect(params).toHaveProperty("status", "sold");
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 5: Pre-selected tool from query param
  // ═════════════════════════════════════════════════════════════════
  test("5. Pre-selected tool from query param", async ({ page }) => {
    // Navigate with ?tool=logoutUser in URL
    await page.goto(
      `/dashboard/servers/${serverId}/playground?tool=logoutUser`,
    );
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // logoutUser should be pre-selected by the URL query param
    const selectedOption = page.getByRole("option", { selected: true });
    await expect(selectedOption).toContainText("logoutUser", {
      timeout: 5000,
    });

    // Share button should still be disabled — no call made yet
    const shareButton = page.getByRole("button", { name: /share/i });
    await expect(shareButton).toBeDisabled();
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 6: Open shared URL in incognito browser context
  // ═════════════════════════════════════════════════════════════════
  test("6. Open shared URL in new browser context", async ({
    page,
    browser,
    request,
  }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // Select and call getPetById with petId=42
    await page.getByRole("option", { name: /getPetById/i }).click();
    await expect(page.locator("#tool-field-petId")).toBeVisible({
      timeout: 5000,
    });
    await page.locator("#tool-field-petId").fill("42");
    await page.getByRole("button", { name: /call tool/i }).click();
    await expect(page.getByText(/ms/)).toBeVisible({ timeout: 15000 });

    // Share and capture the URL
    await page.getByRole("button", { name: /share/i }).click();
    await expect(page.getByText(/share url copied/i)).toBeVisible({
      timeout: 3000,
    });
    const shareUrl = await readClipboard(page);
    expect(shareUrl).toBeTruthy();

    // Open a new browser context (incognito-like, separate cookie store)
    const secondContext = await browser.newContext();
    try {
      // Log in with the same credentials in the new context
      const secondPage = await secondContext.newPage();
      await loginViaApiAndSetCookies(
        request,
        secondPage,
        user.email,
        user.password,
      );

      // Navigate to the share URL in the incognito context
      await secondPage.goto(shareUrl);

      // Should connect and have the tool pre-selected from the URL?s ?tool param
      await expect(secondPage.getByText("Connected")).toBeVisible({
        timeout: 15000,
      });

      // getPetById should be pre-selected
      const selected = secondPage.getByRole("option", { selected: true });
      await expect(selected).toContainText("getPetById", { timeout: 5000 });
    } finally {
      await secondContext.close();
    }
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 7: Multiple share sessions with different parameters
  // ═════════════════════════════════════════════════════════════════
  test("7. Multiple share sessions with different parameters", async ({
    page,
  }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    const sharedUrls: string[] = [];

    // ── Share 1: getPetById with petId=100 ──────────────────────────
    await page.getByRole("option", { name: /getPetById/i }).click();
    await expect(page.locator("#tool-field-petId")).toBeVisible({
      timeout: 5000,
    });
    await page.locator("#tool-field-petId").fill("100");
    await page.getByRole("button", { name: /call tool/i }).click();
    await expect(page.getByText(/ms/)).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: /share/i }).click();
    await expect(page.getByText(/share url copied/i)).toBeVisible({
      timeout: 3000,
    });
    sharedUrls.push(await readClipboard(page));

    // ── Share 2: findPetsByStatus with status=available ─────────────
    await page.getByRole("option", { name: /findPetsByStatus/i }).click();
    await page.waitForTimeout(1000);
    const statusSelect = page.locator("#tool-field-status");
    await expect(statusSelect).toBeVisible({ timeout: 5000 });
    await statusSelect.selectOption("available");
    await page.getByRole("button", { name: /call tool/i }).click();
    await expect(page.getByText(/ms/)).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: /share/i }).click();
    await expect(page.getByText(/share url copied/i)).toBeVisible({
      timeout: 3000,
    });
    sharedUrls.push(await readClipboard(page));

    // ── Share 3: logoutUser (no params) ────────────────────────────
    await page.getByRole("option", { name: /logoutUser/i }).click();
    await expect(page.getByText("No input parameters required")).toBeVisible({
      timeout: 5000,
    });
    await page.getByRole("button", { name: /call tool/i }).click();
    await expect(page.getByText(/ms/)).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: /share/i }).click();
    await expect(page.getByText(/share url copied/i)).toBeVisible({
      timeout: 3000,
    });
    sharedUrls.push(await readClipboard(page));

    // ── Verify all 3 URLs are unique ────────────────────────────────
    expect(sharedUrls).toHaveLength(3);
    expect(new Set(sharedUrls).size).toBe(3);

    // Each URL references a different tool
    const tools = sharedUrls.map(
      (url) => new URL(url).searchParams.get("tool"),
    );
    expect(tools).toContain("getPetById");
    expect(tools).toContain("findPetsByStatus");
    expect(tools).toContain("logoutUser");
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 8: Shared URLs are permanent (no server-side expiration)
  // ═════════════════════════════════════════════════════════════════
  test("8. Shared URLs are permanent (no expiration)", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // Make a call and share it
    await page.getByRole("option", { name: /getInventory/i }).click();
    await expect(page.getByText("No input parameters required")).toBeVisible({
      timeout: 5000,
    });
    await page.getByRole("button", { name: /call tool/i }).click();
    await expect(page.getByText(/ms/)).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: /share/i }).click();
    await expect(page.getByText(/share url copied/i)).toBeVisible({
      timeout: 3000,
    });

    const shareUrl = await readClipboard(page);

    // Client-side share URLs are permanent — no expiration field present
    expect(shareUrl).toContain("tool=getInventory");
    expect(shareUrl).not.toContain("expires");
    expect(shareUrl).not.toContain("share_token");
    expect(shareUrl).not.toContain("share_id");

    // Navigate directly to the share URL to verify it's still functional
    await page.goto(shareUrl);
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // getInventory should be pre-selected from the URL
    const selected = page.getByRole("option", { selected: true });
    await expect(selected).toContainText("getInventory", { timeout: 5000 });
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 9: Share disabled when disconnected (server paused)
  // ═════════════════════════════════════════════════════════════════
  test("9. Share disabled when disconnected", async ({ page, request }) => {
    // Pause server to force WebSocket disconnection
    const pauseRes = await pauseServer(request, serverId);
    expect(pauseRes.response.ok()).toBeTruthy();
    console.log(`Paused server: ${serverId}`);

    try {
      await page.goto(`/dashboard/servers/${serverId}/playground`);

      // Should show disconnected state
      await expect(page.getByText("Disconnected")).toBeVisible({
        timeout: 15000,
      });

      // Share button must be disabled — no call possible while disconnected
      const shareButton = page.getByRole("button", { name: /share/i });
      await expect(shareButton).toBeDisabled();

      // Tooltip should indicate why
      await shareButton.hover();
      await expect(page.getByText(/complete a tool call first/i)).toBeVisible({
        timeout: 3000,
      });
    } finally {
      // Always resume so subsequent tests work
      const resumeRes = await resumeServer(request, serverId);
      if (!resumeRes.response.ok()) {
        console.warn(
          `Warning: failed to resume server: ${JSON.stringify(resumeRes.body)}`,
        );
      }
    }
  });

  // ═════════════════════════════════════════════════════════════════
  //  TEST 10: Share disabled after error tool call
  // ═════════════════════════════════════════════════════════════════
  test("10. Share disabled after error tool call", async ({ page }) => {
    await page.goto(`/dashboard/servers/${serverId}/playground`);
    await expect(page.getByText("Connected")).toBeVisible({ timeout: 15000 });

    // Select getPetById and submit with empty petId to trigger an error
    await page.getByRole("option", { name: /getPetById/i }).click();
    await expect(page.locator("#tool-field-petId")).toBeVisible({
      timeout: 5000,
    });
    await page.locator("#tool-field-petId").fill("");

    // Call tool — the backend should return an error for invalid/missing petId
    await page.getByRole("button", { name: /call tool/i }).click();

    // Wait for the call to complete (error or not)
    await page.waitForTimeout(3000);

    // Share button must remain disabled — error calls don't count as successful
    const shareButton = page.getByRole("button", { name: /share/i });
    await expect(shareButton).toBeDisabled();

    // The call log should still show an entry for this call
    await expect(
      page.getByRole("listitem").filter({ hasText: /getPetById/i }),
    ).toBeVisible({ timeout: 5000 });
  });
});
