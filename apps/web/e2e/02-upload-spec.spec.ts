import { test, expect } from "@playwright/test";
import {
  mockAuthMe,
  mockUploadSuccess,
  mockSelectTools,
  mockBuildStart,
  mockBuildStatusSSE,
  mockServerDetail,
} from "./helpers";

test.describe("Create server by uploading a spec file", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthMe(page);
  });

  test("completes the full 4-step wizard via file upload", async ({ page }) => {
    await mockUploadSuccess(page);
    await mockSelectTools(page);
    await mockBuildStart(page);
    await mockBuildStatusSSE(page);
    await mockServerDetail(page);

    await page.goto("/dashboard/servers/new");
    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible();

    // Step 1: Switch to Upload tab and pick a file
    await page.getByRole("tab", { name: /upload file/i }).click();
    await expect(page.getByText(/drop your openapi spec/i)).toBeVisible();

    // Upload using the file chooser (hidden input with type=file)
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByText(/browse files/i).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: "spec.yaml",
      mimeType: "application/x-yaml",
      buffer: Buffer.from('openapi: "3.0.3"\ninfo:\n  title: Test\n  version: "1.0"\npaths: {}'),
    });

    // Wait for the upload API call and success
    await expect(page.locator('section[aria-label="Step 2: Select Tools"]')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("get_item")).toBeVisible();

    // Step 2: Continue with tools selected
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 3: Server config + credentials
    await expect(page.locator('section[aria-label="Step 3: Configure Server"]')).toBeVisible();
    await page.getByLabel("Server name").fill("Uploaded API Server");
    await page.getByLabel("Base URL").fill("https://api.example.com");
    await page.getByRole("button", { name: "Save and Continue" }).click();
    await expect(page.getByText("Continue to Build")).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Continue to Build" }).click();

    // Step 4: Build
    await expect(page.locator('section[aria-label="Step 4: Build Progress"]')).toBeVisible();
    await expect(page.getByText("Build complete", { exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: /view server/i })).toBeVisible();
  });
});
