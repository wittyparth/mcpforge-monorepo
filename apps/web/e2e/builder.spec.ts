import { test, expect, type Page } from "@playwright/test";

// ── Mock factories ──────────────────────────────────────────────────────

/**
 * Mock GET /api/v1/auth/me — dashboard layout calls this on every page load
 * under /dashboard/*. Returns a valid User object.
 */
async function mockAuthMe(page: Page): Promise<void> {
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "test-user-id",
        email: "test@example.com",
        display_name: "Test User",
        avatar_url: null,
        plan: "free",
        email_verified: true,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      }),
    });
  });
}

/**
 * Mock POST /api/v1/specs/fetch — called in Step 1 when the user submits
 * a spec URL. Returns a SpecUploadResponse with two tools.
 */
async function mockSpecFetchSuccess(page: Page): Promise<void> {
  await page.route("**/api/v1/specs/fetch", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        spec_id: "test-spec-id",
        title: "Pet Store API",
        version: "1.0.0",
        openapi_version: "3.0.3",
        endpoint_count: 2,
        spec_size_bytes: 2048,
        tools: [
          {
            name: "list_pets",
            description: "List all pets available in the store",
            input_schema: {
              type: "object",
              properties: {
                limit: { type: "integer", description: "Max results" },
              },
            },
            base_url_override: null,
            operation_id: "listPets",
            method: "GET",
            path: "/pets",
            original_operation_id: "listPets",
            summary: "List pets",
            tags: ["pets"],
            parameters: [
              {
                name: "limit",
                in: "query",
                required: false,
                description: "Max results",
                schema: { type: "integer" },
              },
            ],
            request_body_schema: null,
            response_schemas: { "200": { type: "array", items: {} } },
            security_requirements: [],
            selected: true,
            warnings: [],
          },
          {
            name: "create_pet",
            description: "Create a new pet in the store",
            input_schema: {
              type: "object",
              properties: {
                name: { type: "string", description: "Pet name" },
                species: { type: "string", description: "Pet species" },
              },
              required: ["name"],
            },
            base_url_override: null,
            operation_id: "createPet",
            method: "POST",
            path: "/pets",
            original_operation_id: "createPet",
            summary: "Create pet",
            tags: ["pets"],
            parameters: [],
            request_body_schema: {
              type: "object",
              properties: {
                name: { type: "string" },
                species: { type: "string" },
              },
            },
            response_schemas: { "201": { type: "object" } },
            security_requirements: [],
            selected: true,
            warnings: [],
          },
        ],
      }),
    });
  });
}

/**
 * Mock POST /api/v1/specs/{spec_id}/select-tools — called in Step 3 when
 * the user submits the server config form. Creates the McpServer and
 * returns it.
 */
async function mockSelectTools(page: Page): Promise<void> {
  await page.route("**/api/v1/specs/*/select-tools", async (route) => {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: "test-server-id",
        user_id: "test-user-id",
        slug: "test-server",
        name: "Test Server",
        description: "A test MCP server",
        status: "building",
        spec_url: "https://example.com/spec.json",
        base_url: "https://api.example.com",
        auth_scheme: "none",
        tools_config: { version: 1, tools: [] },
        transport_mode: "sse",
        total_calls: 0,
        monthly_calls: 0,
        last_call_at: null,
        version: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    });
  });
}

/**
 * Mock POST /api/v1/servers/{server_id}/build — called when entering Step 4
 * to trigger the build pipeline.
 */
async function mockBuildStart(page: Page): Promise<void> {
  await page.route("**/api/v1/servers/*/build", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "test-server-id",
        user_id: "test-user-id",
        slug: "test-server",
        name: "Test Server",
        description: "A test MCP server",
        status: "building",
        spec_url: "https://example.com/spec.json",
        base_url: "https://api.example.com",
        auth_scheme: "none",
        tools_config: { version: 1, tools: [] },
        transport_mode: "sse",
        total_calls: 0,
        monthly_calls: 0,
        last_call_at: null,
        version: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    });
  });
}

