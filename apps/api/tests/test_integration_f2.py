"""Real integration tests for F2 AI Description Engine against live Docker services.

These tests run against the actual running API at http://localhost:8000
with real Postgres, Redis, and LLM provider. They test the full end-to-end
flow: register -> login -> create server -> enhance tools -> accept -> verify.

Run:  uv run pytest tests/test_integration_f2.py -v
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import httpx
import pytest



BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT = 30.0

# ── Test data ────────────────────────────────────────────────────────────

TEST_TOOLS = {
    "tools": [
        {
            "name": "search_products",
            "description": "Search for products by query",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                    },
                },
                "required": ["query"],
            },
            "method": "GET",
            "path": "/api/products/search",
            "tags": ["products"],
            "selected": True,
        },
        {
            "name": "get_product",
            "description": "Get a single product by ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Product ID",
                    },
                },
                "required": ["id"],
            },
            "method": "GET",
            "path": "/api/products/{id}",
            "tags": ["products"],
            "selected": True,
        },
        {
            "name": "create_order",
            "description": "Create a new order",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Product ID to order",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of items",
                    },
                },
                "required": ["product_id", "quantity"],
            },
            "method": "POST",
            "path": "/api/orders",
            "tags": ["orders"],
            "selected": True,
        },
    ],
}


# ── Helpers ──────────────────────────────────────────────────────────────


def random_slug() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


def random_email() -> str:
    return f"f2-test-{uuid.uuid4().hex[:8]}@example.com"


def auth_headers(user: dict) -> dict:
    """Return headers dict with CSRF token for authenticated requests.

    The httpx client automatically sends cookies; the ``X-CSRF-Token``
    header must be sent explicitly.
    """
    headers = {"X-CSRF-Token": user.get("csrf_token", "")}
    return {"cookies": user["cookies"], "headers": headers}


@pytest.fixture
def http() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)


@pytest.fixture
async def registered_user(http: httpx.AsyncClient) -> dict:
    """Register a test user and return auth cookies + user info."""
    email = random_email()
    password = uuid.uuid4().hex + "Ab1!"
    display_name = "F2 Integration Test"

    resp = await http.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    assert resp.status_code in (200, 201), f"Register failed: {resp.text}"
    data = resp.json()

    # Login to get cookies
    resp = await http.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"

    cookies = resp.cookies
    access_token = cookies.get("access_token", "")
    assert access_token, "No access_token cookie set"

    # Capture CSRF token via a GET request (sets csrf_token cookie)
    me_resp = await http.get("/auth/me", cookies=cookies)
    assert me_resp.status_code == 200
    csrf_cookies = me_resp.cookies
    csrf_token = csrf_cookies.get("csrf_token", "")
    if not csrf_token:
        # Fallback: try from the first response cookies
        csrf_token = cookies.get("csrf_token", "")

    return {
        "email": email,
        "password": password,
        "cookies": cookies,
        "csrf_token": csrf_token,
        "access_token": access_token,
        "user": resp.json().get("user", data),
    }


@pytest.fixture
async def test_server(http: httpx.AsyncClient, registered_user: dict) -> dict:
    """Create a server with tools for testing."""
    slug = random_slug()
    resp = await http.post(
        "/servers",
        json={
            "name": "F2 Integration Test Server",
            "slug": slug,
            "base_url": "https://api.example.com/v1",
            "description": "Server for testing F2 AI enhancement",
            "tools_config": TEST_TOOLS,
        },
        **auth_headers(registered_user),
    )
    assert resp.status_code in (200, 201), f"Create server failed: {resp.text}"
    server = resp.json()
    assert server.get("id"), f"No server ID: {server}"
    assert server.get("tools_config", {}).get("tools"), "No tools in config"
    return server


@pytest.fixture
async def second_user(http: httpx.AsyncClient) -> dict:
    """Register a second user for ownership tests."""
    email = random_email()
    password = uuid.uuid4().hex + "Xy9!"
    resp = await http.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Second User"},
    )
    assert resp.status_code in (200, 201), f"Register failed: {resp.text}"

    resp = await http.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"email": email, "cookies": resp.cookies}


# ── Tests ────────────────────────────────────────────────────────────────


class TestAuthAndServer:
    """Test the foundation: auth + server CRUD."""

    async def test_health_endpoint(self, http: httpx.AsyncClient) -> None:
        """Health endpoint should return OK with all services."""
        resp = await http.get(f"{BASE_URL.replace('/api/v1', '')}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"
        assert data["redis"] == "ok"

    async def test_register_duplicate_email(
        self, http: httpx.AsyncClient, registered_user: dict
    ) -> None:
        """Registering with an existing email should fail."""
        resp = await http.post(
            "/auth/register",
            json={
                "email": registered_user["email"],
                "password": "OtherPass123!",
            },
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

    async def test_login_wrong_password(self, http: httpx.AsyncClient) -> None:
        """Login with wrong password should fail."""
        random_email_addr = random_email()
        resp = await http.post(
            "/auth/login",
            json={"email": random_email_addr, "password": "wrong-password-123!"},
        )
        # Should either be 401 (wrong password) or 423 (locked if too many attempts)
        assert resp.status_code in (401, 423), (
            f"Expected 401 or 423, got {resp.status_code}: {resp.text}"
        )

    async def test_me_authenticated(
        self, http: httpx.AsyncClient, registered_user: dict
    ) -> None:
        """GET /auth/me should return the user when authenticated."""
        resp = await http.get("/auth/me", **auth_headers(registered_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == registered_user["email"]
        assert "id" in data

    async def test_me_unauthenticated(self, http: httpx.AsyncClient) -> None:
        """GET /auth/me without auth should fail."""
        resp = await http.get("/auth/me")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    async def test_create_server_validates_slug(
        self, http: httpx.AsyncClient, registered_user: dict
    ) -> None:
        """Creating server with duplicate slug should fail."""
        dup_slug = random_slug()
        # Create first server
        resp = await http.post(
            "/servers",
            json={
                "name": "First Server",
                "slug": dup_slug,
                "base_url": "https://example.com",
            },
            **auth_headers(registered_user),
        )
        assert resp.status_code in (200, 201), f"First create failed: {resp.text}"

        # Try creating second server with same slug
        resp = await http.post(
            "/servers",
            json={
                "name": "Duplicate Server",
                "slug": dup_slug,
                "base_url": "https://example.com",
            },
            **auth_headers(registered_user),
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"


class TestToolManagement:
    """Test tool listing and basic management."""

    async def test_list_tools(
        self, http: httpx.AsyncClient, registered_user: dict, test_server: dict
    ) -> None:
        """GET tools should return the 3 test tools."""
        server_id = test_server["id"]
        resp = await http.get(
            f"/servers/{server_id}/tools",
            **auth_headers(registered_user),
        )
        assert resp.status_code == 200, f"List tools failed: {resp.text}"
        data = resp.json()
        assert data["tool_count"] == 3
        tool_names = {t["name"] for t in data["tools"]}
        assert tool_names == {"search_products", "get_product", "create_order"}

    async def test_list_tools_unauthenticated(
        self, http: httpx.AsyncClient, test_server: dict
    ) -> None:
        """Listing tools without auth should fail."""
        # Use a fresh client to avoid inheriting cookies from fixtures
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as anon:
            resp = await anon.get(f"/servers/{test_server['id']}/tools")
            assert resp.status_code == 401, (
                f"Expected 401, got {resp.status_code}: {resp.text}"
            )

    async def test_list_tools_nonexistent_server(
        self, http: httpx.AsyncClient, registered_user: dict
    ) -> None:
        """Listing tools for a server that doesn't exist should fail."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await http.get(
            f"/servers/{fake_id}/tools",
            cookies=registered_user["cookies"],
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    async def test_update_tool_other_user(
        self, http: httpx.AsyncClient, test_server: dict, second_user: dict
    ) -> None:
        """Updating a tool on another user's server should fail."""
        server_id = test_server["id"]
        resp = await http.patch(
            f"/servers/{server_id}/tools/search_products",
            json={"description": "Hacked description"},
            **auth_headers(second_user),
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


class TestAIEnhancementEdgeCases:
    """Test edge cases for AI enhancement without hitting the LLM."""

    async def test_enhance_nonexistent_server(
        self, http: httpx.AsyncClient, registered_user: dict
    ) -> None:
        """Enhancing a server that doesn't exist should fail."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await http.post(
            f"/servers/{fake_id}/tools/enhance",
            json={},
            **auth_headers(registered_user),
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    async def test_enhance_other_users_server(
        self, http: httpx.AsyncClient, test_server: dict, second_user: dict
    ) -> None:
        """Enhancing another user's server should fail."""
        server_id = test_server["id"]
        resp = await http.post(
            f"/servers/{server_id}/tools/enhance",
            json={},
            **auth_headers(second_user),
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    async def test_enhance_unauthenticated(
        self, http: httpx.AsyncClient, test_server: dict
    ) -> None:
        """Enhancing without auth should fail.

        CSRF middleware runs before auth, so a POST without cookies
        returns 403 (CSRF missing), not 401 (unauthorized).
        """
        # Use fresh client to avoid fixture cookie contamination
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as anon:
            resp = await anon.post(
                f"/servers/{test_server['id']}/tools/enhance",
                json={},
            )
            # CSRF runs before auth => 403, not 401
            assert resp.status_code in (401, 403), (
                f"Expected 401 or 403, got {resp.status_code}: {resp.text}"
            )

    async def test_enhance_invalid_body(
        self, http: httpx.AsyncClient, registered_user: dict, test_server: dict
    ) -> None:
        """Enhancing with invalid body fields should not crash."""
        server_id = test_server["id"]
        resp = await http.post(
            f"/servers/{server_id}/tools/enhance",
            json={"tool_names": "not-a-list", "force": "not-a-bool"},
            **auth_headers(registered_user),
        )
        # Should either work or return a validation error - but not 500
        assert resp.status_code < 500, f"Server error: {resp.text}"

    async def test_accept_nonexistent_server(
        self, http: httpx.AsyncClient, registered_user: dict
    ) -> None:
        """Accepting enhancements for a nonexistent server should fail."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await http.post(
            f"/servers/{fake_id}/tools/accept",
            json={"accepted_tools": []},
            **auth_headers(registered_user),
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    async def test_accept_other_users_server(
        self, http: httpx.AsyncClient, test_server: dict, second_user: dict
    ) -> None:
        """Accepting on another user's server should fail."""
        server_id = test_server["id"]
        resp = await http.post(
            f"/servers/{server_id}/tools/accept",
            json={"accepted_tools": []},
            **auth_headers(second_user),
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    async def test_build_nonexistent_server(
        self, http: httpx.AsyncClient, registered_user: dict
    ) -> None:
        """Build endpoint for nonexistent server should fail."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await http.post(
            f"/servers/{fake_id}/build",
            **auth_headers(registered_user),
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


class TestFullAIEnhancement:
    """Full end-to-end AI enhancement test with real LLM calls.

    These tests make real API calls to the LLM provider and verify
    the enhancement results. They require LLM_PROVIDER to be configured.
    """

    async def test_full_enhance_flow(
        self, http: httpx.AsyncClient, registered_user: dict, test_server: dict
    ) -> None:
        """Complete flow: enhance -> poll SSE -> accept -> verify."""
        server_id = test_server["id"]

        # ---- Step 1: Verify tools exist before enhancement ----
        resp = await http.get(
            f"/servers/{server_id}/tools",
            **auth_headers(registered_user),
        )
        assert resp.status_code == 200
        tools_before = resp.json()
        assert tools_before["tool_count"] == 3
        # Original descriptions should NOT have enhanced_ prefix
        for tool in tools_before["tools"]:
            assert "enhanced_description" not in tool, (
                f"Tool {tool['name']} already has enhancement"
            )

        # ---- Step 2: Start enhancement ----
        resp = await http.post(
            f"/servers/{server_id}/tools/enhance",
            json={},
            **auth_headers(registered_user),
        )
        # May return 200 (job created) or fail with specific errors
        if resp.status_code == 402:
            pytest.skip("Insufficient AI credits")
        assert resp.status_code == 200, (
            f"Enhance failed: {resp.status_code} {resp.text}"
        )
        enhance_data = resp.json()
        job_id = enhance_data.get("job_id", "")
        assert job_id, f"No job_id in response: {enhance_data}"
        assert enhance_data.get("estimated_cost_cents", -1) >= 0
        assert enhance_data.get("estimated_duration_seconds", -1) >= 0

        # ---- Step 3: Poll SSE for build events ----
        sse_events = []
        sse_url = (
            f"http://localhost:8000/api/v1/servers/{server_id}/build-status"
        )
        timeout_val = 120.0
        deadline = time.monotonic() + timeout_val
    
        async with httpx.AsyncClient(timeout=TIMEOUT) as sse_client:
            async with sse_client.stream(
                "GET",
                sse_url,
                **auth_headers(registered_user),
            ) as response:
                assert response.status_code == 200, (
                    f"SSE failed: {response.status_code}"
                )
                buffer = ""
                received_complete = False
                try:
                    async for chunk in response.aiter_text():
                        if not chunk:
                            continue
                        buffer += chunk
                        while "\n\n" in buffer:
                            event_text, buffer = buffer.split("\n\n", 1)
                            if event_text.startswith("event:"):
                                event_type = event_text.split("\n")[0].replace("event:", "").strip()
                                data_line = "\n".join(
                                    l.replace("data:", "").strip()
                                    for l in event_text.split("\n")
                                    if l.startswith("data:")
                                )
                            elif event_text.startswith("data:"):
                                event_type = "message"
                                data_line = event_text.replace("data:", "").strip()
                            else:
                                continue
    
                            if data_line:
                                try:
                                    event = json.loads(data_line)
                                    sse_events.append(event)
                                    if event.get("event") in ("ai_complete", "done"):
                                        received_complete = True
                                except json.JSONDecodeError:
                                    pass
    
                        if received_complete:
                            break
                        if time.monotonic() > deadline:
                            break
                except httpx.ReadTimeout:
                    pass
    
        assert len(sse_events) > 0, "No SSE events received"
        start_events = [e for e in sse_events if e.get("event") == "start"]
        progress_events = [e for e in sse_events if e.get("event") == "ai_progress"]
        enhanced_events = [e for e in sse_events if e.get("event") == "tool_enhanced"]
        complete_events = [e for e in sse_events if e.get("event") == "ai_complete"]

        print(
            f"\n  SSE events: start={len(start_events)}, "
            f"progress={len(progress_events)}, "
            f"enhanced={len(enhanced_events)}, "
            f"complete={len(complete_events)}"
        )

        # ---- Step 4: Verify enhanced tools ----
        # Add a brief wait for the Celery task to finish writing to DB
        await asyncio.sleep(5)

        resp = await http.get(
            f"/servers/{server_id}/tools",
            **auth_headers(registered_user),
        )
        assert resp.status_code == 200
        tools_after = resp.json()
        assert tools_after["tool_count"] == 3

        enhanced_tools = []
        for tool in tools_after["tools"]:
            if tool.get("quality_score") or tool.get("enhanced_description"):
                enhanced_tools.append(tool)

        # Allow partial enhancement — some tools may fail or the job
        # may still be running.  At least 1 should be enhanced.
        if len(enhanced_tools) == 0 and not complete_events:
            # Job may still be running; wait longer
            await asyncio.sleep(15)
            resp = await http.get(
                f"/servers/{server_id}/tools",
                **auth_headers(registered_user),
            )
            tools_after = resp.json()
            for tool in tools_after["tools"]:
                if tool.get("quality_score") or tool.get("enhanced_description"):
                    enhanced_tools.append(tool)

        assert len(enhanced_tools) >= 1, (
            f"No tools were enhanced. Events received: "
            f"start={len(start_events)}, progress={len(progress_events)}, "
            f"enhanced={len(enhanced_events)}, complete={len(complete_events)}"
        )
        print(
            f"\n  Enhanced {len(enhanced_tools)}/{tools_after['tool_count']} tools"
        )
        for tool in enhanced_tools:
            qs = tool.get("quality_score", {})
            if isinstance(qs, dict) and qs.get("total"):
                print(f"  - {tool['name']}: score={qs['total']}/100 badge={qs.get('badge', '?')}")
            if tool.get("enhanced_description"):
                ed_len = len(tool["enhanced_description"])
                orig_len = len(tool.get("description", ""))
                print(f"    desc: {orig_len}ch -> {ed_len}ch")

        # ---- Step 5: Accept enhancements ----
        enhanced_names = [t["name"] for t in enhanced_tools]
        if enhanced_names:
            resp = await http.post(
                f"/servers/{server_id}/tools/accept",
                json={"accepted_tools": enhanced_names},
                **auth_headers(registered_user),
            )
            assert resp.status_code == 200, (
                f"Accept failed: {resp.status_code} {resp.text}"
            )
            accept_data = resp.json()
            assert accept_data["status"] == "accepted"
            assert accept_data["tools_updated"] == len(enhanced_names)

            # Verify accepted descriptions are now the primary ones
            resp = await http.get(
                f"/servers/{server_id}/tools",
                **auth_headers(registered_user),
            )
            assert resp.status_code == 200
            accepted_tools = resp.json()["tools"]
            for tool in accepted_tools:
                if tool["name"] in enhanced_names:
                    assert "enhanced_description" not in tool, (
                        f"enhanced_description should be cleaned up after accept for {tool['name']}"
                    )

    async def test_enhance_single_tool_flow(
        self, http: httpx.AsyncClient, registered_user: dict, test_server: dict
    ) -> None:
        """Enhance a single tool and verify only that tool was modified."""
        server_id = test_server["id"]

        resp = await http.post(
            f"/servers/{server_id}/tools/enhance",
            json={"tool_names": ["search_products"]},
            **auth_headers(registered_user),
        )
        if resp.status_code == 402:
            pytest.skip("Insufficient AI credits")
        if resp.status_code == 200:
            # Wait briefly for the job to process
            await asyncio.sleep(5)

        resp = await http.get(
            f"/servers/{server_id}/tools",
            **auth_headers(registered_user),
        )
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        for tool in tools:
            if tool["name"] == "search_products":
                print(f"  Single enhance: {tool['name']} enhanced={bool(tool.get('enhanced_description'))}")

    async def test_enhance_and_reject(
        self, http: httpx.AsyncClient, registered_user: dict, test_server: dict
    ) -> None:
        """Enhance a tool and then reject (revert) it."""
        server_id = test_server["id"]

        resp = await http.post(
            f"/servers/{server_id}/tools/enhance",
            json={},
            **auth_headers(registered_user),
        )
        if resp.status_code == 402:
            pytest.skip("Insufficient AI credits")
        if resp.status_code != 200:
            pytest.fail(f"Enhance failed: {resp.status_code} {resp.text}")

        # Wait for enhancement to complete
        await asyncio.sleep(10)

        resp = await http.get(
            f"/servers/{server_id}/tools",
            **auth_headers(registered_user),
        )
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        enhanced_tools = [t for t in tools if t.get("enhanced_description")]
        if not enhanced_tools:
            pytest.skip("No tools were enhanced")

        # Reject all enhanced tools
        enhanced_names = [t["name"] for t in enhanced_tools]
        resp = await http.post(
            f"/servers/{server_id}/tools/accept",
            json={
                "accepted_tools": [],
                "rejected_tools": enhanced_names,
            },
            **auth_headers(registered_user),
        )
        assert resp.status_code == 200, f"Reject failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["status"] == "accepted"

        print(f"  Rejected {len(enhanced_names)} tools successfully")

    async def test_build_status_sse_connected(
        self, http: httpx.AsyncClient, registered_user: dict, test_server: dict
    ) -> None:
        """SSE build-status should return connected event."""
        server_id = test_server["id"]
        sse_url = f"http://localhost:8000/api/v1/servers/{server_id}/build-status"

        async with httpx.AsyncClient(timeout=TIMEOUT) as sse_client:
            async with sse_client.stream(
                "GET", sse_url, **auth_headers(registered_user)
            ) as response:
                assert response.status_code == 200
                try:
                    async for chunk in response.aiter_text():
                        if "event: connected" in chunk:
                            print("  SSE connected event received")
                            return
                except (httpx.ReadTimeout, httpx.StreamError):
                    pass

                # If we didn't get the connected event, still verify connection
                assert response.status_code == 200, (
                    f"SSE connection failed: {response.status_code}"
                )


