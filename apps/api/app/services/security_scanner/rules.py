"""Security scanner rule definitions (F5 §3.3).

Each check_* function inspects a list of tool dicts (from the server's
``tools_config["tools"]`` JSONB column) and returns a list of finding dicts
matching the ``Finding`` Pydantic schema.

Checks that require authentication context accept an ``auth_scheme`` string;
the ``RULES`` registry's ``requires_auth`` field tells the scanner whether to
pass it.
"""

from __future__ import annotations

import re
from typing import Any


def check_ssrf_url_param(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check for URL-like parameters that could be exploited for SSRF.

    Scans each tool's ``input_schema.properties`` for parameter names that
    match common URL-related keywords. Flags parameters whose type is
    ``"string"`` or unspecified.
    """
    url_param_names = {
        "url",
        "endpoint",
        "uri",
        "target",
        "host",
        "href",
        "link",
        "src",
        "source",
    }
    findings: list[dict[str, Any]] = []
    for tool in tools:
        tool_name = tool.get("name", "unknown")
        properties = tool.get("input_schema", {}).get("properties", {})
        for param_name, param_schema in properties.items():
            if param_name.lower() in url_param_names:
                param_type = param_schema.get("type") if isinstance(param_schema, dict) else None
                if param_type is None or param_type == "string":
                    findings.append({
                        "id": "SSRF_URL_PARAM",
                        "severity": "critical",
                        "title": "Tool accepts URL parameter (SSRF risk)",
                        "description": f"Parameter '{param_name}' is a URL-like string",
                        "affected_tools": [tool_name],
                        "remediation": (
                            "Validate the URL is on an allowlist of approved hosts"
                            " before fetching."
                        ),
                        "references": [
                            "https://owasp.org/www-community/attacks/Server_Side_Request_Forgery",
                        ],
                    })
    return findings


def check_no_auth_delete(tools: list[dict[str, Any]], auth_scheme: str) -> list[dict[str, Any]]:
    """Check for DELETE operations without authentication (CRITICAL)."""
    if auth_scheme != "none":
        return []
    findings: list[dict[str, Any]] = []
    for tool in tools:
        method = tool.get("method") or tool.get("http_method")
        if method == "DELETE":
            tool_name = tool.get("name", "unknown")
            findings.append({
                "id": "NO_AUTH_DELETE",
                "severity": "critical",
                "title": "DELETE operation without authentication",
                "description": (
                    f"DELETE method on tool '{tool_name}' with no authentication configured."
                ),
                "affected_tools": [tool_name],
                "remediation": (
                    "Add Bearer or API Key authentication before deploying"
                    " destructive tools."
                ),
                "references": [
                    "https://owasp.org/www-community/attacks/HTTP_Methods",
                ],
            })
    return findings


def check_credential_in_response(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check for credential-like fields in response schemas (HIGH).

    Scans each tool's ``response_schemas`` dictionary for property names
    containing keywords such as ``password``, ``secret``, ``token``, ``key``,
    or ``private_key``.
    """
    cred_keywords = {"password", "secret", "token", "key", "private_key"}
    findings: list[dict[str, Any]] = []
    for tool in tools:
        tool_name = tool.get("name", "unknown")
        response_schemas = tool.get("response_schemas", {})
        for schema in response_schemas.values():
            if not isinstance(schema, dict):
                continue
            properties = schema.get("properties", {})
            if not isinstance(properties, dict):
                continue
            for prop_name in properties:
                prop_lower = prop_name.lower()
                if any(cred in prop_lower for cred in cred_keywords):
                    findings.append({
                        "id": "CREDENTIAL_IN_RESPONSE",
                        "severity": "high",
                        "title": "Response may include sensitive credentials",
                        "description": (
                            f"Response for '{tool_name}' contains property "
                            f"'{prop_name}' which may expose sensitive credentials."
                        ),
                        "affected_tools": [tool_name],
                        "remediation": (
                            "Remove sensitive fields from response schemas or mark them "
                            "with writeOnly: true."
                        ),
                        "references": [
                            "https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html",
                        ],
                    })
                    break  # one finding per tool
    return findings


def check_prompt_injection_desc(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check tool descriptions for prompt-injection-amenable patterns (HIGH).

    Flags descriptions containing:
    - Markdown links  ``[...](...)``
    - HTML tags ``<...>``
    - "ignore previous instructions" patterns (case-insensitive)
    """
    findings: list[dict[str, Any]] = []
    for tool in tools:
        tool_name = tool.get("name", "unknown")
        description = tool.get("description", "")
        has_markdown_link = bool(re.search(r"\[.*?\]\(.*?\)", description))
        has_html_tag = bool(re.search(r"<[^>]+>", description))
        has_ignore_pattern = bool(
            re.search(r"ignore\s+previous\s+instructions", description, re.IGNORECASE)
        )
        if has_markdown_link or has_html_tag or has_ignore_pattern:
            findings.append({
                "id": "PROMPT_INJECTION_DESC",
                "severity": "high",
                "title": "Tool description may be vulnerable to prompt injection",
                "description": (
                    f"Description of '{tool_name}' contains patterns that could "
                    f"be exploited for prompt injection."
                ),
                "affected_tools": [tool_name],
                "remediation": (
                    "Remove markdown links, HTML tags, and instruction-override patterns "
                    "from tool descriptions."
                ),
                "references": [
                    "https://owasp.org/www-community/attacks/Prompt_Injection",
                ],
            })
    return findings


def check_no_auth_writes(tools: list[dict[str, Any]], auth_scheme: str) -> list[dict[str, Any]]:
    """Check for write operations without authentication (HIGH).

    Returns a single aggregate finding listing all affected tools when no
    authentication scheme is configured but the server exposes POST, PUT,
    or PATCH endpoints.
    """
    if auth_scheme != "none":
        return []
    write_methods = {"POST", "PUT", "PATCH"}
    affected: list[str] = []
    for tool in tools:
        method = tool.get("method") or tool.get("http_method")
        if method in write_methods:
            affected.append(tool.get("name", "unknown"))
    if not affected:
        return []
    return [
        {
            "id": "NO_AUTH_WRITES",
            "severity": "high",
            "title": "Write-capable tools without authentication",
            "description": (
                f"Server has no auth configured but exposes write operations: "
                f"{', '.join(affected)}."
            ),
            "affected_tools": affected,
            "remediation": (
                "Configure Bearer or API Key authentication before deploying "
                "write-capable tools."
            ),
            "references": [
                "https://owasp.org/www-community/controls/Access_Control",
            ],
        },
    ]


def check_untagged_endpoints(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check for endpoints without tags (MEDIUM).

    Returns a single aggregate finding listing all tools that are missing
    tags or have an empty tags list.
    """
    affected: list[str] = []
    for tool in tools:
        tags = tool.get("tags")
        if not tags:
            affected.append(tool.get("name", "unknown"))
    if not affected:
        return []
    return [
        {
            "id": "UNTAGGED_ENDPOINTS",
            "severity": "medium",
            "title": "Endpoints without tags",
            "description": f"Tools missing tags: {', '.join(affected)}.",
            "affected_tools": affected,
            "remediation": "Add descriptive tags to all endpoints for better organization.",
            "references": [
                "https://swagger.io/docs/specification/grouping-operations-with-tags/",
            ],
        },
    ]


def check_deprecated_methods(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check for deprecated HTTP methods TRACE and CONNECT (MEDIUM)."""
    deprecated = {"TRACE", "CONNECT"}
    findings: list[dict[str, Any]] = []
    for tool in tools:
        method = tool.get("method") or tool.get("http_method")
        if method in deprecated:
            tool_name = tool.get("name", "unknown")
            findings.append({
                "id": "DEPRECATED_HTTP_METHODS",
                "severity": "medium",
                "title": "Deprecated HTTP methods",
                "description": (
                    f"Tool '{tool_name}' uses deprecated HTTP method '{method}'."
                ),
                "affected_tools": [tool_name],
                "remediation": (
                    "Replace TRACE/CONNECT methods with standard methods "
                    "(GET, POST, PUT, PATCH, DELETE)."
                ),
                "references": [
                    "https://owasp.org/www-community/attacks/HTTP_Methods",
                ],
            })
    return findings


def check_large_tool_set(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Warn when a server exposes 50 or more tools (INFO).

    Large tool sets can degrade LLM tool-selection accuracy.
    """
    if len(tools) < 50:
        return []
    return [
        {
            "id": "LARGE_TOOL_SET",
            "severity": "info",
            "title": "Large tool set may produce unfocused server",
            "description": (
                f"Server has {len(tools)} tools. Large tool sets may confuse "
                f"LLMs and reduce selection accuracy."
            ),
            "affected_tools": [t.get("name", "unknown") for t in tools],
            "remediation": (
                "Deselect less important tools to keep the set focused "
                "(ideally under 20)."
            ),
            "references": [
                "https://docs.anthropic.com/en/docs/build-with-claude/tool-use",
            ],
        },
    ]


# ── Registry ─────────────────────────────────────────────────────────────────

RULES: list[dict[str, Any]] = [
    {
        "id": "SSRF_URL_PARAM",
        "severity": "critical",
        "title": "Tool accepts URL parameter (SSRF risk)",
        "check": check_ssrf_url_param,
        "requires_auth": False,
    },
    {
        "id": "NO_AUTH_DELETE",
        "severity": "critical",
        "title": "DELETE operation without authentication",
        "check": check_no_auth_delete,
        "requires_auth": True,
    },
    {
        "id": "CREDENTIAL_IN_RESPONSE",
        "severity": "high",
        "title": "Response may include sensitive credentials",
        "check": check_credential_in_response,
        "requires_auth": False,
    },
    {
        "id": "PROMPT_INJECTION_DESC",
        "severity": "high",
        "title": "Tool description may be vulnerable to prompt injection",
        "check": check_prompt_injection_desc,
        "requires_auth": False,
    },
    {
        "id": "NO_AUTH_WRITES",
        "severity": "high",
        "title": "Write-capable tools without authentication",
        "check": check_no_auth_writes,
        "requires_auth": True,
    },
    {
        "id": "UNTAGGED_ENDPOINTS",
        "severity": "medium",
        "title": "Endpoints without tags",
        "check": check_untagged_endpoints,
        "requires_auth": False,
    },
    {
        "id": "DEPRECATED_HTTP_METHODS",
        "severity": "medium",
        "title": "Deprecated HTTP methods",
        "check": check_deprecated_methods,
        "requires_auth": False,
    },
    {
        "id": "LARGE_TOOL_SET",
        "severity": "info",
        "title": "Large tool set may produce unfocused server",
        "check": check_large_tool_set,
        "requires_auth": False,
    },
]
