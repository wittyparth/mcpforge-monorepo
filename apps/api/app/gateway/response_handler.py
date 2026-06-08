"""Response handler for MCP gateway — processes upstream HTTP responses into ToolCallResult.

The ResponseHandler takes an ``httpx.Response`` from an upstream API call and converts
it into a structured ``ToolCallResult`` suitable for MCP tool response formatting.
This includes content-type-aware processing (JSON parsing, binary encoding,
HTML stripping), size limit enforcement, and truncation.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.exceptions import UpstreamError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum size of a single tool call response payload (100 KB).
MAX_RESPONSE_SIZE = 100 * 1024

# Maximum upstream response body we are willing to buffer (5 MB).
UPSTREAM_MAX_SIZE = 5 * 1024 * 1024

# Regex for stripping HTML tags.  Kept as a module-level constant so it is
# compiled once rather than on every call.
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class ToolCallResult:
    """Processed upstream response ready for MCP tool call formatting.

    Attributes:
        type: The content type category — ``"json"``, ``"text"``, or ``"binary"``.
        content: The parsed/processed content.  ``dict`` or ``list`` for JSON,
            ``str`` for text/binary.
        mime_type: The original MIME type from the upstream response.
        truncated: Whether the content was truncated due to size limits.
        response_size_bytes: The original response body size in bytes.
        status_code: The HTTP status code from the upstream response.
    """

    type: Literal["json", "text", "binary"]
    content: str | dict[str, object] | list[object]
    status_code: int
    mime_type: str | None = None
    truncated: bool = False
    response_size_bytes: int = 0


class ResponseHandler:
    """Processes upstream HTTP responses into structured ``ToolCallResult`` instances.

    The handler applies content-type-aware processing, size enforcement,
    and error classification.  It is designed to be used by the tool executor
    when converting upstream API responses into MCP tool results.
    """

    async def handle(self, response: httpx.Response) -> ToolCallResult:
        """Process an upstream HTTP response into a ``ToolCallResult``.

        Args:
            response: The ``httpx.Response`` from an upstream API call.

        Returns:
            A ``ToolCallResult`` with content processed according to
            content-type.

        Raises:
            UpstreamError: If the upstream response status is 500 or higher.
        """
        # 1. Upstream server errors (5xx) → raise immediately.
        if response.status_code >= 500:
            logger.warning(
                "upstream server error",
                status_code=response.status_code,
            )
            raise UpstreamError(
                f"Upstream server returned {response.status_code}",
            )

        # 2. Body size enforcement — reject oversized payloads.
        body = response.content
        response_size = len(body)

        content_length_str = response.headers.get("content-length")
        if content_length_str is not None:
            declared_size = int(content_length_str)
            if declared_size > UPSTREAM_MAX_SIZE:
                logger.warning(
                    "upstream response too large (content-length)",
                    declared_size=declared_size,
                    limit=UPSTREAM_MAX_SIZE,
                )
                return ToolCallResult(
                    type="text",
                    content=(
                        f"Upstream response exceeds maximum allowed size "
                        f"of {UPSTREAM_MAX_SIZE} bytes"
                    ),
                    mime_type="text/plain",
                    status_code=response.status_code,
                    response_size_bytes=declared_size,
                )

        if response_size > UPSTREAM_MAX_SIZE:
            logger.warning(
                "upstream response too large (actual)",
                actual_size=response_size,
                limit=UPSTREAM_MAX_SIZE,
            )
            return ToolCallResult(
                type="text",
                content=(
                    f"Upstream response exceeds maximum allowed size "
                    f"of {UPSTREAM_MAX_SIZE} bytes"
                ),
                mime_type="text/plain",
                status_code=response.status_code,
                response_size_bytes=response_size,
            )

        # 3. Determine content type and process accordingly.
        content_type = response.headers.get("content-type", "").lower()

        if "application/json" in content_type or "/json" in content_type:
            return await self._handle_json(body, content_type, response.status_code)

        if (
            "image/" in content_type
            or content_type == "application/pdf"
            or content_type == "application/octet-stream"
        ):
            return await self._handle_binary(body, content_type, response.status_code)

        if "text/html" in content_type or "/html" in content_type:
            return await self._handle_html(body, content_type, response.status_code)

        return await self._handle_text(body, content_type, response.status_code)

    async def _handle_json(
        self,
        body: bytes,
        content_type: str,
        status_code: int,
    ) -> ToolCallResult:
        """Parse JSON body and return as parsed Python object."""
        body_str = body.decode("utf-8", errors="replace")
        response_size = len(body)

        truncated = response_size > MAX_RESPONSE_SIZE
        if truncated:
            body_str = body_str[:MAX_RESPONSE_SIZE]

        try:
            parsed: dict[str, object] | list[object] = json.loads(body_str)
        except json.JSONDecodeError:
            logger.warning("failed to parse JSON response, falling back to text")
            return ToolCallResult(
                type="text",
                content=body_str[:MAX_RESPONSE_SIZE],
                mime_type=content_type or "text/plain",
                truncated=truncated,
                response_size_bytes=response_size,
                status_code=status_code,
            )

        return ToolCallResult(
            type="json",
            content=parsed,
            mime_type=content_type or "application/json",
            truncated=truncated,
            response_size_bytes=response_size,
            status_code=status_code,
        )

    async def _handle_binary(
        self,
        body: bytes,
        content_type: str,
        status_code: int,
    ) -> ToolCallResult:
        """Base64-encode binary body."""
        response_size = len(body)
        truncated = response_size > MAX_RESPONSE_SIZE
        data = body[:MAX_RESPONSE_SIZE] if truncated else body
        encoded = base64.b64encode(data).decode("ascii")

        return ToolCallResult(
            type="binary",
            content=encoded,
            mime_type=content_type or "application/octet-stream",
            truncated=truncated,
            response_size_bytes=response_size,
            status_code=status_code,
        )

    async def _handle_html(
        self,
        body: bytes,
        content_type: str,
        status_code: int,
    ) -> ToolCallResult:
        """Strip HTML tags and return plain text."""
        body_str = body.decode("utf-8", errors="replace")
        response_size = len(body)

        text = _HTML_TAG_RE.sub("", body_str)
        # Collapse multiple whitespace characters for readability.
        text = re.sub(r"\s+", " ", text).strip()

        truncated = len(text) > MAX_RESPONSE_SIZE
        if truncated:
            text = text[:MAX_RESPONSE_SIZE]

        return ToolCallResult(
            type="text",
            content=text,
            mime_type=content_type or "text/html",
            truncated=truncated,
            response_size_bytes=response_size,
            status_code=status_code,
        )

    async def _handle_text(
        self,
        body: bytes,
        content_type: str,
        status_code: int,
    ) -> ToolCallResult:
        """Return body as plain text."""
        body_str = body.decode("utf-8", errors="replace")
        response_size = len(body)
        truncated = response_size > MAX_RESPONSE_SIZE
        if truncated:
            body_str = body_str[:MAX_RESPONSE_SIZE]

        return ToolCallResult(
            type="text",
            content=body_str,
            mime_type=content_type or "text/plain",
            truncated=truncated,
            response_size_bytes=response_size,
            status_code=status_code,
        )
