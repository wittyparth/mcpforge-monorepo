/**
 * Comprehensive Playwright E2E tests for API key management (F7).
 *
 * CRITICAL: Uses REAL API calls via Playwright's `request` fixture.
 * NO page.route() mocks.
 *
 * Tests cover the full lifecycle: empty state, creation, listing, copy,
 * scopes, validation, revocation, verification, multiple keys, and expiry.
 *
 * State-dependent tests run serially via test.describe.serial().
 */

import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import {
  API_BASE,
  testUser,
  registerUser,
  loginViaApiAndSetCookies,
  ensureCsrf,
  csrfHeaders,
} from "../e2e/api-helpers";

// ── Helpers ──────────────────────────────────────────────────────────────

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Login via API, inject cookies into the page context, and navigate to the
 * API keys settings page.
 */
async function loginAndGoToKeys(
  page: Page,
  request: APIRequestContext,
  email: string,
  password: string,
) {
  await loginViaApiAndSetCookies(request, page, email, password);
  await page.goto("/dashboard/settings/api-keys");
  await page.waitForLoadState("networkidle");
}

/**
 * Create an API key via the UI dialog and return the plaintext key.
 *
 * Steps:
 *  1. Clicks "Create API Key" button
 *  2. Fills the name field
 *  3. Toggles the given scopes
 *  4. Optionally selects an expiration from the dropdown
 *  5. Submits the form
 *  6. Waits for the KeyDisplayOnce dialog
 *  7. Returns the plaintext key shown in the dialog
 *
 * NOTE: Does NOT close the dialog — caller must dismiss it.
 */
async function createKeyViaDialog(
  page: Page,
  name: string,
  scopes: string[],
  expiryLabel?: string,
): Promise<string> {
  await page.getByRole("button", { name: /create.*api.*key/i }).click();

  // Fill name
  await page.getByLabel("Name").fill(name);

  // Select scopes — each scope is a button[role="checkbox"] wrapped in a
  // <label> whose accessible text includes the scope name.
  for (const scope of scopes) {
    await page.getByRole("checkbox", { name: new RegExp(scope, "i") }).click();
  }

  // Select expiration if specified
  if (expiryLabel) {
    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: expiryLabel }).click();
  }

  // Submit
  await page.getByRole("button", { name: /create key/i }).click();

  // Wait for the key display dialog — it has the heading "Save your API key"
  await expect(
    page.getByRole("heading", { name: /save your api key/i }),
  ).toBeVisible({ timeout: 10000 });

  // Extract the plaintext key from the <code> element in the dialog
  const plaintextKey = await page.locator("dialog code, [role='dialog'] code").last().textContent();
  expect(plaintextKey).toMatch(/^mcpforge_live_/);

  return plaintextKey ?? "";
}

/**
 * Dismiss the KeyDisplayOnce dialog by acknowledging and clicking Done.
 */
async function dismissKeyDisplay(page: Page) {
  await page.getByLabel("I've saved my key").check();
  await page.getByRole("button", { name: /done/i }).click();
  // Wait for the dialog to close
  await expect(
    page.getByRole("heading", { name: /save your api key/i }),
  ).not.toBeVisible({ timeout: 5000 }).catch(() => {});
}

// ── Test suite ───────────────────────────────────────────────────────────

