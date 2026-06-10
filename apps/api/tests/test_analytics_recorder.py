"""Tests for AnalyticsRecorder (F6 — Usage Analytics).

12 tests covering:
  - 5 sanitize-error pure-function tests
  - 2 classify-error pure-function tests
  - 1 invalid status raises ValueError
  - 1 record writes row to tool_calls
  - 1 record never raises on DB failure (missing table)
  - 1 record stores sanitized error message
  - 1 record auto-classifies error when no error_type given
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_server import MCPServer
from app.models.user import User
from app.services.analytics.recorder import AnalyticsRecorder

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_test_user_and_server(
    session: AsyncSession,
) -> tuple[User, MCPServer]:
    """Create a minimal user + server pair."""
    user = User(
        email=f"rec-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
    )
    session.add(user)
    await session.flush()
    server = MCPServer(
        user_id=user.id,
        slug=f"rec-slug-{uuid.uuid4().hex[:8]}",
        name="Recorder Test Server",
        base_url="https://example.com",
    )
    session.add(server)
    await session.flush()
    return user, server


# ── Sanitize error (pure function) ────────────────────────────────────────────


class TestSanitizeError:
    """AnalyticsRecorder._sanitize_error — credential redaction."""

    def test_sanitize_bearer_token(self) -> None:
        """Bearer token is redacted."""
        msg = "Error: Bearer abc123def456xyz789"
        result = AnalyticsRecorder._sanitize_error(msg)
        assert "Bearer [REDACTED]" in result
        assert "abc123def456xyz789" not in result

    def test_sanitize_basic_auth(self) -> None:
        """Basic auth credentials are redacted."""
        msg = "Error: Basic dXNlcjpwYXNz"
        result = AnalyticsRecorder._sanitize_error(msg)
        assert "Basic [REDACTED]" in result
        assert "dXNlcjpwYXNz" not in result

    def test_sanitize_query_param_api_key(self) -> None:
        """Query-string api_key/token/secret/password are redacted."""
        msg = "https://api.example.com?api_key=secret123&foo=bar"
        result = AnalyticsRecorder._sanitize_error(msg)
        assert "api_key=[REDACTED]" in result
        assert "secret123" not in result

    def test_sanitize_authorization_header(self) -> None:
        """Authorization header value is redacted."""
        msg = "Header: Authorization: Bearer xyz789"
        result = AnalyticsRecorder._sanitize_error(msg)
        # The pattern matches 'Authorization: <value>'
        assert "Authorization: [REDACTED]" in result
        assert "Bearer xyz789" not in result

    def test_sanitize_json_value(self) -> None:
        """JSON-style key-value pairs are redacted."""
        msg = '{"api_key": "super-secret", "password": "hunter2"}'
        result = AnalyticsRecorder._sanitize_error(msg)
        assert '"api_key": "[REDACTED]"' in result
        assert '"password": "[REDACTED]"' in result
        assert "super-secret" not in result
        assert "hunter2" not in result

    def test_sanitize_truncates_long(self) -> None:
        """Error messages longer than 500 chars are truncated."""
        long_msg = "x" * 1000
        result = AnalyticsRecorder._sanitize_error(long_msg)
        assert len(result) <= 500

    def test_sanitize_handles_empty_string(self) -> None:
        """Empty string is handled without error."""
        result = AnalyticsRecorder._sanitize_error("")
        assert result == ""


# ── Classify error (pure function) ────────────────────────────────────────────


class TestClassifyError:
    """AnalyticsRecorder._classify_error — error type detection."""

    def test_classify_timeout(self) -> None:
        """Message with 'timeout' → TimeoutError."""
        assert AnalyticsRecorder._classify_error("connection timeout") == "TimeoutError"
        assert AnalyticsRecorder._classify_error("TIMEOUT") == "TimeoutError"

    def test_classify_rate_limit(self) -> None:
        """Message with 'rate limit' or starting with '429' → RateLimitError."""
        assert AnalyticsRecorder._classify_error("rate limit exceeded") == "RateLimitError"
        assert AnalyticsRecorder._classify_error("429 Too Many Requests") == "RateLimitError"

    def test_classify_auth(self) -> None:
        """Message with 'auth'/'unauthorized'/'forbidden' → AuthError."""
        assert AnalyticsRecorder._classify_error("authentication failed") == "AuthError"
        assert AnalyticsRecorder._classify_error("Unauthorized") == "AuthError"
        assert AnalyticsRecorder._classify_error("forbidden access") == "AuthError"

    def test_classify_ssrf(self) -> None:
        """Message with 'ssrf' or 'blocked' → SSRFBlocked."""
        assert AnalyticsRecorder._classify_error("SSRF detected") == "SSRFBlocked"
        assert AnalyticsRecorder._classify_error("request blocked") == "SSRFBlocked"

    def test_classify_upstream(self) -> None:
        """Message with 'upstream' or 'http 5' → UpstreamError."""
        assert AnalyticsRecorder._classify_error("upstream error") == "UpstreamError"
        assert AnalyticsRecorder._classify_error("HTTP 502") == "UpstreamError"

    def test_classify_validation(self) -> None:
        """Message with 'invalid' or 'validation' → ValidationError."""
        assert AnalyticsRecorder._classify_error("invalid input") == "ValidationError"
        assert AnalyticsRecorder._classify_error("validation failed") == "ValidationError"

    def test_classify_other(self) -> None:
        """Non-matching message → Other."""
        assert AnalyticsRecorder._classify_error("something unexpected happened") == "Other"


# ── Record tool call (DB integration) ─────────────────────────────────────────


class TestRecordToolCall:
    """AnalyticsRecorder.record_tool_call — DB write behaviour."""

    async def test_record_writes_row(
        self,
        test_session: AsyncSession,
    ) -> None:
        """record_tool_call inserts a row into tool_calls."""
        user, server = await _create_test_user_and_server(test_session)

        recorder = AnalyticsRecorder(test_session)
        await recorder.record_tool_call(
            server_id=server.id,
            tool_name="test_tool",
            status="success",
            latency_ms=100,
            response_size_bytes=1024,
            error_type=None,
            error_msg=None,
            client_name="test-client",
        )

        result = await test_session.execute(
            text("SELECT COUNT(*) FROM tool_calls"),
        )
        assert result.scalar() == 1

        row = (await test_session.execute(
            text("SELECT tool_name, status, latency_ms, response_size_bytes,"
                 " client_name FROM tool_calls"),
        )).one()
        assert row.tool_name == "test_tool"
        assert row.status == "success"
        assert row.latency_ms == 100
        assert row.response_size_bytes == 1024
        assert row.client_name == "test-client"

    async def test_record_stores_sanitized_error(
        self,
        test_session: AsyncSession,
    ) -> None:
        """Error message is sanitized before storage."""
        user, server = await _create_test_user_and_server(test_session)

        recorder = AnalyticsRecorder(test_session)
        await recorder.record_tool_call(
            server_id=server.id,
            tool_name="tool_with_err",
            status="error",
            latency_ms=50,
            response_size_bytes=None,
            error_type=None,
            error_msg="Bearer tokensecret",
            client_name="test-client",
        )

        row = (await test_session.execute(
            text("SELECT error_msg, error_type FROM tool_calls WHERE tool_name = 'tool_with_err'"),
        )).one()
        assert "Bearer [REDACTED]" in row.error_msg
        assert "tokensecret" not in row.error_msg

    async def test_record_auto_classifies_error(
        self,
        test_session: AsyncSession,
    ) -> None:
        """When error_type is None, error is auto-classified from message."""
        user, server = await _create_test_user_and_server(test_session)

        recorder = AnalyticsRecorder(test_session)
        await recorder.record_tool_call(
            server_id=server.id,
            tool_name="timeout_tool",
            status="error",
            latency_ms=None,
            response_size_bytes=None,
            error_type=None,
            error_msg="connection timeout after 30s",
            client_name="test-client",
        )

        row = (await test_session.execute(
            text("SELECT error_type, error_msg FROM tool_calls WHERE tool_name = 'timeout_tool'"),
        )).one()
        assert row.error_type == "TimeoutError"

    async def test_record_preserves_explicit_error_type(
        self,
        test_session: AsyncSession,
    ) -> None:
        """When error_type is provided, it is not overwritten by auto-classify."""
        user, server = await _create_test_user_and_server(test_session)

        recorder = AnalyticsRecorder(test_session)
        await recorder.record_tool_call(
            server_id=server.id,
            tool_name="custom_err",
            status="error",
            latency_ms=None,
            response_size_bytes=None,
            error_type="CustomError",
            error_msg="connection timeout",
            client_name="test-client",
        )

        row = (await test_session.execute(
            text("SELECT error_type FROM tool_calls WHERE tool_name = 'custom_err'"),
        )).one()
        assert row.error_type == "CustomError"

    async def test_record_never_raises_on_missing_table(
        self,
        test_session: AsyncSession,
    ) -> None:
        """record_tool_call never raises when the tool_calls table does not exist."""
        # Drop the tool_calls table to simulate DB failure.
        # CASCADE is PostgreSQL-only; SQLite doesn't need it for DROP TABLE.
        await test_session.execute(text("DROP TABLE IF EXISTS tool_calls"))
        await test_session.commit()

        recorder = AnalyticsRecorder(test_session)
        # Should not raise despite missing table.
        await recorder.record_tool_call(
            server_id=uuid.uuid4(),
            tool_name="broken_tool",
            status="error",
            latency_ms=None,
            response_size_bytes=None,
            error_type=None,
            error_msg="something broke",
            client_name="test-client",
        )
        # No assertion needed — we just verify no exception was raised.

    async def test_record_invalid_status_raises(
        self,
        test_session: AsyncSession,
    ) -> None:
        """record_tool_call raises ValueError for invalid status."""
        user, server = await _create_test_user_and_server(test_session)

        recorder = AnalyticsRecorder(test_session)
        with pytest.raises(ValueError, match="Invalid status"):
            await recorder.record_tool_call(
                server_id=server.id,
                tool_name="bad",
                status="unknown_status",
                latency_ms=None,
                response_size_bytes=None,
                error_type=None,
                error_msg=None,
                client_name=None,
            )
