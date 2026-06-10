"""Unit tests for the 8 security scanner rules (F5 §3.3).

Each rule has exactly 2 tests:
- **positive** — confirms the rule detects a real issue
- **negative** — confirms the rule returns empty for safe input
"""

from __future__ import annotations

from app.services.security_scanner.rules import (
    check_credential_in_response,
    check_deprecated_methods,
    check_large_tool_set,
    check_no_auth_delete,
    check_no_auth_writes,
    check_prompt_injection_desc,
    check_ssrf_url_param,
    check_untagged_endpoints,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _tool(
    name: str = "test_tool",
    method: str = "GET",
    path: str = "/test",
    tags: list[str] | None = None,
    description: str = "A test tool",
    properties: dict | None = None,
    response_properties: dict | None = None,
    **extra: object,
) -> dict:
    """Build a minimal tool dict matching the ``tools_config`` JSONB shape."""
    tool: dict = {
        "name": name,
        "description": description,
        "method": method,
        "path": path,
        "tags": tags or [],
        "input_schema": {
            "type": "object",
            "properties": properties or {},
        },
        "parameters": [],
        "request_body_schema": None,
        "response_schemas": {
            "200": {
                "type": "object",
                "properties": response_properties or {},
            },
        },
        "security_requirements": [],
        "selected": True,
    }
    tool.update(extra)
    return tool


# ── SSRF_URL_PARAM ────────────────────────────────────────────────────────────


class TestSsrfUrlParam:
    def test_detects_url_like_params(self) -> None:
        """Positive: tool with a ``url`` parameter of type string is flagged."""
        tools = [
            _tool(name="fetch_page", properties={"url": {"type": "string"}}),
        ]
        findings = check_ssrf_url_param(tools)
        assert len(findings) == 1
        f = findings[0]
        assert f["id"] == "SSRF_URL_PARAM"
        assert f["severity"] == "critical"
        assert "url" in f["description"]
        assert "fetch_page" in f["affected_tools"]

    def test_skips_non_url_params(self) -> None:
        """Negative: tool with only safe parameter names is not flagged."""
        tools = [
            _tool(
                name="list_users",
                properties={"page": {"type": "integer"}, "limit": {"type": "integer"}},
            ),
        ]
        findings = check_ssrf_url_param(tools)
        assert findings == []


# ── NO_AUTH_DELETE ────────────────────────────────────────────────────────────


class TestNoAuthDelete:
    def test_detects_unauthenticated_delete(self) -> None:
        """Positive: DELETE tool with no auth is flagged."""
        tools = [
            _tool(name="delete_user", method="DELETE"),
        ]
        findings = check_no_auth_delete(tools, auth_scheme="none")
        assert len(findings) == 1
        f = findings[0]
        assert f["id"] == "NO_AUTH_DELETE"
        assert f["severity"] == "critical"
        assert "delete_user" in f["affected_tools"]

    def test_skips_authenticated_delete(self) -> None:
        """Negative: DELETE tool with auth configured is not flagged."""
        tools = [
            _tool(name="delete_user", method="DELETE"),
        ]
        findings = check_no_auth_delete(tools, auth_scheme="bearer")
        assert findings == []


# ── CREDENTIAL_IN_RESPONSE ────────────────────────────────────────────────────


class TestCredentialInResponse:
    def test_detects_credential_fields(self) -> None:
        """Positive: response with ``api_key`` property is flagged."""
        tools = [
            _tool(
                name="get_token",
                response_properties={"api_key": {"type": "string"}},
            ),
        ]
        findings = check_credential_in_response(tools)
        assert len(findings) == 1
        f = findings[0]
        assert f["id"] == "CREDENTIAL_IN_RESPONSE"
        assert f["severity"] == "high"
        assert "api_key" in f["description"]
        assert "get_token" in f["affected_tools"]

    def test_skips_safe_responses(self) -> None:
        """Negative: response with only safe fields is not flagged."""
        tools = [
            _tool(
                name="list_users",
                response_properties={"id": {"type": "integer"}, "name": {"type": "string"}},
            ),
        ]
        findings = check_credential_in_response(tools)
        assert findings == []


# ── PROMPT_INJECTION_DESC ──────────────────────────────────────────────────────


class TestPromptInjectionDesc:
    def test_detects_markdown_links_in_description(self) -> None:
        """Positive: description with a markdown link is flagged."""
        tools = [
            _tool(name="fetch_data", description="See [docs](https://example.com) for details"),
        ]
        findings = check_prompt_injection_desc(tools)
        assert len(findings) == 1
        f = findings[0]
        assert f["id"] == "PROMPT_INJECTION_DESC"
        assert f["severity"] == "high"
        assert "fetch_data" in f["affected_tools"]

    def test_skips_safe_descriptions(self) -> None:
        """Negative: clean description without injection patterns is not flagged."""
        tools = [
            _tool(name="list_users", description="List all users in the system"),
        ]
        findings = check_prompt_injection_desc(tools)
        assert findings == []


# ── NO_AUTH_WRITES ─────────────────────────────────────────────────────────────


class TestNoAuthWrites:
    def test_detects_unauthenticated_writes(self) -> None:
        """Positive: POST/PUT/PATCH tools with no auth are flagged."""
        tools = [
            _tool(name="create_user", method="POST"),
            _tool(name="update_user", method="PUT"),
            _tool(name="patch_user", method="PATCH"),
        ]
        findings = check_no_auth_writes(tools, auth_scheme="none")
        assert len(findings) == 1
        f = findings[0]
        assert f["id"] == "NO_AUTH_WRITES"
        assert f["severity"] == "high"
        assert "create_user" in f["affected_tools"]
        assert "update_user" in f["affected_tools"]
        assert "patch_user" in f["affected_tools"]

    def test_skips_authenticated_writes(self) -> None:
        """Negative: POST tool with auth configured is not flagged."""
        tools = [
            _tool(name="create_user", method="POST"),
        ]
        findings = check_no_auth_writes(tools, auth_scheme="bearer")
        assert findings == []


# ── UNTAGGED_ENDPOINTS ────────────────────────────────────────────────────────


class TestUntaggedEndpoints:
    def test_detects_missing_tags(self) -> None:
        """Positive: tool with empty tags list is flagged."""
        tools = [
            _tool(name="orphan_endpoint", tags=[]),
        ]
        findings = check_untagged_endpoints(tools)
        assert len(findings) == 1
        f = findings[0]
        assert f["id"] == "UNTAGGED_ENDPOINTS"
        assert f["severity"] == "medium"
        assert "orphan_endpoint" in f["affected_tools"]

    def test_skips_tagged_tools(self) -> None:
        """Negative: tool with tags is not flagged."""
        tools = [
            _tool(name="list_users", tags=["users"]),
        ]
        findings = check_untagged_endpoints(tools)
        assert findings == []


# ── DEPRECATED_HTTP_METHODS ────────────────────────────────────────────────────


class TestDeprecatedMethods:
    def test_detects_trace_and_connect(self) -> None:
        """Positive: tool with TRACE or CONNECT method is flagged."""
        tools = [
            _tool(name="trace_route", method="TRACE"),
            _tool(name="connect_tunnel", method="CONNECT"),
        ]
        findings = check_deprecated_methods(tools)
        assert len(findings) == 2
        for f in findings:
            assert f["id"] == "DEPRECATED_HTTP_METHODS"
            assert f["severity"] == "medium"

    def test_skips_standard_methods(self) -> None:
        """Negative: tools using GET/POST/PUT/PATCH/DELETE are not flagged."""
        tools = [
            _tool(name="get_item", method="GET"),
            _tool(name="create_item", method="POST"),
            _tool(name="delete_item", method="DELETE"),
        ]
        findings = check_deprecated_methods(tools)
        assert findings == []


# ── LARGE_TOOL_SET ─────────────────────────────────────────────────────────────


class TestLargeToolSet:
    def test_detects_50_plus_tools(self) -> None:
        """Positive: 50+ tools triggers an info finding."""
        tools = [_tool(name=f"tool_{i}") for i in range(50)]
        findings = check_large_tool_set(tools)
        assert len(findings) == 1
        f = findings[0]
        assert f["id"] == "LARGE_TOOL_SET"
        assert f["severity"] == "info"

    def test_skips_small_tool_set(self) -> None:
        """Negative: fewer than 50 tools is not flagged."""
        tools = [_tool(name=f"tool_{i}") for i in range(49)]
        findings = check_large_tool_set(tools)
        assert findings == []
