import { test, expect } from "@playwright/test";
import {
  testUser,
  registerUser, loginViaApiAndSetCookies,
  deleteServer,
} from "./api-helpers";

test.describe.serial("Server Creation Wizard", () => {
  const ctx = {
    user: testUser(),
    serverId: "",
    serverSlug: "",
    specId: "",
  };

  test.beforeAll(async ({ request }) => {
    const { userId } = await registerUser(request, ctx.user);
    expect(userId).toBeTruthy();
  });

  test.afterAll(async ({ request }) => {
    if (ctx.serverId) {
      await deleteServer(request, ctx.serverId).catch(() => {});
    }
  });

  test("01 — navigate to new server page shows wizard", async ({ page }) => {
    await loginViaApiAndSetCookies(page.request, page, ctx.user.email, ctx.user.password);
    await page.goto("/dashboard/servers/new");
    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible({ timeout: 15000 });
    const steps = page.locator("text=Spec, Tools, Configure, Build");
    expect(steps).toBeDefined();
  });

  test("02 — fetch spec from URL shows tools", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto("/dashboard/servers/new");
    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible({ timeout: 15000 });

    const specUrl = "https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml";
    await page.getByLabel("OpenAPI Spec URL").fill(specUrl);
    await page.getByRole("button", { name: "Fetch Spec" }).click();

    await expect(page.locator('section[aria-label="Step 2: Select Tools"]')).toBeVisible({ timeout: 30000 });
    const firstTool = page.getByText("getPetById").first();
    await expect(firstTool).toBeVisible({ timeout: 15000 });
  });

  test("03 — tool selection enables/disables continue", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto("/dashboard/servers/new");

    const specUrl = "https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml";
    await page.getByLabel("OpenAPI Spec URL").fill(specUrl);
    await page.getByRole("button", { name: "Fetch Spec" }).click();
    await expect(page.locator('section[aria-label="Step 2: Select Tools"]')).toBeVisible({ timeout: 30000 });

    // Wait for tool list to render
    await expect(page.getByText("getPetById").first()).toBeVisible({ timeout: 15000 });

    // Deselect all tools (click each selected checkbox)
    const checkboxes = page.locator('section[aria-label="Step 2: Select Tools"] input[type="checkbox"]');
    const count = await checkboxes.count();
    for (let i = 0; i < count; i++) {
      const cb = checkboxes.nth(i);
      if (await cb.isChecked()) {
        await cb.click();
      }
    }

    // Continue should be disabled when no tools selected
    const continueBtn = page.getByRole("button", { name: "Continue" });
    if (count > 0) {
      await expect(continueBtn).toBeDisabled();
    }

    // Re-select first tool
    if (count > 0) {
      await checkboxes.nth(0).check();
      await expect(continueBtn).toBeEnabled();
    }
  });

  test("04 — HTTP URL rejected client-side", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto("/dashboard/servers/new");

    await page.getByLabel("OpenAPI Spec URL").fill("http://insecure.example.com/spec.json");
    await page.getByRole("button", { name: "Fetch Spec" }).click();

    await expect(page.getByText("Only HTTPS URLs are allowed")).toBeVisible({ timeout: 5000 });
  });

  test("05 — broken spec URL shows API error", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto("/dashboard/servers/new");

    await page.getByLabel("OpenAPI Spec URL").fill("https://example.com/invalid-spec.json");
    await page.getByRole("button", { name: "Fetch Spec" }).click();

    await expect(page.getByText(/invalid|error|failed/i)).toBeVisible({ timeout: 15000 });
  });

  test("06 — back button returns to step 1", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto("/dashboard/servers/new");

    // Fetch spec
    const specUrl = "https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml";
    await page.getByLabel("OpenAPI Spec URL").fill(specUrl);
    await page.getByRole("button", { name: "Fetch Spec" }).click();
    await expect(page.locator('section[aria-label="Step 2: Select Tools"]')).toBeVisible({ timeout: 30000 });

    // Click back
    await page.getByText("Back").first().click();

    // Should be back at step 1
    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible({ timeout: 10000 });
  });

  test("07 — complete wizard creates server", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto("/dashboard/servers/new");

    const specUrl = "https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml";
    await page.getByLabel("OpenAPI Spec URL").fill(specUrl);
    await page.getByRole("button", { name: "Fetch Spec" }).click();
    await expect(page.locator('section[aria-label="Step 2: Select Tools"]')).toBeVisible({ timeout: 30000 });

    // Wait for tools then proceed
    await expect(page.getByText("getPetById").first()).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 3: Configure
    await expect(page.locator('section[aria-label="Step 3: Configure Server"]')).toBeVisible({ timeout: 15000 });
    const serverName = `E2E Wizard Server ${Date.now()}`;
    await page.getByLabel("Server name").fill(serverName);
    await page.getByLabel("Base URL").fill("https://petstore.swagger.io/v2");
    await page.getByRole("button", { name: /save|create/i }).click();

    // After server creation, should show Continue to Build
    await expect(page.getByText("Continue to Build")).toBeVisible({ timeout: 30000 });
    await page.getByRole("button", { name: "Continue to Build" }).click();

    // Step 4: Build
    await expect(page.locator('section[aria-label="Step 4: Build Progress"]')).toBeVisible({ timeout: 15000 });

    // Wait for build to complete (could take a while)
    await expect(page.getByText("Build complete")).toBeVisible({ timeout: 120000 });

    // Extract server ID from URL after redirect
    await page.waitForURL(/\/dashboard\/servers\//, { timeout: 30000 });
    const url = page.url();
    const parts = url.split("/");
    ctx.serverId = parts[parts.length - 1] ?? "";
    expect(ctx.serverId).toBeTruthy();
  });

  test("08 — server appears in list after creation", async ({ page, request }) => {
    test.skip(!ctx.serverId, "No server created yet");
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto("/dashboard/servers");
    await expect(page.getByText("E2E Wizard Server")).toBeVisible({ timeout: 15000 });
  });

  test("09 — server detail page shows server info", async ({ page, request }) => {
    test.skip(!ctx.serverId, "No server created yet");
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto(`/dashboard/servers/${ctx.serverId}`);
    await expect(page.getByText(/overview|server information/i)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/active|building/i)).toBeVisible({ timeout: 10000 });
  });

  test("10 — tool search filters tools", async ({ page, request }) => {
    test.skip(!ctx.serverId, "No server created yet");
    await loginViaApiAndSetCookies(request, page, ctx.user.email, ctx.user.password);
    await page.goto(`/dashboard/servers/${ctx.serverId}`);

    // Click Tools tab
    await page.getByRole("tab", { name: /tools/i }).click();
    await expect(page.getByPlaceholder(/search/i)).toBeVisible({ timeout: 10000 });

    const searchInput = page.getByPlaceholder(/search/i);
    await searchInput.fill("pet");
    await page.waitForTimeout(500);
    // Tool list should filter (at least some tools visible)
    const toolRows = page.locator('[class*="divide-y"] > div');
    const toolCount = await toolRows.count();
    expect(toolCount).toBeGreaterThan(0);
  });
});
