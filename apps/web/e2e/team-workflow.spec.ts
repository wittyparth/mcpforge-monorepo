/**
 * Comprehensive Playwright E2E tests for team management workflows.
 *
 * Covers: empty state, team creation, member invitations (including duplicate
 * detection), role management, member removal, audit log verification, and
 * team leave (self-removal).
 *
 * CRITICAL: Uses real API calls via Playwright's `request` fixture.
 * NO page.route() mocks.
 *
 * IMPORTANT: Team invites are gated by plan limits. On the "free" plan
 * (default for new users), max_members=1 which prevents inviting additional
 * members. Tests 3–9 gracefully skip when the plan does not allow invites.
 *
 * State-dependent tests run serially via test.describe.serial().
 */

import { test, expect } from "@playwright/test";
import {
  API_BASE,
  testUser,
  registerUser,
  loginViaApiAndSetCookies,
  getTeam,
  getTeamMembers,
  inviteTeamMember,
  removeTeamMember,
  updateMemberRole,
  getAuditLog,
  uniqueId,
} from "../e2e/api-helpers";

// ── Helpers ──────────────────────────────────────────────────────────────

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Track created emails for manual cleanup documentation
const createdEmails: string[] = [];

/** Safely extract a member array from a getTeamMembers response body. */
function extractMembers(body: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(body)) return body as Array<Record<string, unknown>>;
  const m = (body as Record<string, unknown>)?.members;
  return Array.isArray(m) ? (m as Array<Record<string, unknown>>) : [];
}

/** Safely extract audit log items from a getAuditLog response body. */
function extractAuditItems(body: unknown): Array<Record<string, unknown>> {
  if (!body || typeof body !== "object") return [];
  const items = (body as Record<string, unknown>).items;
  return Array.isArray(items) ? (items as Array<Record<string, unknown>>) : [];
}

// ── Team workflow tests (state-dependent, run serially) ────────────────────

