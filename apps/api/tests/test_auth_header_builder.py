"""Tests for AuthHeaderBuilder (F2 — MCP gateway auth support).

Covers all six auth schemes: ``none``, ``api_key``, ``bearer``,
``oauth2``, ``basic``, and ``header``.
"""

from __future__ import annotations

import base64

from app.gateway.auth_header_builder import AuthHeaderBuilder


def test_none_auth() -> None:
    """``none`` / empty scheme returns an empty dict."""
    builder = AuthHeaderBuilder()

    result = builder.build("none", "some-value")
    assert result == {}

    result = builder.build("", "some-value")
    assert result == {}


def test_api_key_with_default_header() -> None:
    """``api_key`` uses ``X-API-Key`` by default."""
    builder = AuthHeaderBuilder()

    result = builder.build("api_key", "my-secret-key")

    assert result == {"X-API-Key": "my-secret-key"}


def test_api_key_with_custom_header() -> None:
    """``api_key`` respects a custom header name."""
    builder = AuthHeaderBuilder()

    result = builder.build("api_key", "my-secret-key", auth_header_name="X-My-Key")

    assert result == {"X-My-Key": "my-secret-key"}


def test_bearer() -> None:
    """``bearer`` returns ``Authorization: Bearer <token>``."""
    builder = AuthHeaderBuilder()

    result = builder.build("bearer", "tok_abc123")

    assert result == {"Authorization": "Bearer tok_abc123"}


def test_oauth2() -> None:
    """``oauth2`` returns the same header format as ``bearer``."""
    builder = AuthHeaderBuilder()

    result = builder.build("oauth2", "oauth2-token")

    assert result == {"Authorization": "Bearer oauth2-token"}


def test_basic() -> None:
    """``basic`` base64-encodes the credential and returns ``Authorization: Basic …``."""
    builder = AuthHeaderBuilder()
    credential = "admin:secret123"

    result = builder.build("basic", credential)

    expected_value = base64.b64encode(credential.encode()).decode()
    assert result == {"Authorization": f"Basic {expected_value}"}


def test_header_with_default_header() -> None:
    """``header`` uses ``X-Custom-Header`` by default."""
    builder = AuthHeaderBuilder()

    result = builder.build("header", "custom-value")

    assert result == {"X-Custom-Header": "custom-value"}


def test_header_with_custom_header() -> None:
    """``header`` respects a custom header name."""
    builder = AuthHeaderBuilder()

    result = builder.build("header", "custom-value", auth_header_name="X-My-Custom")

    assert result == {"X-My-Custom": "custom-value"}


def test_unknown_scheme() -> None:
    """An unrecognised scheme returns an empty dict."""
    builder = AuthHeaderBuilder()

    result = builder.build("unknown_scheme", "value")

    assert result == {}