/**
 * Mock GET /api/v1/servers/{server_id}/build-status — SSE endpoint
 * consumed by useBuildStatus. Returns a multi-line text/event-stream body
 * with parsing → generating → testing → deploying → complete stages.
 */
async function mockBuildStatusSSE(page: Page): Promise<void> {
  await page.route("**/api/v1/servers/*/build-status", async (route) => {
    // NB: trailing newline is CRITICAL — without it, `useBuildStatus`
    // moves the last (complete) line into a partial buffer and drops
    // it when the reader signals `done`.
    const body = [
      'data: {"stage":"parsing","progress":25,"message":"Parsing OpenAPI specification..."}',
      'data: {"stage":"generating","progress":50,"message":"Generating MCP tool definitions..."}',
      'data: {"stage":"testing","progress":75,"message":"Running security tests..."}',
      'data: {"stage":"deploying","progress":90,"message":"Deploying MCP server..."}',
      'data: {"stage":"complete","progress":100,"message":"Build complete!"}',
      "", // ← trailing empty line drives a final \n so split yields no orphan
    ].join("\n");

    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body,
    });
  });
}

/**
 * Mock GET /api/v1/servers/{server_id} — called by the server detail page
 * after the build completes and the wizard auto-redirects.
 */
async function mockServerGet(page: Page): Promise<void> {
  await page.route("**/api/v1/servers/*", async (route, request) => {
    if (request.method() !== "GET") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "test-server-id",
        user_id: "test-user-id",
        slug: "test-server",
        name: "Test Server",
        description: "A test MCP server",
        status: "active",
        spec_url: "https://example.com/spec.json",
        base_url: "https://api.example.com",
        auth_scheme: "none",
        tools_config: { version: 1, tools: [] },
        transport_mode: "sse",
        total_calls: 0,
        monthly_calls: 0,
        last_call_at: null,
        version: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    });
  });
}

/**
 * Mock GET /api/v1/servers/{server_id}/tools — called by server detail page.
 */
async function mockServerTools(page: Page): Promise<void> {
  await page.route("**/api/v1/servers/*/tools", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        server_id: "test-server-id",
        tool_count: 2,
        tools: [
          { name: "list_pets", description: "List all pets", enabled: true },
          { name: "create_pet", description: "Create a pet", enabled: true },
        ],
      }),
    });
  });
}

/**
 * Mock GET /api/v1/servers/{server_id}/credentials — called by server detail page.
 */
async function mockServerCredentials(page: Page): Promise<void> {
  await page.route("**/api/v1/servers/*/credentials", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        server_id: "test-server-id",
        credentials: [],
        total: 0,
      }),
    });
  });
}

// ── Suite ───────────────────────────────────────────────────────────────

