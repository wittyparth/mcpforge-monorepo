import { type Page } from "@playwright/test";

export async function mockAuthMe(page: Page): Promise<void> {
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

export async function mockSpecFetchSuccess(page: Page): Promise<void> {
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
            description: "List all pets",
            input_schema: { type: "object", properties: { limit: { type: "integer" } } },
            base_url_override: null,
            operation_id: "listPets",
            method: "GET",
            path: "/pets",
            original_operation_id: "listPets",
            summary: "List pets",
            tags: ["pets"],
            parameters: [{ name: "limit", in: "query", required: false, description: "Max results", schema: { type: "integer" } }],
            request_body_schema: null,
            response_schemas: { "200": { type: "array" } },
            security_requirements: [],
            selected: true,
            warnings: [],
          },
          {
            name: "create_pet",
            description: "Create a new pet",
            input_schema: { type: "object", properties: { name: { type: "string" }, species: { type: "string" } } },
            base_url_override: null,
            operation_id: "createPet",
            method: "POST",
            path: "/pets",
            original_operation_id: "createPet",
            summary: "Create pet",
            tags: ["pets"],
            parameters: [],
            request_body_schema: { type: "object", properties: { name: { type: "string" }, species: { type: "string" } } },
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

export async function mockUploadSuccess(page: Page): Promise<void> {
  await page.route("**/api/v1/specs/upload", async (route) => {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        spec_id: "uploaded-spec-id",
        title: "Uploaded API",
        version: "2.0.0",
        openapi_version: "3.0.3",
        endpoint_count: 1,
        spec_size_bytes: 512,
        tools: [
          {
            name: "get_item",
            description: "Get a single item",
            input_schema: { type: "object", properties: { id: { type: "integer" } } },
            base_url_override: null,
            operation_id: "getItem",
            method: "GET",
            path: "/items/{id}",
            original_operation_id: "getItem",
            summary: "Get item",
            tags: ["items"],
            parameters: [{ name: "id", in: "path", required: true, description: "Item ID", schema: { type: "integer" } }],
            request_body_schema: null,
            response_schemas: { "200": { type: "object" } },
            security_requirements: [],
            selected: true,
            warnings: [],
          },
        ],
      }),
    });
  });
}

export async function mockSelectTools(page: Page): Promise<void> {
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

export async function mockBuildStart(page: Page): Promise<void> {
  await page.route("**/api/v1/servers/*/build", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "test-server-id", status: "building" }),
    });
  });
}

export async function mockBuildStatusSSE(page: Page): Promise<void> {
  await page.route("**/api/v1/servers/*/build-status", async (route) => {
    const body = [
      'data: {"stage":"parsing","progress":25,"message":"Parsing spec..."}',
      'data: {"stage":"generating","progress":50,"message":"Generating tools..."}',
      'data: {"stage":"testing","progress":75,"message":"Running checks..."}',
      'data: {"stage":"deploying","progress":90,"message":"Deploying..."}',
      'data: {"stage":"complete","progress":100,"message":"Build complete!"}',
      "",
    ].join("\n");
    await route.fulfill({ status: 200, contentType: "text/event-stream", body });
  });
}

export async function mockServerDetail(page: Page): Promise<void> {
  await page.route("**/api/v1/servers/*", async (route, request) => {
    if (request.method() !== "GET") { await route.fallback(); return; }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "test-server-id", user_id: "test-user-id", slug: "test-server",
        name: "Test Server", description: "A test MCP server", status: "active",
        base_url: "https://api.example.com", auth_scheme: "none",
        tools_config: { version: 1, tools: [] }, transport_mode: "sse",
        total_calls: 0, monthly_calls: 0, last_call_at: null, version: 1,
        created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      }),
    });
  });
  await page.route("**/api/v1/servers/*/tools", async (route) => {
    await route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ server_id: "test-server-id", tool_count: 2, tools: [] }),
    });
  });
  await page.route("**/api/v1/servers/*/credentials", async (route) => {
    await route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ server_id: "test-server-id", credentials: [], total: 0 }),
    });
  });
}

export async function mockSpecFetch422(page: Page): Promise<void> {
  await page.route("**/api/v1/specs/fetch", async (route) => {
    await route.fulfill({
      status: 422, contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid spec: missing openapi field", code: "INVALID_SPEC" }),
    });
  });
}
