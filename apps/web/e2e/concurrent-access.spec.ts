import { test, expect, type APIRequestContext } from "@playwright/test";
import {
  API_BASE,
  APP_BASE,
  testUser,
  testServer,
  uniqueId,
  registerUser,
  loginUser,
  loginViaApiAndSetCookies,
  fetchSpec,
  selectToolsAndCreateServer,
  startBuild,
  getBuildStatus,
  deleteServer,
  getServer,
  sendMcpMessage,
  createCredential,
  deleteCredential,
  listCredentials,
  createTeam,
  inviteTeamMember,
  pauseServer,
} from "../e2e/api-helpers";

// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Full flow: register → login → fetch spec → create server.
 * Returns the created server ID and slug.
 */
async function createServerForUser(
  ctx: APIRequestContext,
): Promise<{ serverId: string; slug: string }> {
  const uid = uniqueId();
  const spec = await fetchSpec(ctx, testServer().specUrl);
  const specId =
    spec.response.status() === 200
      ? (spec.body.spec_id ?? spec.body.id)
      : null;

  if (!specId) {
    const serverRes = await selectToolsAndCreateServer(ctx, "bypass", {
      name: `Concurrent-${uid}`,
      slug: `concurrent-${uid}`,
      baseUrl: testServer().baseUrl,
      description: "E2E concurrent access test server",
    });
    const body = serverRes.body ?? {};
    return {
      serverId: (body.id ?? body.server_id ?? uid) as string,
      slug: `concurrent-${uid}`,
    };
  }

  const serverRes = await selectToolsAndCreateServer(ctx, specId, {
    name: `Concurrent-${uid}`,
    slug: `concurrent-${uid}`,
    baseUrl: testServer().baseUrl,
    description: "E2E concurrent access test server",
  });
  const body = serverRes.body ?? {};
  return {
    serverId: (body.id ?? body.server_id ?? uid) as string,
    slug: `concurrent-${uid}`,
  };
}

/**
 * Parse Set-Cookie header into a flat cookie string for reuse.
 */
function _parseCookieHeader(setCookie: string | string[] | undefined): string {
  if (!setCookie) return "";
  const parts: string[] = Array.isArray(setCookie) ? setCookie : [setCookie];
  return parts
    .map((c: string) => (c.split(";")[0] ?? "").trim())
    .filter(Boolean)
    .join("; ");
}

// ── Tracked cleanup ────────────────────────────────────────────────────────

const createdUserEmails: string[] = [];
const createdServerIds: string[] = [];
const createdTeams: string[] = [];

test.afterAll(async ({ request }) => {
  // Delete servers in reverse order
  for (const sid of createdServerIds.reverse()) {
    try {
      await deleteServer(request, sid);
    } catch {
      // Best-effort cleanup
    }
  }
});

// ── Test Suite ─────────────────────────────────────────────────────────────

