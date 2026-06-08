import { test, expect } from "@playwright/test";
import {
  mockAuthMe,
  mockSpecFetchSuccess,
  mockSelectTools,
  mockBuildStart,
  mockBuildStatusSSE,
  mockServerDetail,
} from "./helpers";

test.describe("Create server from OpenAPI URL", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthMe(page);
  });

  test("completes the full 4-step wizard via URL fetch", async ({ page }) => {
    await mockSpecFetchSuccess(page);
    await mockSelectTools(page);
    await mockBuildStart(page);
    await mockBuildStatusSSE(page);
    await mockServerDetail(page);

    await page.goto("/dashboard/servers/new");
    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible();

    // Step 1: Fill URL and fetch
    await page.getByLabel("OpenAPI Spec URL").fill("https://example.com/spec.json");
    await page.getByRole("button", { name: "Fetch Spec" }).click();

    // Step 2: Tool selection
    await expect(page.locator('section[aria-label="Step 2: Select Tools"]')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("list_pets")).toBeVisible();
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 3: Server config
    await expect(page.locator('section[aria-label="Step 3: Configure Server"]')).toBeVisible();
    await page.getByLabel("Server name").fill("Test Server");
    await page.getByLabel("Base URL").fill("https://api.example.com");
    await page.getByRole("button", { name: "Save and Continue" }).click();
    await expect(page.getByText("Continue to Build")).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Continue to Build" }).click();

    // Step 4: Build progress
    await expect(page.locator('section[aria-label="Step 4: Build Progress"]')).toBeVisible();
    await expect(page.getByText("Build complete", { exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: /view server/i })).toBeVisible();
  });
});
