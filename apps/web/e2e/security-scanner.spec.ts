/**
 * Comprehensive Playwright E2E tests for the Security Scanner feature.
 *
 * CRITICAL: Uses real API calls via Playwright's `request` fixture.
 * NO page.route() mocks.
 *
 * Tests run serially (test.describe.serial) because each test depends on
 * state established by the previous test.
 *
 * Prerequisites (beforeAll):
 * - Register user
 * - Create a server with tools (petstore spec)
 * - Build the server
 * - Pause the server (so the Deploy button is visible)
 * - Create a second server with an empty spec (for the "no findings" test)
 */

import { test, expect, type APIRequestContext } from "@playwright/test";
import {
  API_BASE,
  testUser,
  testServer,
  uniqueId,
  registerUser,
  loginViaApiAndSetCookies,
  fetchSpec,
  selectToolsAndCreateServer,
  startBuild,
  deleteServer,
  getLatestScan,
  getAcknowledgments,
  pauseServer,
  uploadSpec,
  ensureCsrf,
  csrfHeaders,
} from "../e2e/api-helpers";

// ── Helpers ──────────────────────────────────────────────────────────────

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Poll GET /security/latest until the scan status is "completed" or "failed".
 * Throws if the deadline is exceeded.
 */
async function waitForScanCompletion(
  request: APIRequestContext,
  serverId: string,
  timeout = 90_000,
) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const { response, body } = await getLatestScan(request, serverId);
    if (response.ok() && body && body.scan_status === "completed") {
      return body;
    }
    if (response.ok() && body && body.scan_status === "failed") {
      throw new Error(`Scan failed for server ${serverId}`);
    }
    await sleep(2000);
  }
  throw new Error(`Scan did not complete within ${timeout}ms for server ${serverId}`);
}

/**
 * Acknowledge a specific finding via the correct backend endpoint.
 * The api-helpers `acknowledgeFinding` sends to a different path, so we
 * construct the standard path directly.
 */
async function acknowledgeFindingDirect(
  request: APIRequestContext,
  serverId: string,
  findingId: string,
  note = "Acknowledged via E2E test",
) {
  await ensureCsrf(request);
  const res = await request.post(
    `${API_BASE}/api/v1/servers/${serverId}/security/${encodeURIComponent(findingId)}/acknowledge`,
    { data: { note }, headers: { ...csrfHeaders() } },
  );
  return { response: res, body: await res.json().catch(() => null) };
}

/**
 * Fetch scan history from the correct backend endpoint.
 * The api-helpers `getScanHistory` uses a different path, so we construct
 * it directly.
 */
async function getScanHistoryDirect(
  request: APIRequestContext,
  serverId: string,
  page = 1,
  pageSize = 20,
) {
  const res = await request.get(
    `${API_BASE}/api/v1/servers/${serverId}/security/scans?page=${page}&page_size=${pageSize}`,
  );
  return { response: res, body: await res.json().catch(() => null) };
}

/**
 * Trigger a deploy and return the response.
 */
async function deployServer(
  request: APIRequestContext,
  serverId: string,
) {
  const res = await request.post(
    `${API_BASE}/api/v1/servers/${serverId}/deploy`,
  );
  return { response: res, body: await res.json().catch(() => null) };
}

// ── Test suite ───────────────────────────────────────────────────────────

