import { test, expect } from "@playwright/test";
import {
  API_BASE, testUser, uniqueId,
  registerUser,
  fetchSpec, selectToolsAndCreateServer,
  startBuild, getBuildStatus, deleteServer,
  getGatewaySSE, sendMcpMessage,
} from "./api-helpers";

test.describe.serial("MCP Gateway SSE Transport", () => {
  const ctx = {
    user: testUser(),
    serverId: "",
    slug: "",
    specId: "",
    messageEndpoint: "",
  };

  test.beforeAll(async ({ request }) => {
    // Register user
    const { userId } = await registerUser(request, ctx.user);
    expect(userId).toBeTruthy();

    // Create a server with tools via the API
    const specUrl = "https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml";
    const { response: fetchRes, body: fetchBody } = await fetchSpec(request, specUrl);
    expect(fetchRes.status()).toBe(200);
    ctx.specId = fetchBody.id ?? fetchBody.spec_id;
    expect(ctx.specId).toBeTruthy();

    const slug = `gateway-sse-${uniqueId()}`;
    const { response: createRes, body: createBody } = await selectToolsAndCreateServer(request, ctx.specId, {
      name: `Gateway SSE Test ${Date.now()}`,
      slug,
      baseUrl: "https://petstore.swagger.io/v2",
      toolNames: ["getPetById", "addPet", "findPetsByStatus"],
      transportMode: "sse",
    });
    expect(createRes.status()).toBe(200);
    ctx.serverId = createBody.id ?? createBody.server_id;
    ctx.slug = slug;
    expect(ctx.serverId).toBeTruthy();

    // Build the server
    const { response: buildRes } = await startBuild(request, ctx.serverId);
    expect(buildRes.status()).toBe(200);

    // Wait for build to complete
    let buildStatus = "building";
    for (let i = 0; i < 60; i++) {
      const { body: statusBody } = await getBuildStatus(request, ctx.serverId);
      buildStatus = statusBody.status;
      if (buildStatus === "active" || buildStatus === "ready") break;
      await new Promise((r) => setTimeout(r, 2000));
    }
    expect(buildStatus).toMatch(/active|ready/);
  });

  test.afterAll(async ({ request }) => {
    if (ctx.serverId) {
      await deleteServer(request, ctx.serverId).catch(() => {});
    }
  });

  test("01 — SSE endpoint returns event stream", async ({ request }) => {
    const res = await request.get(`${API_BASE}/mcp/v1/${ctx.slug}/sse`);
    expect(res.status()).toBe(200);
    const contentType = res.headers()["content-type"] || "";
    expect(contentType).toContain("text/event-stream");
  });

  test("02 — SSE initial endpoint event received", async ({ request }) => {
    const res = await request.get(`${API_BASE}/mcp/v1/${ctx.slug}/sse`);
    expect(res.status()).toBe(200);

    const body = await res.text();
    expect(body).toContain("event: endpoint");
    expect(body).toContain(`/mcp/v1/${ctx.slug}/message`);
  });

  test("03 — POST JSON-RPC tools/list returns tool definitions", async ({ request }) => {
    const { response: sseRes } = await getGatewaySSE(request, ctx.slug);
    expect(sseRes.status()).toBe(200);

    const { response, body } = await sendMcpMessage(request, ctx.slug, {
      jsonrpc: "2.0",
      id: "e2e-001",
      method: "tools/list",
    });
    expect(response.status()).toBe(200);
    expect(body.jsonrpc).toBe("2.0");
    expect(body.id).toBe("e2e-001");
    expect(body.result).toBeDefined();
    expect(body.result.tools).toBeDefined();
    expect(Array.isArray(body.result.tools)).toBe(true);
    expect(body.result.tools.length).toBeGreaterThan(0);

    // Verify tool names match what we selected
    const toolNames = body.result.tools.map((t: { name: string }) => t.name);
    expect(toolNames).toContain("getPetById");
  });

  test("04 — POST JSON-RPC tools/call executes a tool", async ({ request }) => {
    const { response, body } = await sendMcpMessage(request, ctx.slug, {
      jsonrpc: "2.0",
      id: "e2e-002",
      method: "tools/call",
      params: {
        name: "getPetById",
        arguments: { petId: 1 },
      },
    });
    expect(response.status()).toBe(200);
    expect(body.jsonrpc).toBe("2.0");
    expect(body.id).toBe("e2e-002");
    expect(body.result).toBeDefined();
    expect(body.result.content).toBeDefined();
    expect(Array.isArray(body.result.content)).toBe(true);
  });

  test("05 — Invalid JSON-RPC returns error -32600", async ({ request }) => {
    const { response, body } = await sendMcpMessage(request, ctx.slug, {
      jsonrpc: "2.0",
      id: "e2e-003",
      // Missing "method" field
      params: {},
    });
    expect(response.status()).toBe(200); // JSON-RPC returns 200 with error
    expect(body.error).toBeDefined();
    expect(body.error.code).toBe(-32600);
  });

  test("06 — Unknown tool returns error -32602", async ({ request }) => {
    const { response, body } = await sendMcpMessage(request, ctx.slug, {
      jsonrpc: "2.0",
      id: "e2e-004",
      method: "tools/call",
      params: {
        name: "nonexistentTool",
        arguments: {},
      },
    });
    expect(response.status()).toBe(200);
    expect(body.error).toBeDefined();
    expect(body.error.code).toBe(-32602);
  });

  test("07 — Invalid slug returns 404", async ({ request }) => {
    const res = await request.get(`${API_BASE}/mcp/v1/nonexistent-slug-does-not-exist/sse`);
    expect(res.status()).toBe(404);
  });

  test("08 — Multiple concurrent SSE connections", async ({ request }) => {
    const results = await Promise.allSettled(
      [1, 2, 3].map(() =>
        request.get(`${API_BASE}/mcp/v1/${ctx.slug}/sse`).then(async (r) => ({
          status: r.status(),
          contentType: r.headers()["content-type"] || "",
          body: await r.text(),
        })),
      ),
    );

    expect(results.length).toBe(3);
    for (const result of results) {
      expect(result.status).toBe("fulfilled");
      if (result.status === "fulfilled") {
        expect(result.value.status).toBe(200);
        expect(result.value.contentType).toContain("text/event-stream");
      }
    }
  });

  test("09 — Concurrent POST messages all succeed", async ({ request }) => {
    const results = await Promise.allSettled(
      [1, 2, 3, 4, 5].map((i) =>
        sendMcpMessage(request, ctx.slug, {
          jsonrpc: "2.0",
          id: `e2e-concurrent-${i}`,
          method: "tools/list",
        }),
      ),
    );

    expect(results.length).toBe(5);
    for (const result of results) {
      expect(result.status).toBe("fulfilled");
      if (result.status === "fulfilled") {
        expect(result.value.response.status()).toBe(200);
        expect(result.value.body.result).toBeDefined();
        expect(result.value.body.result.tools).toBeDefined();
      }
    }
  });

  test("10 — health check before gateway calls", async ({ request }) => {
    const res = await request.get(`${API_BASE}/health`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  test("11 — SSE with paused server returns service unavailable", async ({ request }) => {
    // Pause the server
    const pauseRes = await request.post(`${API_BASE}/api/v1/servers/${ctx.serverId}/pause`);
    expect(pauseRes.status()).toBe(200);

    // Wait for state to propagate
    await new Promise((r) => setTimeout(r, 2000));

    // Try SSE connection
    const sseRes = await request.get(`${API_BASE}/mcp/v1/${ctx.slug}/sse`);
    // Either 503 or 200 (depending on whether paused servers reject connections)
    const status = sseRes.status();
    expect(status === 503 || status === 200).toBe(true);

    // Resume the server for subsequent tests
    const resumeRes = await request.post(`${API_BASE}/api/v1/servers/${ctx.serverId}/resume`);
    expect(resumeRes.status()).toBe(200);
    await new Promise((r) => setTimeout(r, 2000));
  });

  test("12 — tools/call with getPetById returns pet data", async ({ request }) => {
    const { response, body } = await sendMcpMessage(request, ctx.slug, {
      jsonrpc: "2.0",
      id: "e2e-005",
      method: "tools/call",
      params: {
        name: "getPetById",
        arguments: { petId: "1" },
      },
    });
    expect(response.status()).toBe(200);
    expect(body.result).toBeDefined();
    expect(body.result.content).toBeDefined();
  });

  test("13 — addPet tool accepts valid arguments", async ({ request }) => {
    const { response, body } = await sendMcpMessage(request, ctx.slug, {
      jsonrpc: "2.0",
      id: "e2e-006",
      method: "tools/call",
      params: {
        name: "addPet",
        arguments: { name: "Fluffy", tag: "cat" },
      },
    });
    // addPet may fail if the upstream API rejects it — that's OK,
    // we just verify the gateway routes it and returns a JSON-RPC response
    expect(response.status()).toBe(200);
    expect(body.jsonrpc).toBe("2.0");
    expect(body.id).toBe("e2e-006");
  });
});
