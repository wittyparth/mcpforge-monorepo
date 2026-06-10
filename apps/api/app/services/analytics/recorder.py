"""Tool call recording service (F6 — Analytics).

Records individual tool call telemetry to the partitioned ``tool_calls`` table.
Never stores parameter values. Sanitizes error messages before persistence.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)

_VALID_STATUSES = frozenset({"success", "error", "timeout"})

# Regex patterns for credential redaction in error messages.
_BEARER_PATTERN = re.compile(r"Bearer [A-Za-z0-9\-._~+/]+=*")
_BASIC_PATTERN = re.compile(r"Basic [A-Za-z0-9+/=]+")
_QUERY_PARAM_PATTERN = re.compile(
    r"(api_key|token|secret|password)=[^\s&]+", re.IGNORECASE
)
_AUTH_HEADER_PATTERN = re.compile(
    r"Authorization:\s+[^\s]+", re.IGNORECASE
)
_JSON_VALUE_PATTERN = re.compile(
    r'"(api_key|password|token|secret)"\s*:\s*"[^"]+"', re.IGNORECASE
)

_REDACTED_STR = "[REDACTED]"

# Maximum length for a stored error message after sanitization.
_MAX_ERROR_LENGTH = 500


class AnalyticsRecorder:
    """Records individual tool call events to the partitioned ``tool_calls`` table.

    This is called by the MCP gateway on every tool invocation. All methods are
    designed to NEVER raise — the gateway must not fail because of analytics.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the recorder with a DB session.

        Args:
            session: An active SQLAlchemy async session.
        """
        self.session = session

    async def record_tool_call(
        self,
        server_id: UUID,
        tool_name: str,
        status: str,
        latency_ms: int | None,
        response_size_bytes: int | None,
        error_type: str | None,
        error_msg: str | None,
        client_name: str | None,
    ) -> None:
        """Record a tool call event.

        Sanitizes and classifies errors before persisting. Never raises on
        DB failure — logs a warning instead.

        Args:
            server_id: The server that handled the call.
            tool_name: Name of the tool that was called.
            status: One of ``'success'``, ``'error'``, ``'timeout'``.
            latency_ms: Call duration in milliseconds, or ``None``.
            response_size_bytes: Size of the response payload, or ``None``.
            error_type: Pre-classified error type. If ``None`` and
                ``error_msg`` is provided, the error is auto-classified.
            error_msg: Raw error message (sanitized before storage).
            client_name: Name of the calling client (e.g. ``'claude-desktop'``).

        Raises:
            ValueError: If ``status`` is not one of the valid values.
        """
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. "
                f"Must be one of: {', '.join(sorted(_VALID_STATUSES))}",
            )

        # Sanitize and classify error.
        safe_error_msg: str | None = None
        resolved_error_type: str | None = error_type
        if error_msg is not None:
            safe_error_msg = self._sanitize_error(error_msg)
            if resolved_error_type is None:
                resolved_error_type = self._classify_error(error_msg)

        now = datetime.now(UTC)
        call_id = uuid4()

        stmt = text("""
            INSERT INTO tool_calls
                (id, server_id, tool_name, status, error_type, error_msg,
                 latency_ms, response_size_bytes, client_name, called_at)
            VALUES
                (:id, :server_id, :tool_name, :status, :error_type, :error_msg,
                 :latency_ms, :response_size_bytes, :client_name, :called_at)
        """)

        try:
            await self.session.execute(
                stmt,
                {
                    "id": call_id,
                    "server_id": server_id,
                    "tool_name": tool_name,
                    "status": status,
                    "error_type": resolved_error_type,
                    "error_msg": safe_error_msg,
                    "latency_ms": latency_ms,
                    "response_size_bytes": response_size_bytes,
                    "client_name": client_name,
                    "called_at": now,
                },
            )
            await self.session.commit()

            logger.info(
                "tool_call_recorded",
                server_id=str(server_id),
                tool=tool_name,
                status=status,
                latency_ms=latency_ms,
            )
        except Exception:
            logger.warning(
                "tool_call_record_failed",
                server_id=str(server_id),
                tool=tool_name,
                status=status,
                latency_ms=latency_ms,
                exc_info=True,
            )
            await self.session.rollback()

    @staticmethod
    def _sanitize_error(error_msg: str) -> str:
        """Strip credentials from an error message.

        Redacts the following patterns:
        - ``Bearer <token>`` → ``Bearer [REDACTED]``
        - ``Basic <credentials>`` → ``Basic [REDACTED]``
        - ``api_key=<value>``, ``token=<value>``, etc.
        - ``Authorization: <value>``
        - JSON-style ``"api_key": "<value>"``, etc.

        Args:
            error_msg: The raw error message.

        Returns:
            Sanitized error message, truncated to ``_MAX_ERROR_LENGTH`` chars.
        """
        sanitized = _BEARER_PATTERN.sub(f"Bearer {_REDACTED_STR}", error_msg)
        sanitized = _BASIC_PATTERN.sub(f"Basic {_REDACTED_STR}", sanitized)
        sanitized = _QUERY_PARAM_PATTERN.sub(r"\1=[REDACTED]", sanitized)
        sanitized = _AUTH_HEADER_PATTERN.sub(
            f"Authorization: {_REDACTED_STR}", sanitized,
        )
        sanitized = _JSON_VALUE_PATTERN.sub(r'"\1": "[REDACTED]"', sanitized)
        return sanitized[:_MAX_ERROR_LENGTH]

    @staticmethod
    def _classify_error(error_msg: str) -> str:
        """Classify an error message into a standard error type.

        Matching is order-sensitive: the first matched pattern wins.

        Args:
            error_msg: The error message to classify.

        Returns:
            One of ``'TimeoutError'``, ``'UpstreamError'``,
            ``'ValidationError'``, ``'SSRFBlocked'``, ``'AuthError'``,
            ``'RateLimitError'``, ``'Other'``.
        """
        msg_lower = error_msg.lower()

        if "timeout" in msg_lower:
            return "TimeoutError"
        if "rate limit" in msg_lower or msg_lower.startswith("429"):
            return "RateLimitError"
        if "ssrf" in msg_lower or "blocked" in msg_lower:
            return "SSRFBlocked"
        if "auth" in msg_lower or "unauthoriz" in msg_lower or "forbidden" in msg_lower:
            return "AuthError"
        if "upstream" in msg_lower or "http 5" in msg_lower:
            return "UpstreamError"
        if "invalid" in msg_lower or "validation" in msg_lower:
            return "ValidationError"

        return "Other"