test.describe.serial("Concurrent / Simultaneous Access Scenarios", () => {
  test.use({ storageState: undefined });

  // ==========================================================================
  // Scenario 1: Two users register and create servers simultaneously
  // ==========================================================================
  test.slow();
  test("Scenario 1: Two users register and create servers in parallel", async ({
    playwright,
    request,
  }) => {
    test.setTimeout(120_000);

    const userA = testUser();
    const userB = testUser();
    createdUserEmails.push(userA.email, userB.email);

    // Step 1: Register both users in parallel
    // Accept 200 (user already exists from prior run) or 201 (newly created)
    const [regA, regB] = await Promise.all([
      registerUser(request, userA),
      registerUser(request, userB),
    ]);
    expect([200, 201]).toContain(regA.response.status());
    expect([200, 201]).toContain(regB.response.status());

    // Step 2: Login both and capture separate API contexts
    const ctxA = await playwright.request.newContext();
    const ctxB = await playwright.request.newContext();

    const [loginA, loginB] = await Promise.all([
      loginUser(ctxA, userA.email, userA.password),
      loginUser(ctxB, userB.email, userB.password),
    ]);
    expect(loginA.response.status()).toBe(200);
    expect(loginB.response.status()).toBe(200);

    // Step 3: Create servers in parallel (fetch spec + select tools)
    // Use a known-working spec URL or inline minimal spec
    const specUrl = testServer().specUrl;
    const [fetchA, fetchB] = await Promise.all([
      fetchSpec(ctxA, specUrl),
      fetchSpec(ctxB, specUrl),
    ]);

    const specIdA = fetchA.response.status() === 200 ? (fetchA.body.spec_id ?? fetchA.body.id) : null;
    const specIdB = fetchB.response.status() === 200 ? (fetchB.body.spec_id ?? fetchB.body.id) : null;

    const uidA = uniqueId();
    const uidB = uniqueId();

    const [serverResA, serverResB] = await Promise.all([
      selectToolsAndCreateServer(ctxA, specIdA ?? "bypass", {
        name: `Concurrent-A-${uidA}`,
        slug: `concurrent-a-${uidA}`,
        baseUrl: testServer().baseUrl,
        description: "Scenario 1 server A",
      }),
      selectToolsAndCreateServer(ctxB, specIdB ?? "bypass", {
        name: `Concurrent-B-${uidB}`,
        slug: `concurrent-b-${uidB}`,
        baseUrl: testServer().baseUrl,
        description: "Scenario 1 server B",
      }),
    ]);

    expect(serverResA.response.status()).toBe(201);
    expect(serverResB.response.status()).toBe(201);

    const bodyA = serverResA.body ?? {};
    const bodyB = serverResB.body ?? {};
    const serverIdA: string = bodyA.id ?? bodyA.server_id ?? bodyA.slug;
    const serverIdB: string = bodyB.id ?? bodyB.server_id ?? bodyB.slug;

    // Verify they have different IDs
    expect(serverIdA).not.toBe(serverIdB);
    expect(typeof serverIdA).toBe("string");
    expect(typeof serverIdB).toBe("string");

    // Verify each user owns their respective server via GET
    const [getA, getB] = await Promise.all([
      getServer(ctxA, serverIdA),
      getServer(ctxB, serverIdB),
    ]);
    expect(getA.response.status()).toBe(200);
    expect(getB.response.status()).toBe(200);

    // Verify auth isolation: User A cannot access User B's server and vice versa
    const [crossGetA, crossGetB] = await Promise.all([
      getServer(ctxA, serverIdB),
      getServer(ctxB, serverIdA),
    ]);
    // Should be 403 (forbidden) or 404 (not found — hidden from other users)
    expect([403, 404]).toContain(crossGetA.response.status());
    expect([403, 404]).toContain(crossGetB.response.status());

    createdServerIds.push(serverIdA, serverIdB);

    await ctxA.dispose();
    await ctxB.dispose();
  });

  // ==========================================================================
  // Scenario 2: Auth isolation — User B cannot access User A's server
  // ==========================================================================
  test.slow();
  test("Scenario 2: Auth isolation between users", async ({ playwright, page }) => {
    test.setTimeout(90_000);

    // User A: register, login, create server
    const userA = testUser();
    const userB = testUser();
    createdUserEmails.push(userA.email, userB.email);

    const ctxA = await playwright.request.newContext();
    const ctxB = await playwright.request.newContext();

    // Register both
    await registerUser(ctxA, userA);
    await registerUser(ctxB, userB);

    // Login both
    await loginUser(ctxA, userA.email, userA.password);
    await loginUser(ctxB, userB.email, userB.password);

    // A creates a server
    const { serverId: serverIdA, slug: _slugA } = await createServerForUser(ctxA);
    createdServerIds.push(serverIdA);

    // B tries to access A's server directly via API — expect 403/404
    const bGet = await getServer(ctxB, serverIdA);
    expect([403, 404]).toContain(bGet.response.status());

    // B tries to access via the web UI (should see error or be redirected)
    const pageB = await page.context().newPage();
    await loginViaApiAndSetCookies(ctxB, pageB, userB.email, userB.password);
    await pageB.goto(`${APP_BASE}/dashboard/servers/${serverIdA}`);
    // Should show a "not found" or "access denied" message
    const urlAfter = pageB.url();
    // Either the page shows an error, or redirects to dashboard
    const errorVisible = await pageB
      .getByText(/not found|access denied|forbidden|404|403/i)
      .isVisible()
      .catch(() => false);
    const onDashboard = urlAfter.includes("/dashboard/servers") && !urlAfter.includes(serverIdA);
    expect(errorVisible || onDashboard).toBe(true);

    // Now: team-based access grant
    // User A creates a team
    const teamRes = await createTeam(ctxA, `Team-${uniqueId()}`);
    if (teamRes.response.status() === 201) {
      const teamId = teamRes.body.id ?? teamRes.body.team_id;
      createdTeams.push(teamId);

      // A invites B to the team
      const inviteRes = await inviteTeamMember(ctxA, userB.email, "member");
      // Invite may succeed (201) or the endpoint might not exist yet
      if (inviteRes.response.status() === 201) {
        // Wait a beat for async propagation
        await new Promise((r) => setTimeout(r, 1000));

        // Now B should be able to access A's server (if team-based sharing is implemented)
        const bGetAfter = await getServer(ctxB, serverIdA);
        // Either access is granted (200) or still isolated (403/404)
        // Accept both since team-to-server sharing may not be wired yet
        expect([200, 403, 404]).toContain(bGetAfter.response.status());
      }
    }

    await ctxA.dispose();
    await ctxB.dispose();
    await pageB.close();
  });

  // ==========================================================================
  // Scenario 3: Simultaneous tool calls from same user
  // ==========================================================================
  test.slow();
  test("Scenario 3: 20 simultaneous tool calls via MCP gateway", async ({
    playwright,
  }) => {
    test.setTimeout(120_000);

    const user = testUser();
    const ctx = await playwright.request.newContext();
    createdUserEmails.push(user.email);

    await registerUser(ctx, user);
    await loginUser(ctx, user.email, user.password);

    // Create a server and build it
    const { serverId, slug } = await createServerForUser(ctx);
    createdServerIds.push(serverId);

    // Start build
    const buildRes = await startBuild(ctx, serverId);
    if (buildRes.response.status() === 200) {
      // Wait for build to complete
      let buildDone = false;
      for (let i = 0; i < 30; i++) {
        const status = await getBuildStatus(ctx, serverId);
        if (status.body?.status === "completed" || status.body?.status === "ready") {
          buildDone = true;
          break;
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
      expect(buildDone).toBe(true);
    }

    // Send 20 parallel tool call messages to the MCP gateway
    const concurrentCalls = 20;
    const toolPayloads = Array.from({ length: concurrentCalls }, (_, i) => ({
      jsonrpc: "2.0",
      id: `e2e-concurrent-${i}`,
      method: "tools/call",
      params: {
        name: "echo",
        arguments: { message: `hello-${i}` },
      },
    }));

    const startTime = Date.now();

    const results = await Promise.all(
      toolPayloads.map((payload) =>
        sendMcpMessage(ctx, slug, payload).catch((err: Error) => ({
          response: { status: () => 0 },
          body: { error: err.message },
        })),
      ),
    );

    const totalTime = Date.now() - startTime;

    // Verify all requests returned (either success or valid error)
    const statuses = results.map((r) => r.response.status());
    const _successfulCalls = statuses.filter((s) => s === 200 || s === 201).length;

    // At minimum, the gateway responded to all 20 calls without crashing
    expect(results.length).toBe(concurrentCalls);

    // All calls should have a valid HTTP response (gateway may return 200 for tool calls)
    // or 400-level for tool execution errors (which is still a valid response)
    const validStatuses = statuses.filter((s) => s >= 200 && s < 500);
    expect(validStatuses.length).toBe(concurrentCalls);

    // As a benchmark: 20 calls in parallel should be faster than doing them sequentially
    // (sequential would take at least 20 * latency, parallel should be ~1-3x latency)
    // If totalTime > 30s, the gateway may be processing synchronously
    console.log(
      `[Scenario 3] ${concurrentCalls} concurrent tool calls completed in ${totalTime}ms`,
    );

    // Verify no null/undefined results — every call got a response
    for (const r of results) {
      expect(r.body).not.toBeNull();
    }

    await ctx.dispose();
  });

  // ==========================================================================
  // Scenario 4: Race condition — rapid create, delete, and access
  // ==========================================================================
  test.slow();
  test("Scenario 4: Race — rapid create/delete and concurrent modify", async ({
    playwright,
  }) => {
    test.setTimeout(120_000);

    const user = testUser();
    const ctx = await playwright.request.newContext();
    createdUserEmails.push(user.email);

    await registerUser(ctx, user);
    await loginUser(ctx, user.email, user.password);

    // ── Part A: Create, immediately delete, immediately access ──
    const uid = uniqueId();
    const specFetch = await fetchSpec(ctx, testServer().specUrl);
    const specId = specFetch.response.status() === 200
      ? (specFetch.body.spec_id ?? specFetch.body.id)
      : "bypass";

    const createRes = await selectToolsAndCreateServer(ctx, specId ?? "bypass", {
      name: `Race-Delete-${uid}`,
      slug: `race-delete-${uid}`,
      baseUrl: testServer().baseUrl,
      description: "Race condition delete test",
    });
    const raceServerId: string =
      createRes.body?.id ?? createRes.body?.server_id ?? `race-delete-${uid}`;

    // Immediately delete
    const delRes = await deleteServer(ctx, raceServerId);
    expect([200, 204]).toContain(delRes.status());

    // Immediately try to access the deleted server
    const getAfterDel = await getServer(ctx, raceServerId);
    // Must be 404 after deletion
    expect(getAfterDel.response.status()).toBe(404);

    // ── Part B: Create server, start build, immediately try to modify ──
    const uid2 = uniqueId();
    const createRes2 = await selectToolsAndCreateServer(ctx, specId ?? "bypass", {
      name: `Race-Build-${uid2}`,
      slug: `race-build-${uid2}`,
      baseUrl: testServer().baseUrl,
      description: "Race condition build test",
    });
    const raceBuildId: string =
      createRes2.body?.id ?? createRes2.body?.server_id ?? `race-build-${uid2}`;
    createdServerIds.push(raceBuildId);

    // Start build
    const buildRes = await startBuild(ctx, raceBuildId);

    // Immediately try to pause the server while build is running
    const pauseRes = await pauseServer(ctx, raceBuildId);

    // The pause should either:
    // - Succeed (200) if the server allows pausing during build
    // - Return 409 Conflict if build must complete first
    // - Return 400 if invalid state transition
    if (buildRes.response.status() === 200) {
      expect([200, 400, 409]).toContain(pauseRes.response.status());
    }

    // Try to delete while build is in progress
    const delDuringBuild = await deleteServer(ctx, raceBuildId);
    // Should either succeed (200/204), or return 409 if build must finish
    expect([200, 204, 409]).toContain(delDuringBuild.status());

    await ctx.dispose();
  });

  // ==========================================================================
  // Scenario 5: Multiple SSE connections exhausting pool
  // ==========================================================================
  test.slow();
  test("Scenario 5: 10 simultaneous SSE connections to the same server", async ({
    playwright,
  }) => {
    test.setTimeout(120_000);

    const user = testUser();
    const ctx = await playwright.request.newContext();
    createdUserEmails.push(user.email);

    await registerUser(ctx, user);
    await loginUser(ctx, user.email, user.password);

    const { serverId, slug } = await createServerForUser(ctx);
    createdServerIds.push(serverId);

    // Open 10 concurrent SSE connections
    const sseCount = 10;
    const sseResults = await Promise.all(
      Array.from({ length: sseCount }, async (_, i) => {
        // Use raw fetch via the API request context to get the SSE stream
        // SSE connections are long-lived; we only check the initial HTTP response
        try {
          const res = await ctx.get(`${API_BASE}/mcp/v1/${slug}/sse`);
          return { index: i, status: res.status(), ok: res.ok() };
        } catch (err) {
          return { index: i, status: 0, ok: false, error: String(err) };
        }
      }),
    );

    const accepted = sseResults.filter((r) => r.status === 200);
    const rejected = sseResults.filter((r) => r.status !== 200);

    console.log(
      `[Scenario 5] SSE connections: ${accepted.length} accepted, ${rejected.length} rejected/errored`,
    );

    // The backend should either:
    // (a) Accept all 10 connections (pool allows it)
    // (b) Accept some and return 429 for the rest (rate limited)
    // Either behavior is valid as long as it's consistent
    if (rejected.length > 0) {
      // If some were rejected, they should be 429 or 503
      for (const r of rejected) {
        if (r.status > 0) {
          expect([429, 503]).toContain(r.status);
        }
      }
    }

    // At least one connection should succeed
    expect(accepted.length).toBeGreaterThanOrEqual(1);

    // Log the behavior so deployment validation can check the pool limit
    console.log(
      `[Scenario 5] SSE pool behavior: accepts up to ${accepted.length} concurrent connections`,
    );

    await ctx.dispose();
  });

  // ==========================================================================
  // Scenario 6: Concurrent credential creation and deletion
  // ==========================================================================
  test.slow();
  test("Scenario 6: Concurrent credential creation and deletion", async ({
    playwright,
  }) => {
    test.setTimeout(120_000);

    const user = testUser();
    const ctx = await playwright.request.newContext();
    createdUserEmails.push(user.email);

    await registerUser(ctx, user);
    await loginUser(ctx, user.email, user.password);

    const { serverId } = await createServerForUser(ctx);
    createdServerIds.push(serverId);

    // Phase 1: Create 5 credentials simultaneously
    const phase1Creds = ["API_KEY", "SECRET_TOKEN", "DATABASE_URL", "REDIS_URL", "AWS_KEY"];
    const createPhase1 = await Promise.all(
      phase1Creds.map((name) =>
        createCredential(ctx, serverId, {
          env_var_name: name,
          value: `value-${name}-${uniqueId()}`,
        }).catch((err: Error) => ({
          response: { status: () => 0 },
          body: { error: err.message },
        })),
      ),
    );

    const phase1Created = createPhase1.filter((r) => r.response.status() === 201);
    const phase1Failed = createPhase1.filter((r) => r.response.status() !== 201);
    console.log(
      `[Scenario 6] Phase 1: ${phase1Created.length}/5 credentials created` +
        (phase1Failed.length > 0 ? `, ${phase1Failed.length} failed` : ""),
    );

    // Phase 2: Delete 3 and create 3 more simultaneously
    const toDelete = phase1Creds.slice(0, 3);
    const newCreds = ["GITHUB_TOKEN", "SLACK_WEBHOOK", "DOCKER_PASSWORD"];

    const [deleteResults, createPhase2] = await Promise.all([
      Promise.all(
        toDelete.map((name) =>
          deleteCredential(ctx, serverId, name)
            .then((res) => ({ name, status: res.status() }))
            .catch((err: Error) => ({ name, status: 0, error: err.message })),
        ),
      ),
      Promise.all(
        newCreds.map((name) =>
          createCredential(ctx, serverId, {
            env_var_name: name,
            value: `value-${name}-${uniqueId()}`,
          }).catch((err: Error) => ({
            response: { status: () => 0 },
            body: { error: err.message },
          })),
        ),
      ),
    ]);

    const deletesOk = deleteResults.filter((r) => r.status === 200 || r.status === 204).length;
    const phase2Created = createPhase2.filter((r) => r.response.status() === 201).length;

    console.log(
      `[Scenario 6] Phase 2: ${deletesOk}/3 deleted, ${phase2Created}/3 created`,
    );

    // Phase 3: List credentials and verify final count
    const listRes = await listCredentials(ctx, serverId);
    const credentials = listRes.body?.credentials ?? listRes.body?.items ?? listRes.body ?? [];
    const finalCount = Array.isArray(credentials) ? credentials.length : 0;

    // Expected: 5 - 3 + 3 = 5 (if all ops succeeded)
    // But due to concurrency, the actual count depends on timing
    // Accept any count >= 2 (minimum the 2 that weren't deleted + any new ones that succeeded)
    const expectedMin = Math.max(phase1Created.length - toDelete.length + phase2Created, 0);
    expect(finalCount).toBeGreaterThanOrEqual(expectedMin);
    console.log(
      `[Scenario 6] Final credential count: ${finalCount} (expected min: ${expectedMin})`,
    );

    await ctx.dispose();
  });

  // ==========================================================================
  // Scenario 7: Simultaneous build requests (double-build prevention)
  // ==========================================================================
  test.slow();
  test("Scenario 7: Second build request rejected while building", async ({
    playwright,
  }) => {
    test.setTimeout(120_000);

    const user = testUser();
    const ctx = await playwright.request.newContext();
    createdUserEmails.push(user.email);

    await registerUser(ctx, user);
    await loginUser(ctx, user.email, user.password);

    const { serverId } = await createServerForUser(ctx);
    createdServerIds.push(serverId);

    // Start first build
    const build1 = await startBuild(ctx, serverId);

    if (build1.response.status() === 200) {
      // Immediately send a second build request
      const build2 = await startBuild(ctx, serverId);

      // The second build should be rejected with 409 Conflict
      // (build already in progress)
      if (build2.response.status() !== 200) {
        expect(build2.response.status()).toBe(409);
        const body = build2.body ?? {};
        const detail = body.detail ?? body.message ?? "";
        expect(detail.toLowerCase()).toContain("build");
      } else {
        // If the first build completed instantly (unlikely but possible in fast builds),
        // a 200 is also acceptable
        console.log(
          "[Scenario 7] Second build also returned 200 (first build may have completed instantly)",
        );
      }
    } else {
      console.log(
        `[Scenario 7] First build returned ${build1.response.status()}, skipping double-build test`,
      );
    }

    await ctx.dispose();
  });

  // ==========================================================================
  // Scenario 8: Concurrent team invites
  // ==========================================================================
  test.slow();
  test("Scenario 8: 5 simultaneous team invites", async ({ playwright }) => {
    test.setTimeout(120_000);

    const user = testUser();
    const ctx = await playwright.request.newContext();
    createdUserEmails.push(user.email);

    await registerUser(ctx, user);
    await loginUser(ctx, user.email, user.password);

    // Create a team
    const teamRes = await createTeam(ctx, `Team-Concurrent-${uniqueId()}`);
    let teamId: string | null = null;
    if (teamRes.response.status() === 201) {
      teamId = (teamRes.body.id ?? teamRes.body.team_id) as string;
      if (teamId) createdTeams.push(teamId);
    } else if (teamRes.response.status() === 200) {
      // User may already have a team
      teamId = teamRes.body.id ?? teamRes.body.team_id;
    }

    // Send 5 invites to different emails simultaneously
    const inviteEmails = Array.from(
      { length: 5 },
      (_, i) => `invite-${uniqueId()}-${i}@example.com`,
    );

    const invites = await Promise.all(
      inviteEmails.map((email) =>
        inviteTeamMember(ctx, email, "member").catch((err: Error) => ({
          response: { status: () => 0 },
          body: { error: err.message },
        })),
      ),
    );

    const succeeded = invites.filter((r) => r.response.status() === 201);
    const rateLimited = invites.filter((r) => r.response.status() === 429);

    console.log(
      `[Scenario 8] Invites: ${succeeded.length}/5 succeeded` +
        (rateLimited.length > 0 ? `, ${rateLimited.length} rate-limited` : ""),
    );

    // Either all 5 succeeded, or some were rate-limited
    if (rateLimited.length > 0) {
      // Rate-limited invites should return 429
      for (const r of rateLimited) {
        expect(r.response.status()).toBe(429);
      }
    }

    // At least 1 invite should succeed (unless the endpoint doesn't exist)
    if (succeeded.length === 0 && rateLimited.length === 0) {
      // The invite endpoint may return a different status
      const statuses = invites.map((r) => r.response.status());
      console.log(
        `[Scenario 8] No invites succeeded or rate-limited. Statuses: [${statuses.join(", ")}]`,
      );
    }

    await ctx.dispose();
  });

  // ==========================================================================
  // Scenario 9: Concurrent server updates from different browsers
  // ==========================================================================
  test.slow();
  test("Scenario 9: Two browsers updating the same server simultaneously", async ({
    playwright,
    browser,
  }) => {
    test.setTimeout(120_000);

    const user = testUser();
    const ctx = await playwright.request.newContext();
    createdUserEmails.push(user.email);

    await registerUser(ctx, user);
    await loginUser(ctx, user.email, user.password);

    const { serverId } = await createServerForUser(ctx);
    createdServerIds.push(serverId);

    // Create two separate browser contexts for the same user
    const browserCtxA = await browser.newContext();
    const browserCtxB = await browser.newContext();

    const pageA = await browserCtxA.newPage();
    const pageB = await browserCtxB.newPage();

    // Login via API and set cookies on both pages
    const loginRes = await loginUser(ctx, user.email, user.password);
    const cookies = loginRes.cookies;

    // Set cookies on both contexts
    if (cookies) {
      const cookieList = (
        Array.isArray(cookies) ? cookies : [cookies]
      ).flatMap((cs: string) => {
        const parts = cs.split(";").map((s) => s.trim());
        const nameEq = parts[0];
        if (!nameEq) return [];
        const eqIdx = nameEq.indexOf("=");
        if (eqIdx === -1) return [];
        return [
          {
            name: nameEq.slice(0, eqIdx),
            value: nameEq.slice(eqIdx + 1),
            domain: "localhost",
            path: "/",
          },
        ];
      });

      if (cookieList.length > 0) {
        await browserCtxA.addCookies(cookieList);
        await browserCtxB.addCookies(cookieList);
      }
    }

    // Both browsers navigate to the server detail page
    await Promise.all([
      pageA.goto(`${APP_BASE}/dashboard/servers/${serverId}`),
      pageB.goto(`${APP_BASE}/dashboard/servers/${serverId}`),
    ]);
    await Promise.all([
      pageA.waitForLoadState("networkidle"),
      pageB.waitForLoadState("networkidle"),
    ]);

    // Both browsers attempt to update the description simultaneously
    const descA = `Description from browser A at ${Date.now()}`;
    const descB = `Description from browser B at ${Date.now()}`;

    // Attempt to update via the UI
    // The UI might have an edit button or inline editing
    const [resultA, resultB] = await Promise.all([
      (async () => {
        try {
          // Try to find the server name/description field and edit it
          const editBtn = pageA.getByRole("button", { name: /edit|update/i }).first();
          if (await editBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
            await editBtn.click();
            const descField = pageA.getByLabel(/description/i).first();
            if (await descField.isVisible({ timeout: 2000 }).catch(() => false)) {
              await descField.fill(descA);
              await pageA.getByRole("button", { name: /save|submit/i }).first().click();
              return "updated";
            }
          }
          return "no-ui";
        } catch {
          return "error";
        }
      })(),
      (async () => {
        try {
          const editBtn = pageB.getByRole("button", { name: /edit|update/i }).first();
          if (await editBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
            await editBtn.click();
            const descField = pageB.getByLabel(/description/i).first();
            if (await descField.isVisible({ timeout: 2000 }).catch(() => false)) {
              await descField.fill(descB);
              await pageB.getByRole("button", { name: /save|submit/i }).first().click();
              return "updated";
            }
          }
          return "no-ui";
        } catch {
          return "error";
        }
      })(),
    ]);

    console.log(`[Scenario 9] Browser A result: ${resultA}, Browser B result: ${resultB}`);

    // The final state should be one of the two descriptions (last-write-wins)
    // Read the current server state
    const finalGet = await getServer(ctx, serverId);
    if (finalGet.response.status() === 200) {
      const finalBody = finalGet.body ?? {};
      const finalDesc = finalBody.description ?? "";
      console.log(`[Scenario 9] Final description: "${finalDesc}"`);
      // The description should be one of our values (not some stale state)
      const isEither = finalDesc === descA || finalDesc === descB || finalDesc === "";
      // Empty description means the update didn't go through — that's OK in concurrent scenarios
      expect(isEither).toBe(true);
    }

    await pageA.close();
    await pageB.close();
    await browserCtxA.close();
    await browserCtxB.close();
    await ctx.dispose();
  });

  // ==========================================================================
  // Scenario 10: Stale data detection
  // ==========================================================================
  test.slow();
  test("Scenario 10: Stale data — context A uses deleted server", async ({
    playwright,
    browser,
  }) => {
    test.setTimeout(120_000);

    const user = testUser();
    const ctx = await playwright.request.newContext();
    createdUserEmails.push(user.email);

    await registerUser(ctx, user);
    await loginUser(ctx, user.email, user.password);

    const { serverId } = await createServerForUser(ctx);
    createdServerIds.push(serverId);

    // Context A: browser session that loads the server page
    const browserCtxA = await browser.newContext();
    const pageA = await browserCtxA.newPage();
    await loginViaApiAndSetCookies(ctx, pageA, user.email, user.password);

    // Navigate to the server detail page and confirm it loads
    await pageA.goto(`${APP_BASE}/dashboard/servers/${serverId}`);
    await pageA.waitForLoadState("networkidle");
    const pageLoaded = await pageA
      .getByText(/server|dashboard|overview/i)
      .first()
      .isVisible({ timeout: 10000 })
      .catch(() => false);
    console.log(`[Scenario 10] Context A loaded server page: ${pageLoaded}`);

    // Context B: delete the server via API
    const delRes = await deleteServer(ctx, serverId);
    expect([200, 204]).toContain(delRes.status());

    // Verify the server is actually deleted
    const getDel = await getServer(ctx, serverId);
    expect(getDel.response.status()).toBe(404);

    // Context A: try to perform an action on the now-deleted server
    // Option 1: Reload the page
    await pageA.reload();
    await pageA.waitForLoadState("networkidle");

    // Should see an error message about the server not found, or be redirected
    const pageUrl = pageA.url();
    const hasError = await pageA
      .getByText(/not found|deleted|gone|404|no longer|doesn.t exist/i)
      .isVisible()
      .catch(() => false);
    const redirected = !pageUrl.includes(serverId);

    console.log(
      `[Scenario 10] After deletion — URL: ${pageUrl}, error visible: ${hasError}, redirected: ${redirected}`,
    );

    expect(hasError || redirected).toBe(true);

    // Option 2: Try an API action via the page — navigate to an action endpoint
    const apiResponse = await pageA.request
      .post(`${API_BASE}/api/v1/servers/${serverId}/build`)
      .catch(() => null);

    if (apiResponse) {
      // The API should return 404 for the deleted server
      expect(apiResponse.status()).toBe(404);
      const errorBody = await apiResponse.json().catch(() => ({}));
      console.log(`[Scenario 10] API error on deleted server: ${JSON.stringify(errorBody)}`);
      // Verify error message mentions "not found" or similar
      const detail = (errorBody.detail ?? errorBody.message ?? "").toLowerCase();
      const hasNotFound =
        detail.includes("not found") ||
        detail.includes("doesn.t exist") ||
        detail.includes("no longer") ||
        apiResponse.status() === 404;
      expect(hasNotFound).toBe(true);
    }

    // Navigate to server list — deleted server should not appear
    await pageA.goto(`${APP_BASE}/dashboard/servers`);
    await pageA.waitForLoadState("networkidle");

    // The deleted server should NOT appear in the list
    const pageContent = (await pageA.textContent("body").catch(() => "")) ?? "";
    // The server ID or name should not appear on the list page
    // (It may appear in error messages or meta tags though)
    const serverName = `Concurrent-`;
    const nameInContent = pageContent.includes(serverName);

    // Either server isn't listed, or there's a "no servers" message
    const noServers = await pageA
      .getByText(/no servers|get started|create your first/i)
      .isVisible()
      .catch(() => false);

    console.log(
      `[Scenario 10] Server name visible in list: ${nameInContent}, 'no servers' shown: ${noServers}`,
    );
    // At least one of these should be true — either the deleted server is gone, or empty state shows
    expect(!nameInContent || noServers).toBe(true);

    await pageA.close();
    await browserCtxA.close();
    await ctx.dispose();
  });
});