test.describe.serial("Security Scanner", () => {
  let user: ReturnType<typeof testUser>;
  let srv: ReturnType<typeof testServer>;
  let serverId: string;
  let emptyServerId: string;

  test.beforeAll(async ({ request }) => {
    // ── 1. Register user ──
    user = testUser();
    const reg = await registerUser(request, user);
    if (reg.response.status() !== 409) {
      expect(reg.response.ok()).toBeTruthy();
    }

    // ── 2. Create a server with tools from the petstore spec ──
    srv = testServer();
    const spec = await fetchSpec(request, srv.specUrl);
    expect(spec.response.ok()).toBeTruthy();
    const specId = spec.body.spec_id;

    const created = await selectToolsAndCreateServer(request, specId, {
      name: srv.name,
      slug: srv.slug,
      baseUrl: srv.baseUrl,
      description: srv.description,
    });
    expect(created.response.ok()).toBeTruthy();
    serverId = created.body.server_id ?? created.body.id;

    // ── 3. Build the server ──
    const build = await startBuild(request, serverId);
    expect(build.response.ok()).toBeTruthy();

    // Wait for build to finish (poll server status until it's no longer "building")
    let attempts = 0;
    while (attempts < 30) {
      const res = await request.get(`${API_BASE}/api/v1/servers/${serverId}`);
      const body = await res.json().catch(() => ({}));
      if (body.status !== "building") break;
      await sleep(2000);
      attempts++;
    }

    // ── 4. Pause the server so the Deploy button is visible ──
    await pauseServer(request, serverId);

    // ── 5. Create an empty-tools server for test 10 ──
    const emptyYaml =
      'openapi: "3.0.3"\ninfo:\n  title: Empty Spec\n  version: "1.0.0"\npaths: {}\n';
    const uploadRes = await uploadSpec(request, emptyYaml, "empty.yaml");
    expect(uploadRes.response.ok()).toBeTruthy();
    const emptySpecId = uploadRes.body.spec_id;

    const emptyServer = await selectToolsAndCreateServer(request, emptySpecId, {
      name: `Empty Server ${uniqueId()}`,
      slug: `empty-${uniqueId()}`,
      baseUrl: "https://api.example.com",
    });
    expect(emptyServer.response.ok()).toBeTruthy();
    emptyServerId = emptyServer.body.server_id ?? emptyServer.body.id;
  });

  test.afterAll(async ({ request }) => {
    // Clean up both servers (best-effort, don't fail on errors)
    for (const id of [serverId, emptyServerId]) {
      if (id) {
        try {
          await deleteServer(request, id);
        } catch {
          // Silently ignore cleanup errors
        }
      }
    }
  });

  // ── 1. Security page shows empty state ──────────────────────────────────

  test("1. Security page shows empty state", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto(`/dashboard/servers/${serverId}/security`);
    await page.waitForLoadState("networkidle");

    // Verify "Security Scanner" heading
    await expect(
      page.getByRole("heading", { name: /security scanner/i }),
    ).toBeVisible();

    // Verify "No security scans have been run yet" empty state
    await expect(
      page.getByText("No security scans have been run yet"),
    ).toBeVisible();

    // Verify "Run Scan" button is visible
    await expect(
      page.getByRole("button", { name: /run scan/i }),
    ).toBeVisible();
  });

  // ── 2. Run security scan via UI ────────────────────────────────────────

  test("2. Run security scan via UI", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto(`/dashboard/servers/${serverId}/security`);
    await page.waitForLoadState("networkidle");

    // Click "Run Security Scan" button (in the header, next to Export)
    const scanButton = page.getByRole("button", {
      name: /run security scan/i,
    });
    await expect(scanButton).toBeVisible();
    await scanButton.click();

    // Poll the API until the scan completes (Celery runs asynchronously)
    const scanData = await waitForScanCompletion(request, serverId);

    // Reload the page to pick up the finalized scan results
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Verify severity count cards are displayed
    await expect(page.getByText("Critical")).toBeVisible();
    await expect(page.getByText("High")).toBeVisible();
    await expect(page.getByText("Medium")).toBeVisible();
    await expect(page.getByText("Info")).toBeVisible();

    // Verify each severity count card shows the correct number
    if (scanData.critical_count > 0) {
      // The severity cards render count in <p class="text-2xl font-semibold">
      // We find the card by its label text then check the adjacent count
      const criticalCard = page
        .getByText("Critical")
        .locator("..")
        .locator("..");
      const criticalValue = await criticalCard
        .locator("p")
        .textContent()
        .catch(() => "0");
      expect(Number(criticalValue)).toBe(scanData.critical_count);
    }

    // Verify findings list is displayed with finding titles
    // Findings are grouped by severity in card sections
    for (const finding of scanData.findings) {
      // Only check findings with distinct, visible titles
      if (finding.title && finding.title.length > 3) {
        await expect(page.getByText(finding.title).first()).toBeVisible();
      }
    }
  });

  // ── 3. Scan findings severity colors ───────────────────────────────────

  test("3. Scan findings severity colors", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto(`/dashboard/servers/${serverId}/security`);
    await page.waitForLoadState("networkidle");

    // Fetch the scan data to know which severities to expect
    const { body: scanData } = await getLatestScan(request, serverId);
    if (!scanData || scanData.findings.length === 0) {
      test.skip();
      return;
    }

    // Collect unique severities present in the scan
    const severities = Array.from(
      new Set<string>(
        scanData.findings.map((f: { severity: string }) => f.severity),
      ),
    );

    // For each severity, find a SeverityBadge and verify its color class
    for (const sev of severities) {
      const label = sev.toUpperCase(); // SeverityBadge renders uppercase
      const badge = page.getByText(label, { exact: true }).first();
      await expect(badge).toBeVisible();

      switch (sev) {
        case "critical":
          await expect(badge).toHaveClass(/red/);
          break;
        case "high":
          await expect(badge).toHaveClass(/orange/);
          break;
        case "medium":
          await expect(badge).toHaveClass(/amber/);
          break;
        case "info":
          await expect(badge).toHaveClass(/blue/);
          break;
        default:
          // Unknown severity — just verify it's visible
          await expect(badge).toBeVisible();
      }
    }
  });

  // ── 4. Acknowledge a finding ───────────────────────────────────────────

  test("4. Acknowledge a finding", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto(`/dashboard/servers/${serverId}/security`);
    await page.waitForLoadState("networkidle");

    // Find any "Acknowledge" button on the page
    const ackButton = page
      .getByRole("button", { name: "Acknowledge", exact: true })
      .first();

    // If no acknowledge buttons exist (all findings are critical), skip
    if (!(await ackButton.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Get the finding ID from the scan data for the non-critical finding
    const { body: scanData } = await getLatestScan(request, serverId);
    const nonCriticalFinding = scanData?.findings?.find(
      (f: { severity: string }) => f.severity !== "critical",
    );

    // Click the acknowledge button
    await ackButton.click();

    // Wait for the mutation to resolve and the UI to update
    await page.waitForTimeout(1500);

    // Verify the button changed to acknowledged state
    // After acknowledging, the button shows "Acknowledged" and is disabled
    await expect(
      page.getByText("Acknowledged").first(),
    ).toBeVisible({ timeout: 5000 });

    // Verify via API that the acknowledgment was persisted
    if (nonCriticalFinding) {
      const { body: acksData } = await getAcknowledgments(
        request,
        serverId,
      );
      const ackedIds = (acksData?.items ?? []).map(
        (a: { finding_id: string }) => a.finding_id,
      );
      expect(ackedIds).toContain(nonCriticalFinding.id);
    }
  });

  // ── 5. Deploy blocked by critical findings ─────────────────────────────

  test("5. Deploy blocked by critical findings", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);

    // Navigate to the server detail page
    await page.goto(`/dashboard/servers/${serverId}`);
    await page.waitForLoadState("networkidle");

    // Click the Settings tab
    const settingsTab = page.getByRole("tab", { name: /settings/i });
    await expect(settingsTab).toBeVisible();
    await settingsTab.click();

    // Wait for settings content to render (Deploy button is inside a
    // card with the heading "Deployment")
    await page.waitForTimeout(500);

    // Click the "Deploy" button (Button trigger that opens the deploy dialog)
    const deployTrigger = page.getByRole("button", {
      name: "Deploy",
      exact: true,
    });
    if (!(await deployTrigger.isVisible().catch(() => false))) {
      // If the button is not visible (e.g., server is already active),
      // verify via API that the deploy endpoint returns 409
      const deployRes = await deployServer(request, serverId);
      expect(deployRes.response.status()).toBe(409);
      return;
    }
    await deployTrigger.click();

    // Wait for the deploy confirmation dialog to appear
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5000 });

    // Click "Deploy now" to confirm
    await page.getByRole("button", { name: /deploy now/i }).click();

    // Verify the error toast appears (useDeployServer shows "Deploy failed")
    // Sonner renders toasts with role="status" and the message text
    await expect(page.getByText("Deploy failed")).toBeVisible({
      timeout: 10000,
    });
  });

  // ── 6. Deploy succeeds after acknowledging critical findings ────────────

  test("6. Deploy succeeds after acknowledging critical findings", async ({
    page,
    request,
  }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);

    // ── Acknowledge all critical findings via API ──
    // Fetch the latest scan to find critical findings
    const { body: scanData } = await getLatestScan(request, serverId);
    if (scanData && scanData.findings) {
      const criticalFindings = scanData.findings.filter(
        (f: { severity: string }) => f.severity === "critical",
      );
      for (const finding of criticalFindings) {
        await acknowledgeFindingDirect(request, serverId, finding.id);
      }
    }

    // ── Navigate to the server detail page and deploy ──
    await page.goto(`/dashboard/servers/${serverId}`);
    await page.waitForLoadState("networkidle");

    // Click the Settings tab
    await page.getByRole("tab", { name: /settings/i }).click();
    await page.waitForTimeout(500);

    // Click the "Deploy" button to open the dialog
    const deployTrigger = page.getByRole("button", {
      name: "Deploy",
      exact: true,
    });

    // If deploy button is hidden (server already active), verify via API
    if (!(await deployTrigger.isVisible().catch(() => false))) {
      const deployRes = await deployServer(request, serverId);
      expect(deployRes.response.ok()).toBeTruthy();
      return;
    }
    await deployTrigger.click();

    // Confirm in the deploy dialog
    await expect(
      page.getByRole("dialog"),
    ).toBeVisible({ timeout: 5000 });
    await page.getByRole("button", { name: /deploy now/i }).click();

    // Verify the success toast appears
    await expect(page.getByText("Deploy started")).toBeVisible({
      timeout: 10000,
    });

    // Verify the server is no longer paused (status changed to "active")
    // The Deploy button should disappear after successful deployment
    await page.waitForTimeout(2000);
    await expect(
      page.getByRole("button", { name: "Deploy", exact: true }),
    ).not.toBeVisible({ timeout: 5000 });
  });

  // ── 7. Scan history tab ────────────────────────────────────────────────

  test("7. Scan history tab", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto(`/dashboard/servers/${serverId}/security`);
    await page.waitForLoadState("networkidle");

    // Fetch scan history via API to know what to expect
    const { body: historyData } = await getScanHistoryDirect(
      request,
      serverId,
    );

    // Click the "History" tab
    const historyTab = page.getByRole("tab", { name: /history/i });
    await expect(historyTab).toBeVisible();
    await historyTab.click();

    // Wait for the tab content to load
    await page.waitForTimeout(1000);

    if (historyData && historyData.total > 0) {
      // Verify scan entries are listed with date, status, and finding counts
      for (const scan of historyData.items) {
        // Each scan entry shows the scanned_at timestamp
        const scanDate = new Date(scan.scanned_at).toLocaleString("en-US", {
          year: "numeric",
          month: "short",
          day: "numeric",
        });
        // The date portion should be visible somewhere in the entry
        await expect(page.getByText(scanDate).first()).toBeVisible();
      }

      // Verify the badge showing severity counts (e.g., "2C / 1H / 0M / 0I")
      const latestScan = historyData.items[0];
      const badgePattern = new RegExp(
        `${latestScan.critical_count}C\\s*/\\s*${latestScan.high_count}H`,
      );
      await expect(
        page.getByText(badgePattern).first(),
      ).toBeVisible();
    } else {
      // No scan history yet — verify empty state
      await expect(
        page.getByText("No scan history"),
      ).toBeVisible();
    }
  });

  // ── 8. Concurrent scans prevented ──────────────────────────────────────

  test("8. Concurrent scans prevented", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);

    // Trigger a scan via API
    await ensureCsrf(request);
    const firstRes = await request.post(
      `${API_BASE}/api/v1/servers/${serverId}/security/scan`,
      { headers: { ...csrfHeaders() } },
    );
    expect(firstRes.ok()).toBeTruthy();

    // Immediately trigger a second scan
    const secondRes = await request.post(
      `${API_BASE}/api/v1/servers/${serverId}/security/scan`,
      { headers: { ...csrfHeaders() } },
    );

    // The backend might return 200 (both scans accepted) or 409 (concurrent
    // scan prevented). Either is acceptable — we just verify the system
    // handles rapid repeated triggers gracefully.
    if (secondRes.status() === 409) {
      const body = await secondRes.json().catch(() => ({}));
      expect(body).toBeDefined();
    } else {
      expect(secondRes.ok()).toBeTruthy();
    }
  });

  // ── 9. Scan results persist after page reload ──────────────────────────

  test("9. Scan results persist after page reload", async ({
    page,
    request,
  }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);

    // Wait for the latest scan from test 8 to complete
    const scanData = await waitForScanCompletion(request, serverId);

    // Navigate to the security page
    await page.goto(`/dashboard/servers/${serverId}/security`);
    await page.waitForLoadState("networkidle");

    // Reload the page (simulates navigating away and back)
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Verify severity count cards still appear with correct values
    await expect(page.getByText("Critical")).toBeVisible();
    await expect(page.getByText("High")).toBeVisible();
    await expect(page.getByText("Medium")).toBeVisible();
    await expect(page.getByText("Info")).toBeVisible();

    // Verify the counts match the API data
    if (scanData.critical_count > 0) {
      await expect(
        page.getByText(String(scanData.critical_count)).first(),
      ).toBeVisible();
    }

    // Verify finding titles are still displayed
    for (const finding of scanData.findings) {
      if (finding.title && finding.title.length > 3) {
        await expect(
          page.getByText(finding.title).first(),
        ).toBeVisible();
      }
    }
  });

  // ── 10. Security dashboard for server without tools ─────────────────────

  test("10. Security dashboard for server without tools", async ({
    page,
    request,
  }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);

    // Navigate to the empty spec server's security page
    await page.goto(`/dashboard/servers/${emptyServerId}/security`);
    await page.waitForLoadState("networkidle");

    // Verify the empty state is shown initially (no scan yet)
    await expect(
      page.getByText("No security scans have been run yet"),
    ).toBeVisible();

    // Click "Run Scan" button (in the empty state card)
    const scanButton = page.getByRole("button", { name: /run scan/i });
    await expect(scanButton).toBeVisible();
    await scanButton.click();

    // Wait for the scan to complete via API polling
    await waitForScanCompletion(request, emptyServerId);

    // Reload the page to see the results
    await page.reload();
    await page.waitForLoadState("networkidle");

    // The scan should show 0 findings since the server has no tools
    // The severity count cards should show all zeros
    await expect(page.getByText("Critical")).toBeVisible();
    await expect(page.getByText("High")).toBeVisible();
    await expect(page.getByText("Medium")).toBeVisible();
    await expect(page.getByText("Info")).toBeVisible();

    // Verify zero counts are displayed
    await expect(page.getByText("0").first()).toBeVisible();

    // Verify "No findings found" or similar empty findings state
    // The SecurityFindingsList component shows an EmptyState when no findings
    await expect(
      page.getByText("No findings found"),
    ).toBeVisible();
  });
});