test.describe("Server Builder Wizard", () => {
  test.beforeEach(async ({ page }) => {
    // The dashboard layout calls useCurrentUser() on every /dashboard/* page.
    // Must respond before the layout redirects to /login.
    await mockAuthMe(page);
  });

  test("completes the full 4-step wizard happy path", async ({ page }) => {
    // ── Setup all API mocks ─────────────────────────────────────────
    await mockSpecFetchSuccess(page);
    await mockSelectTools(page);
    await mockBuildStart(page);
    await mockBuildStatusSSE(page);

    // Also mock the detail-page endpoints in case the auto-redirect fires
    // before our assertion runs (redirect delay is 1200ms).
    await mockServerGet(page);
    await mockServerTools(page);
    await mockServerCredentials(page);

    // ── Navigate ───────────────────────────────────────────────────
    await page.goto("/dashboard/servers/new");

    // ════════════════════════ Step 1: Spec Input ════════════════════

    // CardTitle renders as <div>, not <h1-6>, so use getByText.
    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible();

    // The "From URL" tab is selected by default. The URL input has
    // id="spec-url", label "OpenAPI Spec URL".
    await page.getByLabel("OpenAPI Spec URL").fill("https://example.com/spec.json");

    // Click "Fetch Spec" — triggers POST /api/v1/specs/fetch.
    // Playwright waits for the button to be enabled (it starts disabled
    // when input is empty, becomes enabled after fill).
    await page.getByRole("button", { name: "Fetch Spec" }).click();

    // ════════════════════════ Step 2: Tool Selection ═══════════════

    // Wait for the tool workspace section to appear.
    await expect(
      page.locator('section[aria-label="Step 2: Select Tools"]'),
    ).toBeVisible({ timeout: 15000 });

    // Verify tools are rendered
    await expect(page.getByText("list_pets")).toBeVisible();
    await expect(page.getByText("create_pet")).toBeVisible();

    // Advance to Step 3
    await page.getByRole("button", { name: "Continue" }).click();

    // ════════════════════════ Step 3: Server Config ════════════════

    await expect(
      page.locator('section[aria-label="Step 3: Configure Server"]'),
    ).toBeVisible();

    // The AuthSchemeSelector card should appear (defaults to "none")
    await expect(page.getByText("Authentication", { exact: true })).toBeVisible();

    // Fill the server config form. Label text includes a required "*"
    // suffix — getByLabel matches the text content before the span.
    await page.getByLabel("Server name").fill("Test Server");
    await page.getByLabel("Base URL").fill("https://api.example.com");

    // Slug is auto-derived from name, transport defaults to SSE.

    // Submit — triggers POST /api/v1/specs/{spec_id}/select-tools which
    // creates the McpServer and returns it.
    await page.getByRole("button", { name: "Save and Continue" }).click();

    // Wait for the server to be created (isServerCreated becomes true).
    // The credentials section appears with auth scheme "none", showing a
    // "No authentication selected" message and "Continue to Build" button.
    await expect(page.getByText("Continue to Build")).toBeVisible({
      timeout: 15000,
    });

    // Advance to Step 4
    await page.getByRole("button", { name: "Continue to Build" }).click();

    // ════════════════════════ Step 4: Build Progress ═══════════════

    await expect(
      page.locator('section[aria-label="Step 4: Build Progress"]'),
    ).toBeVisible();

    // Build events stream in via SSE mock. The build completes nearly
    // instantly since the mock returns all events in one body.
    await expect(page.getByText("Build complete", { exact: true })).toBeVisible({
      timeout: 15000,
    });

    // The "View Server" button should also be visible
    await expect(
      page.getByRole("button", { name: /view server/i }),
    ).toBeVisible();

    // The page auto-redirects to /dashboard/servers/test-server-id
    // after 1200ms. Since we mocked the detail-page endpoints, the
    // redirect target renders cleanly.
  });

  test("shows client-side validation error for HTTP URL", async ({ page }) => {
    // No need to mock spec fetch — client-side validation catches the
    // invalid URL before the API is called.

    await page.goto("/dashboard/servers/new");

    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible();

    // Type an HTTP URL (the zod schema requires HTTPS)
    await page
      .getByLabel("OpenAPI Spec URL")
      .fill("http://insecure.example.com/spec.json");

    // Click "Fetch Spec" — react-hook-form runs client-side validation
    // before calling the API, and the zod refine rejects non-HTTPS URLs.
    // Playwright waits for the button to be enabled.
    await page.getByRole("button", { name: "Fetch Spec" }).click();

    // The error message from the zod refine is rendered inline
    await expect(page.getByText("Only HTTPS URLs are allowed")).toBeVisible();
  });

  test("shows API error when spec fetch returns 422", async ({ page }) => {
    // Mock the spec fetch endpoint to return a validation error
    await page.route("**/api/v1/specs/fetch", async (route) => {
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Invalid OpenAPI spec: missing required field 'openapi'",
          code: "INVALID_SPEC",
        }),
      });
    });

    await page.goto("/dashboard/servers/new");

    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible();

    // Use a valid HTTPS URL so client-side validation passes
    await page
      .getByLabel("OpenAPI Spec URL")
      .fill("https://example.com/invalid-spec.json");

    await page.getByRole("button", { name: "Fetch Spec" }).click();

    // The API error is shown both inline (SpecValidationErrors) and via
    // toast.error(...). Use first() to handle the multi-match.
    await expect(
      page.getByText("Invalid OpenAPI spec: missing required field 'openapi'").first(),
    ).toBeVisible({ timeout: 10000 });
  });
});