test.describe.serial("API key management", () => {
  let user: ReturnType<typeof testUser>;
  // Shared across tests for the revoke verification scenario
  let capturedRevokedKeyPlaintext = "";
  let capturedRevokedKeyName = "";

  const createdEmails: string[] = [];

  test.beforeAll(async ({ request }) => {
    user = testUser();
    createdEmails.push(user.email);

    const reg = await registerUser(request, user);
    // 409 is OK if the user already exists from a previous (failed) run
    if (reg.response.status() !== 409) {
      expect(reg.response.ok()).toBeTruthy();
    }
  });

  test.afterAll(async ({ request }) => {
    // Clean up: revoke all active API keys for this user
    const loginRes = await request.post(`${API_BASE}/api/v1/auth/login`, {
      data: { email: user.email, password: user.password },
    });
    if (loginRes.ok()) {
      const listRes = await request.get(
        `${API_BASE}/api/v1/api-keys?include_revoked=true`,
      );
      if (listRes.ok()) {
        const data = await listRes.json();
        for (const key of data.items ?? []) {
          if (!key.revoked_at) {
            await request
              .delete(`${API_BASE}/api/v1/api-keys/${key.id}`)
              .catch(() => {});
          }
        }
      }
    }

    if (createdEmails.length > 0) {
      console.log(
        "E2E test users created — no admin delete API exists; clean up manually:",
        createdEmails.join(", "),
      );
    }
  });

  // ── 1. Empty state ─────────────────────────────────────────────────

  test("1. API keys page shows empty state", async ({ page, request, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    // Verify "API Keys" heading (use first() since h1 and h2 may both match)
    await expect(
      page.getByRole("heading", { name: /^api keys$/i }).first(),
    ).toBeVisible();

    // Verify the info card about API key usage
    await expect(page.getByText("About API Keys")).toBeVisible();
    await expect(
      page.getByText(/keys have the format/i),
    ).toBeVisible();
    await expect(
      page.getByText(/full key is shown only once/i),
    ).toBeVisible();
    await expect(
      page.getByText(/keys can be revoked but not recovered/i),
    ).toBeVisible();

    // Verify "No API keys" empty state
    await expect(
      page.getByText("You haven't created any API keys yet."),
    ).toBeVisible();

    // Verify "Create API Key" button is visible
    await expect(
      page.getByRole("button", { name: /create.*api.*key/i }),
    ).toBeVisible();
  });

  // ── 2. Create an API key ──────────────────────────────────────────

  test("2. Create an API key — full plaintext shown once", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    await page.getByRole("button", { name: /create.*api.*key/i }).click();

    // Fill in name
    await page.getByLabel("Name").fill("CI/CD Pipeline");

    // Select server:read scope
    await page
      .getByRole("checkbox", { name: /servers:read/i })
      .click();

    // Submit the form
    await page.getByRole("button", { name: /create key/i }).click();

    // Verify the "Save your API key" heading (KeyDisplayOnce dialog)
    await expect(
      page.getByRole("heading", { name: /save your api key/i }),
    ).toBeVisible({ timeout: 10000 });

    // Verify plaintext key is displayed (format: mcpforge_live_...)
    const keyText = await page
      .locator("[role='dialog'] code")
      .last()
      .textContent();
    expect(keyText).toMatch(/^mcpforge_live_/);

    // Verify the note about storing it securely
    await expect(
      page.getByText(/this is the only time/i),
    ).toBeVisible();
    await expect(
      page.getByText(/store it securely/i),
    ).toBeVisible();

    // Dismiss the dialog
    await dismissKeyDisplay(page);
  });

  // ── 3. Key appears in list after creation ─────────────────────────

  test("3. Key appears in list after creation — prefix only, not full key", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    const keyName = "List Visibility Test";
    const plaintext = await createKeyViaDialog(page, keyName, [
      "servers:read",
    ]);
    const prefix = plaintext.slice(0, 12);
    await dismissKeyDisplay(page);

    // Reload the page to get a fresh list from the API
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Verify the key name appears
    await expect(page.getByText(keyName)).toBeVisible();

    // Verify the key prefix (mcpforge_live_...) is shown
    await expect(page.getByText(`${prefix}...`)).toBeVisible();

    // Verify the PARTIAL key prefix is visible but NOT the full key
    // The full key is much longer (12 chars + more)
    await expect(page.getByText(plaintext)).not.toBeVisible();

    // Verify scopes column shows the scope
    await expect(page.getByText("servers:read")).toBeVisible();

    // Verify creation date column (relative date like "Today" or "1 days ago")
    await expect(page.getByText(/today|\d days? ago|yesterday/i)).toBeVisible();
  });

  // ── 4. Copy key button ────────────────────────────────────────────

  test("4. Copy key button works — clipboard verification", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    const keyName = "Copy Button Test";
    const plaintext = await createKeyViaDialog(page, keyName, [
      "servers:read",
    ]);

    // Click the copy button (button with accessible name "Copy key")
    await page.getByRole("button", { name: /copy key/i }).click();

    // Verify "Copied to clipboard!" message appears
    await expect(page.getByText("Copied to clipboard!")).toBeVisible({
      timeout: 3000,
    });

    // Verify clipboard contains the full plaintext key
    const clipboardText = await page.evaluate(() =>
      navigator.clipboard.readText(),
    );
    expect(clipboardText).toBe(plaintext);

    await dismissKeyDisplay(page);
  });

  // ── 5. Create key with all scopes ─────────────────────────────────

  test("5. Create key with all scopes — all permissions displayed", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    const allScopes = [
      "servers:read",
      "servers:write",
      "analytics:read",
      "admin",
    ];

    await page.getByRole("button", { name: /create.*api.*key/i }).click();
    await page.getByLabel("Name").fill("All Scopes Key");

    // Select all scopes
    for (const scope of allScopes) {
      await page.getByRole("checkbox", { name: new RegExp(scope, "i") }).click();
    }

    await page.getByRole("button", { name: /create key/i }).click();
    await expect(
      page.getByRole("heading", { name: /save your api key/i }),
    ).toBeVisible({ timeout: 10000 });

    await dismissKeyDisplay(page);

    // Reload and verify all scopes appear
    await page.reload();
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("All Scopes Key")).toBeVisible();
    for (const scope of allScopes) {
      await expect(page.getByText(scope)).toBeVisible();
    }
  });

  // ── 6. Invalid name validation ────────────────────────────────────

  test("6. Create key with invalid name — client-side validation", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    // ── Empty name ──────────────────────────────────────────────────
    await page.getByRole("button", { name: /create.*api.*key/i }).click();

    // Leave name empty
    await page.getByLabel("Name").fill("");

    // Try to submit
    await page.getByRole("button", { name: /create key/i }).click();

    // Verify client-side validation prevents submission
    await expect(page.getByText("Key name is required")).toBeVisible();

    // Dialog should still be open (submission blocked)
    await expect(
      page.getByRole("heading", { name: /create api key/i }),
    ).toBeVisible();

    // Cancel to close
    await page.getByRole("button", { name: /cancel/i }).click();

    // ── Very long name (over 100 chars) — backend rejects with 422 ─
    await page.getByRole("button", { name: /create.*api.*key/i }).click();
    const longName = "A".repeat(101);
    await page.getByLabel("Name").fill(longName);
    await page
      .getByRole("checkbox", { name: /servers:read/i })
      .click();

    // The frontend Zod schema has max(100), so client-side should block
    await page.getByRole("button", { name: /create key/i }).click();

    // Verify validation error about max length
    await expect(
      page.getByText(/key name must be less than/i),
    ).toBeVisible();
  });

  // ── 7. Revoke an API key ─────────────────────────────────────────

  test("7. Revoke an API key — confirmation dialog, status change", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    // Create a key to revoke — capture the plaintext for test 8
    capturedRevokedKeyName = "Key To Revoke";
    const plaintext = await createKeyViaDialog(page, capturedRevokedKeyName, [
      "servers:read",
    ]);
    capturedRevokedKeyPlaintext = plaintext;
    const prefix = plaintext.slice(0, 12);
    await dismissKeyDisplay(page);

    // Reload to ensure the key appears in the table
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(capturedRevokedKeyName)).toBeVisible();

    // Click the actions dropdown on the row for this key
    // The table row has an "Actions" button (sr-only text) for non-revoked keys
    const actionsButton = page
      .locator("tr")
      .filter({ hasText: capturedRevokedKeyName })
      .getByRole("button", { name: /actions/i });
    await actionsButton.click();

    // Click Revoke in the dropdown menu
    await page.getByRole("menuitem", { name: /revoke/i }).click();

    // Verify confirmation dialog appears with warning about irreversibility
    await expect(
      page.getByRole("heading", { name: /revoke api key/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/this action cannot be undone/i),
    ).toBeVisible();
    await expect(
      page.getByText(/will stop working immediately/i),
    ).toBeVisible();

    // Confirm revocation
    await page.getByRole("button", { name: /revoke key/i }).click();

    // Wait for the revocation to complete and UI to update
    await sleep(1000);

    // Verify the key status changes to "Revoked" badge
    // The row should now show a "Revoked" badge
    const keyRow = page
      .locator("tr")
      .filter({ hasText: capturedRevokedKeyName });
    await expect(keyRow.getByText("Revoked")).toBeVisible({ timeout: 10000 });

    // Verify the key prefix is still shown but the row has reduced opacity
    await expect(keyRow.getByText(`${prefix}...`)).toBeVisible();
  });

  // ── 8. Verify revoked key cannot be used ──────────────────────────

  test("8. Verify revoked key cannot be used — API returns 401", async ({
    request,
  }) => {
    // Ensure we have a revoked key's plaintext from test 7
    expect(capturedRevokedKeyPlaintext).toMatch(/^mcpforge_live_/);

    // Try to use the revoked API key to authenticate an API call
    const res = await request.get(`${API_BASE}/api/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${capturedRevokedKeyPlaintext}`,
      },
    });

    // Verify the API returns 401 with appropriate error
    expect(res.status()).toBe(401);

    const body = await res.json();
    // The backend should indicate the key is invalid or revoked
    expect(body.error?.code).toBe("UNAUTHORIZED");
  });

  // ── 9. Multiple API keys ──────────────────────────────────────────

  test("9. Multiple API keys — independent creation and revocation", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    // Enable "Show revoked" so we can see all keys
    await page.getByLabel("Show revoked").check();

    // Create 3 keys with different names and scope combinations
    const keys = [
      { name: "Multi-Key Alpha", scopes: ["servers:read"] },
      { name: "Multi-Key Beta", scopes: ["servers:read", "servers:write"] },
      {
        name: "Multi-Key Gamma",
        scopes: ["analytics:read", "admin"],
      },
    ];

    for (const key of keys) {
      const plaintext = await createKeyViaDialog(
        page,
        key.name,
        key.scopes,
      );
      expect(plaintext).toMatch(/^mcpforge_live_/);
      await dismissKeyDisplay(page);
    }

    // Reload to get a fresh list
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Verify all 3 appear in the list
    for (const key of keys) {
      await expect(page.getByText(key.name)).toBeVisible();
    }

    // Revoke the middle key (Beta) to test independent revocation
    const betaActions = page
      .locator("tr")
      .filter({ hasText: "Multi-Key Beta" })
      .getByRole("button", { name: /actions/i });
    await betaActions.click();
    await page.getByRole("menuitem", { name: /revoke/i }).click();
    await expect(
      page.getByRole("heading", { name: /revoke api key/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /revoke key/i }).click();
    await sleep(1000);

    // Verify Beta shows "Revoked" badge
    const betaRow = page
      .locator("tr")
      .filter({ hasText: "Multi-Key Beta" });
    await expect(betaRow.getByText("Revoked")).toBeVisible({ timeout: 10000 });

    // Verify Alpha and Gamma do NOT show "Revoked" (still active)
    const alphaRow = page
      .locator("tr")
      .filter({ hasText: "Multi-Key Alpha" });
    await expect(alphaRow.getByText("Revoked")).not.toBeVisible();

    const gammaRow = page
      .locator("tr")
      .filter({ hasText: "Multi-Key Gamma" });
    await expect(gammaRow.getByText("Revoked")).not.toBeVisible();
  });

  // ── 10. API key expiry validation ─────────────────────────────────

  test("10. API key expiry — past expiry rejected at creation, valid expiry displayed", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAndGoToKeys(page, request, user.email, user.password);

    // ── Part A: Try to create a key with invalid expiry via API ─────
    // The backend validates expires_in_days >= 1, so sending 0 should
    // be rejected with 422.
    await ensureCsrf(request);
    const invalidRes = await request.post(
      `${API_BASE}/api/v1/api-keys`,
      {
        data: {
          name: "Expired Key Test",
          scopes: ["servers:read"],
          expires_in_days: 0, // violates ge=1 validation
        },
        headers: { ...csrfHeaders() },
      },
    );
    expect(invalidRes.status()).toBe(422);
    const invalidBody = await invalidRes.json();
    // Pydantic validation error shape
    expect(invalidBody.detail?.[0]?.type ?? invalidBody.error?.code).toBeDefined();

    // ── Part B: Create a key with 30-day expiry via the UI ──────────
    const keyName = "Expiry 30 Day Test";
    await page.getByRole("button", { name: /create.*api.*key/i }).click();
    await page.getByLabel("Name").fill(keyName);
    await page
      .getByRole("checkbox", { name: /servers:read/i })
      .click();

    // Select "30 days" from the expiration dropdown
    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "30 days" }).click();
    await page.getByRole("button", { name: /create key/i }).click();
    await expect(
      page.getByRole("heading", { name: /save your api key/i }),
    ).toBeVisible({ timeout: 10000 });
    await dismissKeyDisplay(page);

    // Reload and verify the expiry info is shown
    await page.reload();
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(keyName)).toBeVisible();
    // The table should show "Expires in..." or "Expires in 30 days"
    await expect(
      page.getByText(/expires in \d+ days?/i),
    ).toBeVisible();

    // ── Part C: Verify the revoke-rejected key does NOT appear ─────
    await expect(
      page.getByText("Expired Key Test"),
    ).not.toBeVisible();
  });
});
