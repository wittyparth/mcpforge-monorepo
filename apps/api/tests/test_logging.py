"""Tests for the strip_sensitive structlog processor.

These tests assert that the processor:
- Redacts any key whose name contains a sensitive substring.
- Redacts any string value whose CONTENT contains a sensitive substring
  (e.g., a token accidentally embedded in a URL).
- Recurses into nested dicts and lists.
- Passes non-sensitive data through unchanged.
"""

from __future__ import annotations

import pytest

from app.core.logging import strip_sensitive_processor


def _process(event_dict: dict) -> dict:
    """Run the processor with no-op logger/method args."""
    return strip_sensitive_processor(None, None, dict(event_dict))


class TestKeyRedaction:
    @pytest.mark.parametrize(
        "key",
        [
            "authorization",
            "Authorization",
            "AUTHORIZATION",
            "x-api-key",
            "password",
            "passwd",
            "secret",
            "token",
            "cookie",
            "set-cookie",
            "bearer",
            "credential",
            "private_key",
        ],
    )
    def test_sensitive_key_is_redacted(self, key: str) -> None:
        result = _process({key: "supersecret-value-12345"})
        assert result[key] == "[REDACTED]"


class TestNonSensitiveKey:
    def test_normal_key_passes_through(self) -> None:
        result = _process({"user_id": "abc-123", "email": "x@y.com"})
        assert result == {"user_id": "abc-123", "email": "x@y.com"}


class TestStringValueRedaction:
    def test_bearer_token_in_string_is_redacted(self) -> None:
        result = _process({"url": "https://api.example.com?bearer=eyJabc"})
        # The url value contains the substring "bearer" → redacted.
        assert result["url"] == "[REDACTED]"

    def test_normal_url_passes_through(self) -> None:
        result = _process({"url": "https://api.example.com/users/42"})
        assert result["url"] == "https://api.example.com/users/42"


class TestNestedStructures:
    def test_nested_dict_is_processed(self) -> None:
        result = _process({"meta": {"password": "p", "ok": "v"}})
        assert result["meta"]["password"] == "[REDACTED]"
        assert result["meta"]["ok"] == "v"

    def test_list_of_dicts_is_processed(self) -> None:
        result = _process(
            {"items": [{"secret": "s1", "name": "n1"}, {"secret": "s2", "name": "n2"}]}
        )
        assert result["items"][0]["secret"] == "[REDACTED]"
        assert result["items"][0]["name"] == "n1"
        assert result["items"][1]["secret"] == "[REDACTED]"
        assert result["items"][1]["name"] == "n2"

    def test_non_string_values_pass_through(self) -> None:
        result = _process({"count": 42, "ratio": 0.5, "flag": True})
        assert result == {"count": 42, "ratio": 0.5, "flag": True}


class TestCredentialsNotInLogs:
    def test_authorization_header_value_redacted(self) -> None:
        """A real-world test: a log record with an Authorization header
        must NEVER contain the token in the output."""
        log_record = {
            "request_id": "550e8400-e29b-41d4",
            "headers": {
                "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                "Content-Type": "application/json",
            },
        }
        result = _process(log_record)
        # The whole key gets redacted, not just the value.
        assert result["headers"]["Authorization"] == "[REDACTED]"
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in str(result)
