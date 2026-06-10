"""Security Scanner service package (F5).

Deterministic rule-based security analysis of MCP server configurations.
Runs 8 rules against server tool configs and produces structured findings.
"""

from app.services.security_scanner.rules import (
    RULES,
    check_credential_in_response,
    check_deprecated_methods,
    check_large_tool_set,
    check_no_auth_delete,
    check_no_auth_writes,
    check_prompt_injection_desc,
    check_ssrf_url_param,
    check_untagged_endpoints,
)

__all__ = [
    "RULES",
    "check_credential_in_response",
    "check_deprecated_methods",
    "check_large_tool_set",
    "check_no_auth_delete",
    "check_no_auth_writes",
    "check_prompt_injection_desc",
    "check_ssrf_url_param",
    "check_untagged_endpoints",
]
