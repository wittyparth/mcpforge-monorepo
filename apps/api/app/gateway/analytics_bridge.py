"""Gateway → analytics bridge.

Single entry point the gateway uses to fire-and-forget an analytics
event after every tool call. The Celery task itself is the one that
opens a DB session and writes the row; this wrapper exists so the
gateway code stays clean and we can short-circuit when the broker is
unavailable.

NEVER raise — analytics must not break the MCP tool call path.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def emit_tool_call(
    server_id: str,
    tool_name: str,
    status: str,
    latency_ms: int | None = None,
    response_size_bytes: int | None = None,
    error_type: str | None = None,
    error_msg: str | None = None,
    client_name: str | None = None,
) -> None:
    """Fire-and-forget enqueue a tool-call analytics event.

    Args:
        server_id: UUID of the target server (string).
        tool_name: Name of the tool that was called.
        status: ``'success'``, ``'error'``, or ``'timeout'``.
        latency_ms: Observed call duration in milliseconds.
        response_size_bytes: Size of the upstream response payload.
        error_type: Classified error category (TimeoutError, etc.).
        error_msg: Raw error message; the recorder sanitizes before
            persistence so it's safe to pass user-supplied content.
        client_name: MCP client name (Claude Desktop, Cursor, …) or
            ``None`` when unknown.

    Notes:
        This function is intentionally synchronous and does not
        ``await`` the Celery task. ``.delay()`` returns immediately
        after enqueuing the message; the worker handles the DB write
        asynchronously. If the broker is unreachable, the exception
        is swallowed and a warning is logged.
    """
    try:
        from app.services.analytics.tasks import record_tool_call

        record_tool_call.delay(
            server_id=server_id,
            tool_name=tool_name,
            status=status,
            latency_ms=latency_ms,
            response_size_bytes=response_size_bytes,
            error_type=error_type,
            error_msg=error_msg,
            client_name=client_name,
        )
    except Exception as exc:  # noqa: BLE001 — intentional broad catch
        # The gateway MUST not fail because of analytics. Log and move on.
        logger.warning(
            "analytics_emit_failed",
            server_id=server_id,
            tool=tool_name,
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )


def classify_dispatch_status(result: dict[str, Any] | None) -> tuple[str, str | None, str | None]:
    """Translate a ToolDispatcher result into analytics status fields.

    Args:
        result: The ``content``/``isError`` dict returned by
            ``ToolDispatcher.dispatch``, or ``None`` if the dispatcher
            raised before producing a result.

    Returns:
        ``(status, error_type, error_msg)`` ready to pass to
        :func:`emit_tool_call`.
    """
    if result is None:
        return ("error", "UpstreamError", "Tool dispatch failed before producing a result")

    is_error = bool(result.get("isError"))
    if not is_error:
        return ("success", None, None)

    # Find the upstream error message in the content list.
    error_msg: str | None = None
    for block in result.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            text_block = str(block.get("text", ""))
            if text_block:
                error_msg = text_block
                break

    if error_msg and "HTTP 5" in error_msg:
        return ("error", "UpstreamError", error_msg)
    if error_msg and "timed out" in error_msg.lower():
        return ("timeout", "TimeoutError", error_msg)
    if error_msg:
        return ("error", "Other", error_msg)
    return ("error", "Other", "Tool returned isError without a message")