test.describe.serial("Team workflow", () => {
  let userA: ReturnType<typeof testUser>;
  let userB: ReturnType<typeof testUser>;
  let teamName: string;
  let canInvite = false;
  let inviteToken: string | null = null;
  let userBId: string | null = null;

  test.beforeAll(async ({ request }) => {
    userA = testUser();
    userB = testUser();
    createdEmails.push(userA.email, userB.email);

    // Register User A (team creator)
    const regA = await registerUser(request, userA);
    if (regA.response.status() !== 409) {
      expect(regA.response.ok()).toBeTruthy();
    }
    // Capture userA's ID if available
    if (regA.body?.id) {
      // userA.userId is not on the type; store separately not needed
    }

    // Register User B (invitee)
    const regB = await registerUser(request, userB);
    if (regB.response.status() !== 409) {
      expect(regB.response.ok()).toBeTruthy();
    }
    userBId = regB.body?.id ?? null;
  });

  test.afterAll(() => {
    if (createdEmails.length > 0) {
      console.log(
        "E2E team test users created — no admin delete API exists; clean up manually:",
        createdEmails.join(", "),
      );
    }
  });

  // ── 1. Team page shows empty state (no team) ──────────────────────────

  test("1. Team page shows empty state (no team)", async ({
    page,
    request,
  }) => {
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);
    await page.goto("/dashboard/team");
    await page.waitForLoadState("networkidle");

    // Verify the "Create your team" card is shown
    await expect(
      page.getByRole("heading", { name: /create your team/i }),
    ).toBeVisible({ timeout: 10000 });

    // Verify the team name input is present
    await expect(page.getByLabel("Team name")).toBeVisible();

    // Verify the "Create team" button is present
    await expect(
      page.getByRole("button", { name: /create team/i }),
    ).toBeVisible();
  });

  // ── 2. Create a team ──────────────────────────────────────────────────

  test("2. Create a team", async ({ page, request }) => {
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);
    await page.goto("/dashboard/team");
    await page.waitForLoadState("networkidle");

    // Wait for the create-team form to be ready
    await expect(
      page.getByRole("heading", { name: /create your team/i }),
    ).toBeVisible({ timeout: 10000 });

    // Fill in a unique team name
    teamName = `E2E Team ${uniqueId()}`;
    await page.getByLabel("Team name").fill(teamName);
    await page.getByRole("button", { name: /create team/i }).click();

    // Wait for the team to be created and the page to re-render with the
    // team dashboard (TeamInfoCard + MembersTable).
    await page.waitForLoadState("networkidle");

    // Verify the team name is displayed in the TeamInfoCard
    await expect(page.getByText(teamName)).toBeVisible({ timeout: 10000 });

    // Verify "Team Details" heading is present
    await expect(
      page.getByRole("heading", { name: /team details/i }),
    ).toBeVisible();

    // Verify "Members" section heading is present
    await expect(
      page.getByRole("heading", { name: /members/i }),
    ).toBeVisible();

    // Verify the current user appears as admin
    // The members table shows "You" badge for the current user
    await expect(page.getByText("You")).toBeVisible();
    // The role badge should show "Admin" (ROLE_LABELS.admin)
    await expect(page.getByText("Admin")).toBeVisible();

    // Verify via API that the team was created and the user is the admin
    const teamResp = await getTeam(request);
    expect(teamResp.response.ok()).toBeTruthy();
    expect(teamResp.body.name).toBe(teamName);
    expect(teamResp.body.current_user_role).toBe("admin");

    // Determine if invites are possible (free plan: max_members=1)
    const teamPlan: string = teamResp.body.plan;
    canInvite = teamPlan !== "free";
    if (!canInvite) {
      console.log(
        `Team plan is "${teamPlan}" — max_members=1, ` +
          "invite-dependent tests (3–9) will be skipped. " +
          "To run full team E2E tests, upgrade the plan (e.g. via billing flow).",
      );
    }

    // Verify via API that members list has exactly 1 member (the creator)
    const membersResp = await getTeamMembers(request);
    expect(membersResp.response.ok()).toBeTruthy();
    const members = extractMembers(membersResp.body);
    expect(members).toHaveLength(1);
    expect(members[0]?.email).toBe(userA.email);
    expect(members[0]?.role).toBe("admin");
  });

  // ── 3. Invite a team member ───────────────────────────────────────────

  test("3. Invite a team member", async ({ page, request }) => {
    test.skip(!canInvite, "Free plan does not allow invites (max_members=1)");

    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);

    // Navigate to team dashboard
    await page.goto("/dashboard/team");
    await page.waitForLoadState("networkidle");

    // Click the "Invite Member" button in the TeamInfoCard
    await page.getByRole("button", { name: /invite member/i }).click();

    // Wait for navigation to the invite page
    await page.waitForURL(/\/dashboard\/team\/invite/, { timeout: 10000 });

    // Verify the invite page heading
    await expect(
      page.getByRole("heading", { name: /invite team member/i }),
    ).toBeVisible({ timeout: 10000 });

    // Fill in User B's email
    await page.getByLabel("Email address").fill(userB.email);

    // Select the "Editor" role (default is "viewer", we change to "Editor")
    const roleSelector = page.getByLabel("Select role");
    await roleSelector.click();

    // Select "Editor" from the role dropdown
    const editorOption = page.getByRole("option", { name: "Editor" });
    await expect(editorOption).toBeVisible();
    await editorOption.click();

    // Click Send invitation
    await page.getByRole("button", { name: /send invitation/i }).click();

    // Verify success toast "Invitation sent!"
    await expect(page.getByText("Invitation sent!")).toBeVisible({
      timeout: 10000,
    });

    // Verify the invitation card shows the sent invitation details
    await expect(
      page.getByRole("heading", { name: /invitation sent/i }),
    ).toBeVisible();

    // Verify the invited email appears on the invitation card
    await expect(page.getByText(userB.email)).toBeVisible();

    // Verify the role appears (the invited role)
    await expect(page.getByText("editor")).toBeVisible();

    // Capture the invitation token from the invite link displayed
    const inviteLinkInput = page.locator(
      'input[readonly][class*="font-mono"]',
    );
    await expect(inviteLinkInput).toBeVisible();
    const inviteLink = await inviteLinkInput.inputValue();
    const urlObj = new URL(inviteLink);
    inviteToken = urlObj.searchParams.get("token");
    expect(inviteToken).toBeTruthy();

    // Verify via API that invitation was created (team still has 1 member)
    const membersResp = await getTeamMembers(request);
    expect(membersResp.response.ok()).toBeTruthy();
    const members = extractMembers(membersResp.body);
    expect(members).toHaveLength(1);
  });

  // ── 4. Invite existing member — duplicate error ───────────────────────

  test("4. Invite existing member — duplicate error", async ({
    page,
    request,
  }) => {
    test.skip(!canInvite, "Free plan does not allow invites (max_members=1)");
    test.skip(!inviteToken, "No invitation was created in test 3");

    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);

    // Navigate to invite page
    await page.goto("/dashboard/team/invite");
    await page.waitForLoadState("networkidle");

    // Fill in the same email again
    await page.getByLabel("Email address").fill(userB.email);

    // Click Send invitation
    await page.getByRole("button", { name: /send invitation/i }).click();

    // The backend returns 409 Conflict for duplicate pending invitation.
    // The UI catches the error and shows a toast "Failed to send invitation".
    await expect(page.getByText("Failed to send invitation")).toBeVisible({
      timeout: 10000,
    });

    // Verify we're still on the invite page (no redirect)
    await expect(page).toHaveURL(/\/dashboard\/team\/invite/);

    // Also verify via API that a duplicate invite returns 409
    const dupResp = await inviteTeamMember(request, userB.email, "viewer");
    expect(dupResp.response.status()).toBe(409);
    const dupBody = dupResp.body as Record<string, unknown> | undefined;
    expect((dupBody?.error as Record<string, unknown> | undefined)?.code).toBe("CONFLICT");
  });

  // ── 5. Role management ────────────────────────────────────────────────

  test("5. Role management", async ({ page, request }) => {
    test.skip(!canInvite, "Free plan does not allow invites (max_members=1)");
    test.skip(!inviteToken, "No invitation was created in test 3");

    // Step 1: Login as User B and accept the invitation via API
    await loginViaApiAndSetCookies(
      request,
      page,
      userB.email,
      userB.password,
    );

    const acceptRes = await request.post(`${API_BASE}/api/v1/team/accept`, {
      data: { token: inviteToken },
    });
    expect(acceptRes.ok()).toBeTruthy();
    const acceptBody = await acceptRes.json();
    expect(acceptBody.role).toBe("editor");

    // Verify User B now has a team
    const teamB = await getTeam(request);
    expect(teamB.response.ok()).toBeTruthy();

    // Step 2: Login as User A to manage roles
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);
    await page.goto("/dashboard/team");
    await page.waitForLoadState("networkidle");

    // Verify User B appears in the members table
    await expect(page.getByText(userB.email)).toBeVisible({ timeout: 10000 });

    // User B's role badge should show "Editor" (the role we invited with)
    await expect(page.getByText("Editor")).toBeVisible();

    // Step 3: Open User B's actions dropdown
    const actionsBtn = page.getByRole("button", {
      name: new RegExp(`actions for ${userB.email}`, "i"),
    });
    await expect(actionsBtn).toBeVisible();
    await actionsBtn.click();

    // The RoleSelector inside the dropdown has aria-label "Select role"
    const bRoleSelector = page.getByLabel("Select role");
    await expect(bRoleSelector).toBeVisible({ timeout: 5000 });

    // Change role to "Admin"
    await bRoleSelector.click();
    const adminOption = page.getByRole("option", { name: "Admin" });
    await expect(adminOption).toBeVisible({ timeout: 5000 });
    await adminOption.click();

    // Wait for the mutation to complete
    await page.waitForTimeout(1000);

    // Verify success toast
    await expect(
      page.getByText(new RegExp(`updated.*${userB.email}.*Admin`, "i")),
    ).toBeVisible({ timeout: 10000 });

    // Close dropdown by clicking elsewhere
    await page.locator("h1").first().click();
    await page.waitForTimeout(500);

    // Verify there are now at least 2 "Admin" badges (User A + User B)
    await expect(page.getByText("Admin").first()).toBeVisible();
    const adminBadges = page.getByText("Admin");
    const adminCount = await adminBadges.count();
    expect(adminCount).toBeGreaterThanOrEqual(2);

    // Verify via API that User B's role is now admin
    const membersAfter = await getTeamMembers(request);
    expect(membersAfter.response.ok()).toBeTruthy();
    const membersList = extractMembers(membersAfter.body);
    const userBMember = membersList.find(
      (m: Record<string, unknown>) => m.email === userB.email,
    );
    expect(userBMember).toBeDefined();
    expect(userBMember!.role).toBe("admin");

    // Step 4: Change User B's role back to "editor" via UI
    await page.goto("/dashboard/team");
    await page.waitForLoadState("networkidle");

    // Open actions for User B again
    const actionsBtn2 = page.getByRole("button", {
      name: new RegExp(`actions for ${userB.email}`, "i"),
    });
    await actionsBtn2.click();

    const bRoleSelector2 = page.getByLabel("Select role");
    await expect(bRoleSelector2).toBeVisible({ timeout: 5000 });
    await bRoleSelector2.click();

    const editorOption = page.getByRole("option", { name: "Editor" });
    await expect(editorOption).toBeVisible({ timeout: 5000 });
    await editorOption.click();

    await page.waitForTimeout(1000);

    // Verify success toast
    await expect(
      page.getByText(new RegExp(`updated.*${userB.email}.*Editor`, "i")),
    ).toBeVisible({ timeout: 10000 });

    // Verify via API that User B is back to editor
    const membersFinal = await getTeamMembers(request);
    const membersFinalList = extractMembers(membersFinal.body);
    const userBMemberFinal = membersFinalList.find(
      (m: Record<string, unknown>) => m.email === userB.email,
    );
    expect(userBMemberFinal).toBeDefined();
    expect(userBMemberFinal!.role).toBe("editor");
  });

  // ── 6. Remove a team member ──────────────────────────────────────────

  test("6. Remove a team member", async ({ page, request }) => {
    test.skip(!canInvite, "Free plan does not allow invites (max_members=1)");
    test.skip(!inviteToken, "No invitation was created in test 3");

    // Step 1: Ensure User B has accepted the invitation
    await loginViaApiAndSetCookies(
      request,
      page,
      userB.email,
      userB.password,
    );

    const teamBCheck = await getTeam(request);
    if (!teamBCheck.response.ok()) {
      await request.post(`${API_BASE}/api/v1/team/accept`, {
        data: { token: inviteToken },
      });
    }

    // Step 2: Login as User A and remove User B
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);
    await page.goto("/dashboard/team");
    await page.waitForLoadState("networkidle");

    // Verify User B is in the members table
    await expect(page.getByText(userB.email)).toBeVisible({ timeout: 10000 });

    // Open User B's actions dropdown
    const actionsBtn = page.getByRole("button", {
      name: new RegExp(`actions for ${userB.email}`, "i"),
    });
    await expect(actionsBtn).toBeVisible();
    await actionsBtn.click();

    // Click "Remove member" in the dropdown
    const removeBtn = page.getByRole("menuitem", { name: /remove member/i });
    await expect(removeBtn).toBeVisible({ timeout: 5000 });
    await removeBtn.click();

    // Verify the confirmation dialog appears
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5000 });

    // Verify dialog title and description
    await expect(
      page.getByRole("heading", { name: /remove team member/i }),
    ).toBeVisible();

    // Verify the dialog mentions the user's email
    await expect(page.getByText(userB.email)).toBeVisible();

    // Confirm removal by clicking the "Remove member" button in the dialog
    const confirmBtn = page.getByRole("button", {
      name: /^remove member$/,
    });
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // Wait for removal to complete
    await page.waitForTimeout(1500);

    // Verify success toast
    await expect(
      page.getByText(new RegExp(`removed.*${userB.email}`, "i")),
    ).toBeVisible({ timeout: 10000 });

    // Verify the dialog is closed
    await expect(page.getByRole("dialog")).not.toBeVisible();

    // Verify User B is no longer in the members table
    await page.waitForTimeout(1000);
    await expect(page.getByText(userB.email)).not.toBeVisible({
      timeout: 10000,
    });

    // Verify via API that User B is no longer a member
    const membersResp = await getTeamMembers(request);
    expect(membersResp.response.ok()).toBeTruthy();
    const members = extractMembers(membersResp.body);
    const userBInMembers = members.some(
      (m: Record<string, unknown>) => m.email === userB.email,
    );
    expect(userBInMembers).toBe(false);

    // Verify User B's GET /team returns 404
    const loginB = await request.post(`${API_BASE}/api/v1/auth/login`, {
      data: { email: userB.email, password: userB.password },
    });
    expect(loginB.ok()).toBeTruthy();

    const setCookie = loginB.headers()["set-cookie"];
    const teamForB = await request.get(`${API_BASE}/api/v1/team`, {
      headers: {
        Cookie: (Array.isArray(setCookie) ? setCookie.join("; ") : (setCookie ?? "")) as string,
      },
    });
    expect(teamForB.status()).toBe(404);

    // Re-invite User B for subsequent tests
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);
    const reInvite = await inviteTeamMember(request, userB.email, "editor");
    if (reInvite.response.status() === 201) {
      const reBody = reInvite.body as Record<string, unknown> | null;
      inviteToken = (reBody?.token as string) ?? null;
    }
  });

  // ── 7. Audit log entries exist ───────────────────────────────────────

  test("7. Audit log entries exist", async ({ page, request }) => {
    test.skip(!canInvite, "Free plan does not allow invites (max_members=1)");
    test.skip(!inviteToken, "No invitation was created in test 3");

    // Ensure User B is a member again
    await loginViaApiAndSetCookies(
      request,
      page,
      userB.email,
      userB.password,
    );
    const teamCheck = await getTeam(request);
    if (!teamCheck.response.ok()) {
      await request.post(`${API_BASE}/api/v1/team/accept`, {
        data: { token: inviteToken },
      });
    }

    // Login as User A and navigate to audit log
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);
    await page.goto("/dashboard/team/audit-log");
    await page.waitForLoadState("networkidle");

    // Verify the audit log page heading
    await expect(
      page.getByRole("heading", { name: /team audit log/i }),
    ).toBeVisible({ timeout: 10000 });

    // Wait for entries to load
    await page.waitForTimeout(2000);

    // Check that at least one audit entry row is visible
    // Each entry in the audit log is a div inside a .divide-y container
    const entryRows = page.locator(
      '.divide-y > div:has([class*="badge"])',
    );
    const entryCount = await entryRows.count();
    expect(entryCount).toBeGreaterThan(0);

    // Verify each entry shows: action badge, user email, and timestamp
    for (let i = 0; i < Math.min(entryCount, 5); i++) {
      const entry = entryRows.nth(i);

      // Action badge
      const badge = entry.locator('[class*="badge"]').first();
      await expect(badge).toBeVisible();
      const badgeText = (await badge.textContent()) ?? "";
      expect(badgeText.length).toBeGreaterThan(0);

      // User email
      const emailSpan = entry.locator("span.text-sm.font-medium");
      await expect(emailSpan).toBeVisible();
      const emailText = (await emailSpan.textContent()) ?? "";
      expect(emailText.length).toBeGreaterThan(0);

      // Timestamp
      const timestampSpan = entry.locator(
        "span.text-xs.text-muted-foreground",
      ).last();
      await expect(timestampSpan).toBeVisible();
      const timestampText = (await timestampSpan.textContent()) ?? "";
      expect(timestampText.length).toBeGreaterThan(0);
    }

    // Verify via API that audit log has entries
    const auditResp = await getAuditLog(request);
    expect(auditResp.response.ok()).toBeTruthy();
    expect(auditResp.body.total).toBeGreaterThan(0);
    expect(auditResp.body.items.length).toBeGreaterThan(0);

    // Verify each API entry has required fields
    const auditItems = extractAuditItems(auditResp.body);
    for (const entry of auditItems) {
      expect(entry.action).toBeDefined();
      expect(typeof entry.action).toBe("string");
      expect((entry.action as string).length).toBeGreaterThan(0);
      expect(entry.created_at).toBeDefined();
    }
  });

  // ── 8. Audit log shows all actions ────────────────────────────────────

  test("8. Audit log shows all actions", async ({ page, request }) => {
    test.skip(!canInvite, "Free plan does not allow invites (max_members=1)");
    test.skip(!inviteToken, "No invitation was created in test 3");

    // Ensure User B is a member
    await loginViaApiAndSetCookies(
      request,
      page,
      userB.email,
      userB.password,
    );
    const teamCheck = await getTeam(request);
    if (!teamCheck.response.ok()) {
      await request.post(`${API_BASE}/api/v1/team/accept`, {
        data: { token: inviteToken },
      });
    }

    // Login as User A and perform actions to generate audit trail
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);

    // Get User B's ID
    const membersResp = await getTeamMembers(request);
    const members = extractMembers(membersResp.body);
    const userBMember = members.find(
      (m: Record<string, unknown>) => m.email === userB.email,
    );
    const userBUuid = (userBMember?.user_id as string | undefined) ?? userBId;

    // Perform role changes, remove, re-invite
    if (userBUuid) {
      await updateMemberRole(request, userBUuid, "admin");
      await sleep(500);
      await updateMemberRole(request, userBUuid, "editor");
      await sleep(500);
      await removeTeamMember(request, userBUuid);
      await sleep(500);
    }
    const reInviteResp = await inviteTeamMember(request, userB.email, "viewer");
    if (reInviteResp.response.status() === 201) {
      const reBody = reInviteResp.body as Record<string, unknown> | null;
      inviteToken = (reBody?.token as string) ?? null;
    }
    await sleep(500);

    // Check the audit log via API for expected action types
    const auditResp = await getAuditLog(request);
    expect(auditResp.response.ok()).toBeTruthy();
    expect(auditResp.body.total).toBeGreaterThan(0);

    const auditItems = extractAuditItems(auditResp.body);
    const auditActions: string[] = auditItems.map(
      (item) => item.action as string,
    );

    // Verify the action types we performed are present in the log.
    // The service layer writes these action names:
    //   team.invite
    //   team.member.role_update
    //   team.member.remove
    const expectedActions = [
      "team.invite",
      "team.member.role_update",
      "team.member.remove",
    ];
    for (const expected of expectedActions) {
      expect(auditActions).toContain(expected);
    }

    // Verify each entry has required fields
    for (const entry of auditItems) {
      expect(entry.action).toBeDefined();
      expect(typeof entry.action).toBe("string");
      expect(entry.created_at).toBeDefined();
    }

    // Navigate to the UI and verify
    await page.goto("/dashboard/team/audit-log");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Verify entry count is shown
    const auditTotal = (auditResp.body as Record<string, unknown>)?.total as number ?? 0;
    await expect(
      page.getByText(new RegExp(`${auditTotal}\\s+entries?`)),
    ).toBeVisible({ timeout: 5000 });

    // Verify action filter dropdown works
    const filterSelect = page.getByLabel("Filter by action");
    await expect(filterSelect).toBeVisible();

    // Test filtering by a specific action
    await filterSelect.click();
    const filterOption = page.getByRole("option", { name: /member invited/i });
    if (await filterOption.isVisible()) {
      await filterOption.click();
      await page.waitForTimeout(1000);

      // Verify filtered results have at least one badge visible
      const filteredBadges = page.locator('[class*="badge"]');
      await expect(filteredBadges.first()).toBeVisible({ timeout: 5000 });
    }
  });

  // ── 9. Leave team (self-removal) ──────────────────────────────────────

  test("9. Leave team", async ({ page, request }) => {
    test.skip(!canInvite, "Free plan does not allow invites (max_members=1)");
    test.skip(!inviteToken, "No invitation was created in test 3");

    // Step 1: Ensure User B is a member and has accepted
    await loginViaApiAndSetCookies(
      request,
      page,
      userB.email,
      userB.password,
    );
    const teamBCheck = await getTeam(request);
    if (!teamBCheck.response.ok()) {
      await request.post(`${API_BASE}/api/v1/team/accept`, {
        data: { token: inviteToken },
      });
    }

    // Step 2: Login as User A and promote User B to admin
    // (so User A is not the last admin and can leave)
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);

    const membersResp = await getTeamMembers(request);
    const members = extractMembers(membersResp.body);
    const userBMember = members.find(
      (m: Record<string, unknown>) => m.email === userB.email,
    );

    if (userBMember && userBMember.role !== "admin") {
      const userBIdStr = userBMember.user_id as string;
      await updateMemberRole(request, userBIdStr, "admin");
      await sleep(500);
    }

    // Step 3: User A leaves the team (self-removal via API)
    // DELETE /api/v1/team/members/{user_id} supports self-removal
    const teamInfo = await getTeam(request);
    expect(teamInfo.response.ok()).toBeTruthy();
    const userAId = teamInfo.body.owner_id;

    const leaveRes = await removeTeamMember(request, userAId);
    expect(leaveRes.ok()).toBeTruthy();
    expect(leaveRes.status()).toBe(204);

    // Step 4: Verify User A no longer has a team
    const teamAfterLeave = await getTeam(request);
    expect(teamAfterLeave.response.status()).toBe(404);

    // Step 5: Verify the UI shows "No team" state
    // Login again to ensure fresh cookies
    await loginViaApiAndSetCookies(request, page, userA.email, userA.password);
    await page.goto("/dashboard/team");
    await page.waitForLoadState("networkidle");

    // Should show the "Create your team" card (empty state)
    await expect(
      page.getByRole("heading", { name: /create your team/i }),
    ).toBeVisible({ timeout: 10000 });

    await expect(page.getByLabel("Team name")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /create team/i }),
    ).toBeVisible();
  });
});
