"""Auth Header Builder — maps an auth scheme and credential to HTTP headers.

The MCP gateway uses this module to attach the correct ``Authorization``
(or custom) header when forwarding requests to the upstream API.
"""

from __future__ import annotations

import base64


class AuthHeaderBuilder:
    """Build HTTP authentication headers from a stored credential.

    Supported schemes:
        - ``none`` / ``""`` : no auth (empty dict)
        - ``api_key``       : ``{<header_name>: <credential_value>}``
        - ``bearer``        : ``{Authorization: Bearer <token>}``
        - ``oauth2``        : ``{Authorization: Bearer <token>}``
        - ``basic``         : ``{Authorization: Basic <base64>}``
        - ``header``        : ``{<header_name>: <credential_value>}``
    """

    def build(
        self,
        auth_scheme: str,
        credential_value: str,
        auth_header_name: str | None = None,
    ) -> dict[str, str]:
        """Build one or more HTTP headers for the given auth scheme.

        Args:
            auth_scheme: The authentication scheme identifier (case-insensitive).
            credential_value: The raw credential value (e.g. API key, token,
                or ``user:pass`` for Basic auth).
            auth_header_name: Optional custom header name used by ``api_key``
                and ``header`` schemes.  Defaults to ``X-API-Key`` and
                ``X-Custom-Header`` respectively.

        Returns:
            A dict of HTTP header name → value pairs (may be empty).
        """
        scheme = auth_scheme.lower().strip() if auth_scheme else "none"

        if scheme in ("none", ""):
            return {}

        if scheme == "api_key":
            header_name = auth_header_name or "X-API-Key"
            return {header_name: credential_value}

        if scheme == "bearer":
            return {"Authorization": f"Bearer {credential_value}"}

        if scheme == "oauth2":
            return {"Authorization": f"Bearer {credential_value}"}

        if scheme == "basic":
            encoded = base64.b64encode(credential_value.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}

        if scheme == "header":
            header_name = auth_header_name or "X-Custom-Header"
            return {header_name: credential_value}

        # Unknown scheme — return no auth headers.
        return {}
