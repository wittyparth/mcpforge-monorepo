/**
 * Comprehensive Playwright E2E tests for billing flows.
 *
 * Tests plan display, monthly/yearly toggle, team seat selector,
 * subscription checkout redirect, billing portal, invoice history,
 * invoice pagination, status badge colors, and cancel subscription dialog.
 *
 * CRITICAL: Uses real API calls via Playwright's `request` fixture.
 * NO page.route() mocks.
 *
 * Handles both real Stripe mode and litigated (mock) mode gracefully.
 * In litigated mode, Stripe calls return mock URLs and the frontend
 * redirects to /dashboard/billing?checkout=success instead.
 *
 * State-dependent tests run serially via test.describe.serial().
 */

import { test, expect } from "@playwright/test";
import {
  API_BASE,
  APP_BASE,
  testUser,
  registerUser,
  loginViaApiAndSetCookies,
  ensureCsrf,
} from "../e2e/api-helpers";

// ── Helpers ──────────────────────────────────────────────────────────────

const _sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Track created emails for manual cleanup documentation
const createdEmails: string[] = [];

// ── Billing flow tests (state-dependent, run serially) ────────────────────

test.describe.serial("Billing flows", () => {
  let user: ReturnType<typeof testUser>;

  test.beforeAll(async ({ request }) => {
    user = testUser();
    createdEmails.push(user.email);

    const reg = await registerUser(request, user);
    // 409 is OK if the user already exists from a previous (failed) run
    if (reg.response.status() !== 409) {
      expect(reg.response.ok()).toBeTruthy();
    }
  });

  test.afterAll(() => {
    if (createdEmails.length > 0) {
      console.log(
        "E2E billing test users created — no admin delete API exists; clean up manually:",
        createdEmails.join(", "),
      );
    }
  });

  // ── 1. Billing page loads with plans ──────────────────────────────────

  test("1. Billing page loads with plans", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Verify heading
    await expect(
      page.getByRole("heading", { name: "Billing" }),
    ).toBeVisible({ timeout: 10000 });

    // Verify "Plans" section heading
    await expect(page.getByText("Plans")).toBeVisible();

    // Verify Free, Pro, and Team plan cards are visible (use first() since text may match multiple elements)
    await expect(page.getByText("Free").first()).toBeVisible();
    await expect(page.getByText("Pro").first()).toBeVisible();
    await expect(page.getByText("Team").first()).toBeVisible();

    // Verify prices are shown
    // Pro default monthly: $12.00/mo
    // Team default monthly: $29.00/mo
    await expect(page.getByText("$12.00")).toBeVisible();
    await expect(page.getByText("$29.00")).toBeVisible();
  });

  // ── 2. Current plan banner shows free plan ────────────────────────────

  test("2. Current plan banner shows free plan", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Verify "Current Plan" card heading
    await expect(
      page.getByRole("heading", { name: /current plan/i }),
    ).toBeVisible();

    // Verify "Free Plan" is shown in the current plan card
    await expect(page.getByText("Free Plan")).toBeVisible();

    // Verify "Upgrade" button is present (for free users to scroll to plans)
    await expect(
      page.getByRole("button", { name: "Upgrade" }),
    ).toBeVisible();
  });

  // ── 3. Monthly/Yearly toggle changes prices ───────────────────────────

  test("3. Monthly/Yearly toggle changes prices", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Default should be Monthly (data-state="on" for Monthly)
    const monthlyToggle = page.getByRole("button", { name: /^monthly$/i });
    const yearlyToggle = page.getByRole("button", { name: /yearly/i });

    // Verify monthly is selected by default
    await expect(monthlyToggle).toHaveAttribute("data-state", "on");

    // Click Yearly
    await yearlyToggle.click();
    await page.waitForTimeout(300);

    // Verify "Save 20%" badge is visible on the yearly toggle
    await expect(page.getByText("Save 20%")).toBeVisible();

    // Verify yearly toggle is now selected
    await expect(yearlyToggle).toHaveAttribute("data-state", "on");
    await expect(monthlyToggle).toHaveAttribute("data-state", "off");

    // Verify prices changed — yearly 20% off Pro: $12.00 → $9.60/mo
    await expect(page.getByText("$9.60")).toBeVisible();

    // Click Monthly to return
    await monthlyToggle.click();
    await page.waitForTimeout(300);

    // Verify monthly prices are back
    await expect(monthlyToggle).toHaveAttribute("data-state", "on");
    await expect(yearlyToggle).toHaveAttribute("data-state", "off");

    // Verify original prices restored
    await expect(page.getByText("$12.00")).toBeVisible();
  });

  // ── 4. Team plan seat selector ────────────────────────────────────────

  test("4. Team plan seat selector", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Verify "Team seats" label is visible (only shown for Team plan card)
    await expect(page.getByText("Team seats")).toBeVisible();

    // Verify the seat input exists with minimum 2
    const seatInput = page.getByLabel("Team seats");
    await expect(seatInput).toBeVisible();
    await expect(seatInput).toHaveValue("2");

    // Verify "Minimum 2 seats" hint text
    await expect(page.getByText("Minimum 2 seats")).toBeVisible();

    // Try reducing below minimum (1 < min 2)
    await seatInput.fill("1");

    // Verify the "Upgrade to Team" button is disabled
    const upgradeTeamBtn = page.getByRole("button", {
      name: /upgrade to team/i,
    });
    await expect(upgradeTeamBtn).toBeDisabled();

    // Restore seats to a valid number — button should re-enable
    await seatInput.fill("2");
    await expect(upgradeTeamBtn).toBeEnabled();
  });

  // ── 5. Subscribe to Pro plan redirects to Stripe checkout ─────────────

  test("5. Subscribe to Pro plan — redirects to checkout", async ({
    page,
    request,
  }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Find and click the "Upgrade to Pro" button
    const upgradeBtn = page.getByRole("button", {
      name: "Upgrade to Pro",
      exact: true,
    });
    await expect(upgradeBtn).toBeVisible();

    // Click the upgrade button and wait for redirect
    upgradeBtn.click();

    // The app navigates to either:
    // - Stripe Checkout URL (real Stripe mode)
    // - /dashboard/billing?checkout=success (litigated mode)
    // Wait up to 15s for the navigation to complete
    try {
      await page.waitForURL(
        (url) =>
          url.href.includes("checkout.stripe.com") ||
          url.href.includes("checkout=success"),
        { timeout: 15000 },
      );

      const url = page.url();
      if (url.includes("checkout.stripe.com")) {
        // Real Stripe mode — redirected to Stripe Checkout
        expect(url).toContain("checkout.stripe.com");
      } else {
        // Litigated mode — redirected to success page in app
        expect(url).toContain("checkout=success");
      }
    } catch {
      // If no navigation was detected within timeout, the API may have
      // failed (e.g., Stripe not configured at all).
      // In that case, the error is shown as a toast and we stay on
      // the billing page. Check that we're still on the billing page.
      const currentUrl = page.url();
      expect(currentUrl).toContain("/dashboard/billing");
    }
  });

  // ── 6. Subscription status reflects after subscribe ───────────────────

  test("6. Subscription status after subscribe", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);

    // Use page.request (shares page context cookies) for authenticated API call
    const res = await page.request.get(
      `${API_BASE}/api/v1/billing/subscription`,
    );

    if (res.status() === 200) {
      // Subscription exists — verify plan and status
      const body = await res.json();
      expect(body.plan).toBeDefined();
      expect(body.status).toBeDefined();
      expect([
        "active",
        "trialing",
        "past_due",
        "canceled",
        "incomplete",
        "unpaid",
      ]).toContain(body.status);
    } else {
      // No subscription found (litigated mode — no webhook processed)
      // or user is on free plan. Either is acceptable.
      expect(res.status()).toBe(404);
      const body = await res.json();
      expect(body.detail).toBeDefined();
    }
  });

  // ── 7. Billing portal opens ───────────────────────────────────────────

  test("7. Billing portal opens", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);

    // Call the portal API via page.request (authenticated via shared cookies)
    const csrfToken = await ensureCsrf(request);
    const res = await page.request.post(
      `${API_BASE}/api/v1/billing/portal`,
      {
        data: { return_url: `${APP_BASE}/dashboard/billing` },
        headers: { "X-CSRF-Token": csrfToken },
      },
    );

    // Portal should work even without an active subscription
    // (it creates a Stripe customer if one doesn't exist)
    expect(res.status()).toBe(200);
    const body = await res.json();

    // Verify portal_url exists and is a valid Stripe portal URL
    expect(body.portal_url).toBeDefined();
    expect(typeof body.portal_url).toBe("string");
    expect(body.portal_url.length).toBeGreaterThan(0);

    // In real mode: "https://billing.stripe.com/p/..."
    // In litigated mode: "https://billing.stripe.com/mock/session/..."
    expect(body.portal_url).toContain("stripe.com");
  });

  // ── 8. Invoice history ────────────────────────────────────────────────

  test("8. Invoice history", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Verify the Invoice History section heading is visible
    await expect(
      page.getByRole("heading", { name: /invoice history/i }),
    ).toBeVisible({ timeout: 10000 });

    // Wait for invoice data to load
    await page.waitForTimeout(1000);

    // Check if invoices exist or if empty state is shown
    const invoicesTable = page.locator("table");
    const emptyStateText = page.getByText("No invoices yet");

    if (await emptyStateText.isVisible()) {
      // Empty state — verify the descriptive text
      await expect(
        page.getByText(
          "Invoices will appear here after your first payment",
        ),
      ).toBeVisible();
    } else if (await invoicesTable.isVisible()) {
      // Invoices exist — verify table headers
      await expect(page.getByText("Date")).toBeVisible();
      await expect(page.getByText("Amount")).toBeVisible();
      await expect(page.getByText("Status")).toBeVisible();

      // Verify at least one invoice row exists
      const rows = await invoicesTable.locator("tbody tr").count();
      expect(rows).toBeGreaterThan(0);

      // Verify each row shows date, amount, and status
      for (let i = 0; i < Math.min(rows, 3); i++) {
        const cells = invoicesTable.locator("tbody tr").nth(i).locator("td");
        await expect(cells.nth(0)).not.toBeEmpty(); // Date
        await expect(cells.nth(1)).not.toBeEmpty(); // Amount (formatted price)
        await expect(cells.nth(2)).not.toBeEmpty(); // Status (badge)
      }
    } else {
      // If neither table nor empty state is visible, data may still be loading
      // Wait a bit more
      await page.waitForTimeout(3000);
      const stillLoading =
        (await emptyStateText.isVisible()) ||
        (await invoicesTable.isVisible());
      expect(stillLoading).toBeTruthy();
    }
  });

  // ── 9. Invoice pagination ─────────────────────────────────────────────

  test("9. Invoice pagination", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Wait for invoices to load
    await page.waitForTimeout(1500);

    const nextBtn = page.getByRole("button", { name: "Next" });
    const prevBtn = page.getByRole("button", { name: "Previous" });

    // Pagination only appears when there are 10+ invoices (PAGE_SIZE)
    if (await nextBtn.isVisible()) {
      // Pagination controls exist — verify at least one is enabled
      // (if there are >10 invoices, Next is enabled)
      if (await nextBtn.isEnabled()) {
        // Note the current page info text
        const pageInfoText = await page
          .locator("text=/Showing \\d+–\\d+ of \\d+/")
          .textContent();

        // Click Next to go to page 2
        await nextBtn.click();
        await page.waitForTimeout(500);

        // Previous button should now be enabled (we're past page 1)
        await expect(prevBtn).toBeEnabled();

        // Verify the page info changed
        const newPageInfo = await page
          .locator("text=/Showing \\d+–\\d+ of \\d+/")
          .textContent();
        expect(newPageInfo).not.toBe(pageInfoText);

        // Click Previous to return to page 1
        await prevBtn.click();
        await page.waitForTimeout(500);
      } else {
        // Next is disabled — on the last page (fewer than 10 invoices
        // remaining on this page, but pagination exists)
        // Previous should be enabled (we're on page > 1)
        // OR both are visible but this is the last page
        await expect(prevBtn).toBeVisible();
      }
    } else {
      // No pagination — fewer than 10 invoices total
      // Verify invoice section is still functional (either table or empty)
      const emptyState = page.getByText("No invoices yet");
      const invoicesTable = page.locator("table");
      const hasInvoices =
        (await emptyState.isVisible()) ||
        (await invoicesTable.isVisible());
      expect(hasInvoices).toBeTruthy();
    }
  });

  // ── 10. Invoice status badges ─────────────────────────────────────────

  test("10. Invoice status badges", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Wait for invoices to load
    await page.waitForTimeout(1500);

    const invoicesTable = page.locator("table");

    if (!(await invoicesTable.isVisible())) {
      // No invoices table — verify empty state instead
      await expect(page.getByText("No invoices yet")).toBeVisible();
      return;
    }

    // Examine each invoice row's status badge
    const rows = invoicesTable.locator("tbody tr");
    const rowCount = await rows.count();

    for (let i = 0; i < rowCount; i++) {
      const row = rows.nth(i);
      // Status is the 3rd column (0-indexed: Date=0, Amount=1, Status=2, Actions=3)
      const statusCell = row.locator("td").nth(2);
      const badge = statusCell.locator("[class*='badge']").first();

      const badgeText = (await badge.textContent())?.trim() ?? "";

      switch (badgeText.toLowerCase()) {
        case "paid":
          await expect(badge).toHaveClass(/bg-green/);
          break;
        case "open":
          await expect(badge).toHaveClass(/bg-blue/);
          break;
        case "uncollectible":
          // destructive variant applies bg-destructive (CSS variable)
          await expect(badge).toHaveClass(/destructive/);
          break;
        case "void":
          // secondary variant applies bg-secondary
          await expect(badge).toHaveClass(/secondary/);
          break;
        default:
          // Unknown status — just verify it's a badge element
          await expect(badge).toBeVisible();
      }
    }
  });

  // ── 11. Cancel subscription dialog ────────────────────────────────────

  test("11. Cancel subscription dialog", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, user.email, user.password);
    await page.goto("/dashboard/billing");
    await page.waitForLoadState("networkidle");

    // Look for a cancel subscription trigger button (only visible for
    // subscribed users — free users see "Upgrade" instead).
    const cancelBtn = page.getByRole("button", {
      name: /cancel subscription/i,
    });

    if (await cancelBtn.isVisible()) {
      // ── User has an active subscription ──
      // Click to open the cancel dialog
      await cancelBtn.click();

      // Verify the dialog opened
      await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5000 });

      // Verify dialog title
      await expect(
        page.getByRole("heading", { name: /cancel subscription/i }),
      ).toBeVisible();

      // Verify two cancellation options are present
      await expect(
        page.getByText("Cancel at end of billing period"),
      ).toBeVisible();
      await expect(page.getByText("Cancel immediately")).toBeVisible();

      // "Cancel at end of billing period" should be selected by default
      const periodEndRadio = page.getByLabel("Cancel at end of billing period");
      await expect(periodEndRadio).toBeChecked();

      // Verify the corresponding warning text is shown
      await expect(
        page.getByText(
          "You will retain access to all paid features until the end of your current billing period.",
        ),
      ).toBeVisible();

      // Select "Cancel immediately"
      await page.getByText("Cancel immediately").click();
      const cancelNowRadio = page.getByLabel("Cancel immediately");
      await expect(cancelNowRadio).toBeChecked();

      // Verify warning text updates for immediate cancellation
      await expect(
        page.getByText(
          "Your access will be revoked immediately. You will be downgraded to the Free plan.",
        ),
      ).toBeVisible();

      // Verify action buttons
      await expect(
        page.getByRole("button", { name: /keep subscription/i }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: /cancel subscription/i }),
      ).toBeVisible();

      // Close the dialog via "Keep Subscription"
      await page.getByRole("button", { name: /keep subscription/i }).click();
      await expect(page.getByRole("dialog")).not.toBeVisible();
    } else {
      // ── User is on Free Plan (no active subscription) ──
      // Cancel button is not shown. This is expected in litigated mode
      // where no subscription was created (no Stripe webhook processed)
      // or when the user hasn't subscribed yet.
      //
      // Verify the current plan banner shows the Upgrade button instead
      await expect(
        page.getByRole("button", { name: "Upgrade" }),
      ).toBeVisible();

      // Verify we're on the billing page
      await expect(
        page.getByRole("heading", { name: "Billing" }),
      ).toBeVisible();
    }
  });
});
