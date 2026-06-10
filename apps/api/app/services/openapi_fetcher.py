"""OpenAPI spec fetching, parsing, validation, and storage service (F1).

This service is the entry point for all OpenAPI ingestion. It handles:

- Fetching from remote URLs with SSRF protection
- Uploading from local file content
- Parsing JSON/YAML content
- Validating against OpenAPI 3.0+ schema
- De-duplicating by SHA-256 hash
- Storing in S3 and persisting metadata in Postgres
- Delegating to SpecAnalyzer for tool extraction
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import time
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

import httpx
import yaml
from openapi_spec_validator import validate as openapi_validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

from app.core.config import settings
from app.core.exceptions import (
    FetchTimeoutError,
    InvalidURLError,
    SpecParseError,
    SpecTooLargeError,
    SpecValidationError,
    UnsupportedSpecVersionError,
    UpstreamError,
)
from app.core.logging import get_logger
from app.core.s3_client import S3Client
from app.repositories.spec_repo import SpecRepository
from app.schemas.openapi_spec import SpecUploadResponse, ToolDefinition

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class SpecAnalyzer(Protocol):
    """Protocol for SpecAnalyzer (defined by the F1 spec_analyzer agent).

    This forward declaration allows OpenAPIFetcher to be implemented and
    tested in parallel with the real SpecAnalyzer. The real implementation
    will duck-type match this protocol.

    The ``extract_tools`` method accepts a parsed OpenAPI dict and returns
    a list of ``ToolDefinition`` instances.
    """

    async def extract_tools(self, spec_dict: dict[str, Any]) -> list[ToolDefinition]:
        """Extract MCP tool definitions from a parsed OpenAPI spec.

        Args:
            spec_dict: The fully parsed and validated OpenAPI specification.

        Returns:
            A list of ``ToolDefinition`` objects, one per HTTP operation.
        """
        ...


class OpenAPIFetcher:
    """Fetches OpenAPI specs from URLs or bytes, validates, stores, and analyzes them.

    Constructor receives all dependencies explicitly — no hidden imports or
    singletons.

    Attributes:
        s3: Client for AWS S3 object storage.
        repo: Repository for spec metadata persistence.
        analyzer: SpecAnalyzer-compatible instance for tool extraction.
        max_size: Maximum allowed spec size in bytes (from settings).
        timeout: Maximum fetch timeout in seconds (from settings).
    """

    def __init__(
        self,
        s3: S3Client,
        spec_repo: SpecRepository,
        analyzer: SpecAnalyzer,
    ) -> None:
        """Initialize the fetcher with all dependencies.

        Args:
            s3: Configured S3 client instance.
            spec_repo: Spec source repository for DB operations.
            analyzer: SpecAnalyzer for extracting tool definitions.
        """
        self.s3 = s3
        self.repo = spec_repo
        self.analyzer = analyzer
        self.max_size = settings.MAX_SPEC_SIZE_BYTES
        self.timeout = settings.MAX_SPEC_FETCH_TIMEOUT_SECONDS

    async def fetch_from_url(
        self,
        user_id: UUID,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> SpecUploadResponse:
        """Fetch an OpenAPI spec from a public URL.

        The full pipeline:
            1. SSRF prevention (private IPs, loopback, link-local rejected)
            2. HTTP GET with timeout and redirect following
            3. Content size check against ``MAX_SPEC_SIZE_BYTES``
            4. Parse (JSON/YAML auto-detect) and validate against schema
            5. SHA-256 dedup across the same user's specs
            6. Store in S3 (unless dedup hit)
            7. Persist metadata in Postgres
            8. Delegate to ``SpecAnalyzer.extract_tools()``

        Args:
            user_id: The authenticated user's UUID.
            url: The full URL to the OpenAPI spec.
            headers: Optional HTTP headers to send (e.g. ``Authorization``).

        Returns:
            A ``SpecUploadResponse`` with parsed metadata and tool list.

        Raises:
            InvalidURLError: URL scheme is not http/https, hostname resolves
                to a private/loopback/link-local IP, or is unresolvable.
            FetchTimeoutError: The HTTP request exceeded the configured timeout.
            UpstreamError: The upstream server returned 4xx or 5xx.
            SpecTooLargeError: The response body exceeds ``MAX_SPEC_SIZE_BYTES``.
            SpecParseError: The content is not valid JSON or YAML.
            SpecValidationError: The parsed spec fails OpenAPI schema validation.
            UnsupportedSpecVersionError: The spec's ``openapi`` field does not
                start with ``"3."`` (e.g. Swagger 2.0).
        """
        logger.info("spec_fetch_started", url=url, user_id=str(user_id))
        start = time.monotonic()

        # 1. SSRF prevention — reject private / loopback / link-local IPs
        self._validate_url(url)

        # 2. Fetch with timeout and redirect following
        fetch_headers = headers or {}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url, headers=fetch_headers)
        except httpx.TimeoutException:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.warning(
                "spec_fetch_failed",
                url=url,
                error_code="FETCH_TIMEOUT",
                duration_ms=elapsed,
            )
            raise FetchTimeoutError(
                f"Spec fetch exceeded {self.timeout}s timeout",
            ) from None

        # 3. Reject non-success HTTP status codes
        if response.status_code >= 400:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.warning(
                "spec_fetch_failed",
                url=url,
                error_code="UPSTREAM_ERROR",
                status_code=response.status_code,
                duration_ms=elapsed,
            )
            raise UpstreamError(
                f"Upstream returned HTTP {response.status_code} for {url}",
            )

        content = response.content
        logger.info(
            "spec_fetch_debug",
            url=url,
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            content_length=len(content),
            content_preview=content[:200].decode("utf-8", errors="replace"),
        )

        # 4. Size check
        if len(content) > self.max_size:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.warning(
                "spec_fetch_failed",
                url=url,
                error_code="TOO_LARGE",
                size_bytes=len(content),
                max_bytes=self.max_size,
                duration_ms=elapsed,
            )
            raise SpecTooLargeError(
                f"Spec is {len(content)} bytes, max is {self.max_size} bytes",
            )

        # 5. Parse + validate
        content_type = response.headers.get("content-type")
        spec_dict = self._parse_content(content, content_type)

        # 6. Hash for dedup
        sha = hashlib.sha256(content).hexdigest()

        # 7. Check for existing spec with same hash
        existing = await self.repo.get_by_user_and_hash(user_id, sha)
        if existing is not None:
            return await self._handle_dedup(existing, content, url, start)

        # 8. Count endpoints
        endpoint_count = self._count_endpoints(spec_dict)

        # 9. Store in S3
        r2_key = f"{user_id}/{sha}.json"
        await self.s3.put_object(r2_key, json.dumps(spec_dict, indent=2).encode("utf-8"))

        # 10. Persist metadata
        spec = await self.repo.create(
            user_id=user_id,
            source_type="url",
            source_url=url,
            r2_key=r2_key,
            title=spec_dict.get("info", {}).get("title", "Untitled"),
            version=spec_dict.get("info", {}).get("version"),
            openapi_version=spec_dict.get("openapi", "unknown"),
            endpoint_count=endpoint_count,
            spec_size_bytes=len(content),
        )

        # 11. Mark as successfully fetched
        await self.repo.update_status(spec, "fetched")

        # 12. Extract tools via SpecAnalyzer
        tools = await self.analyzer.extract_tools(spec_dict)

        elapsed = int((time.monotonic() - start) * 1000)
        logger.info(
            "spec_fetch_succeeded",
            url=url,
            spec_id=str(spec.id),
            dedup=False,
            size_bytes=len(content),
            endpoint_count=endpoint_count,
            duration_ms=elapsed,
        )

        return SpecUploadResponse(
            spec_id=spec.id,
            title=spec.title,
            version=spec.version,
            openapi_version=spec.openapi_version,
            endpoint_count=endpoint_count,
            spec_size_bytes=len(content),
            tools=tools,
        )

    async def upload(
        self,
        user_id: UUID,
        file_content: bytes,
        filename: str,
    ) -> SpecUploadResponse:
        """Parse and store an uploaded OpenAPI spec file.

        Follows the same pipeline as ``fetch_from_url`` except the content
        is provided directly as bytes rather than fetched over HTTP. SSRF
        prevention does not apply.

        Args:
            user_id: The authenticated user's UUID.
            file_content: Raw bytes of the spec file.
            filename: Original filename (used for content-type detection).

        Returns:
            A ``SpecUploadResponse`` with parsed metadata and tool list.

        Raises:
            SpecTooLargeError: The file exceeds ``MAX_SPEC_SIZE_BYTES``.
            SpecParseError: The content is not valid JSON or YAML.
            SpecValidationError: The parsed spec fails OpenAPI schema validation.
            UnsupportedSpecVersionError: The spec's ``openapi`` field does not
                start with ``"3."``.
        """
        logger.info("spec_upload_started", filename=filename, user_id=str(user_id))
        start = time.monotonic()

        # 1. Size check
        if len(file_content) > self.max_size:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.warning(
                "spec_upload_failed",
                filename=filename,
                error_code="TOO_LARGE",
                size_bytes=len(file_content),
                max_bytes=self.max_size,
                duration_ms=elapsed,
            )
            raise SpecTooLargeError(
                f"Spec is {len(file_content)} bytes, max is {self.max_size} bytes",
            )

        # 2. Detect content type from filename extension
        content_type = self._detect_content_type(filename)

        # 3. Parse + validate
        spec_dict = self._parse_content(file_content, content_type)

        # 4. Hash for dedup
        sha = hashlib.sha256(file_content).hexdigest()

        # 5. Check for existing spec with same hash
        existing = await self.repo.get_by_user_and_hash(user_id, sha)
        if existing is not None:
            return await self._handle_dedup(
                existing, file_content, filename, start,
            )

        # 6. Count endpoints
        endpoint_count = self._count_endpoints(spec_dict)

        # 7. Store in S3
        r2_key = f"{user_id}/{sha}.json"
        await self.s3.put_object(r2_key, json.dumps(spec_dict, indent=2).encode("utf-8"))

        # 8. Persist metadata
        spec = await self.repo.create(
            user_id=user_id,
            source_type="upload",
            source_url=filename,
            r2_key=r2_key,
            title=spec_dict.get("info", {}).get("title", "Untitled"),
            version=spec_dict.get("info", {}).get("version"),
            openapi_version=spec_dict.get("openapi", "unknown"),
            endpoint_count=endpoint_count,
            spec_size_bytes=len(file_content),
        )

        # 9. Mark as successfully fetched
        await self.repo.update_status(spec, "fetched")

        # 10. Extract tools via SpecAnalyzer
        tools = await self.analyzer.extract_tools(spec_dict)

        elapsed = int((time.monotonic() - start) * 1000)
        logger.info(
            "spec_upload_succeeded",
            filename=filename,
            spec_id=str(spec.id),
            dedup=False,
            size_bytes=len(file_content),
            endpoint_count=endpoint_count,
            duration_ms=elapsed,
        )

        return SpecUploadResponse(
            spec_id=spec.id,
            title=spec.title,
            version=spec.version,
            openapi_version=spec.openapi_version,
            endpoint_count=endpoint_count,
            spec_size_bytes=len(file_content),
            tools=tools,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    async def _handle_dedup(
        self,
        existing: Any,  # SpecSource — avoid runtime import
        content: bytes,
        source_identifier: str,
        start: float,
    ) -> SpecUploadResponse:
        """Handle a dedup hit: re-analyse existing S3 content.

        Does NOT store the spec again. Fetches the original bytes from S3,
        re-parses, and re-extracts tools.

        Args:
            existing: Existing ``SpecSource`` DB row.
            content: The raw bytes (for size reporting).
            source_identifier: URL or filename (for logging).
            start: ``time.monotonic()`` from the caller.

        Returns:
            A ``SpecUploadResponse`` built from the existing record.
        """
        existing_content = await self.s3.get_object(existing.r2_key)
        if not existing_content:
            stripped = content.lstrip(b" \t\n\r\xef\xbb\xbf")
            content_type = "application/json" if stripped[:1] == b"{" else "application/x-yaml"
            existing_spec = self._parse_content(content, content_type)
            existing_content = json.dumps(existing_spec, indent=2).encode("utf-8")
            await self.s3.put_object(existing.r2_key, existing_content)
        else:
            existing_spec = self._parse_content(existing_content, "application/json")
        tools = await self.analyzer.extract_tools(existing_spec)
        elapsed = int((time.monotonic() - start) * 1000)
        logger.info(
            "spec_fetch_succeeded",
            url=source_identifier,
            spec_id=str(existing.id),
            dedup=True,
            size_bytes=len(content),
            endpoint_count=existing.endpoint_count or len(tools),
            duration_ms=elapsed,
        )
        return SpecUploadResponse(
            spec_id=existing.id,
            title=existing.title,
            version=existing.version,
            openapi_version=existing.openapi_version,
            endpoint_count=existing.endpoint_count or len(tools),
            spec_size_bytes=existing.spec_size_bytes or len(content),
            tools=tools,
        )

    def _validate_url(self, url: str) -> None:
        """Validate a URL for SSRF prevention.

        Checks performed:
            1. Scheme must be ``http`` or ``https``.
            2. Hostname must resolve to an IP address.
            3. Resolved IP must not be private, loopback, or link-local.

        Raises:
            InvalidURLError: On any check failure, with a human-readable
                suggestion.
        """
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise InvalidURLError(
                f"URL scheme '{parsed.scheme}' is not allowed. "
                "Only http and https are supported.",
                suggestion="Use a publicly accessible http/https URL.",
            )

        hostname = parsed.hostname
        if not hostname:
            raise InvalidURLError(
                "URL has no hostname.",
                suggestion="Provide a URL with a valid hostname.",
            )

        try:
            ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            raise InvalidURLError(
                f"Could not resolve hostname '{hostname}'.",
                suggestion="Check that the hostname is correct and "
                "publicly resolvable.",
            ) from None

        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            raise InvalidURLError(
                f"Could not parse resolved IP '{ip}'.",
                suggestion="The hostname resolved to an invalid IP address.",
            ) from None

        if addr.is_private or addr.is_loopback or addr.is_link_local:
            raise InvalidURLError(
                f"URL resolves to a private/internal IP ({ip}). "
                "SSRF prevention blocked this request.",
                suggestion="Use a publicly accessible URL. If you need to "
                "access an internal API, deploy the MCP server in your "
                "own infrastructure.",
            )

    def _parse_content(
        self,
        content: bytes,
        content_type: str | None,
    ) -> dict[str, Any]:
        """Parse raw bytes into a Python dict, auto-detecting JSON vs YAML.

        Detection logic:
            - If ``content_type`` contains ``"json"`` → JSON.
            - Else if the first non-whitespace byte is ``b"{"`` → JSON.
            - Otherwise → YAML (safe-load only).

        After parsing, the spec is validated against the OpenAPI 3.0+
        schema and the ``openapi`` version field is checked.

        Args:
            content: Raw bytes of the spec file.
            content_type: HTTP ``Content-Type`` header value, if any.

        Returns:
            The parsed spec as a Python dict.

        Raises:
            SpecParseError: Content is not valid JSON or YAML.
            SpecValidationError: Parsed spec fails OpenAPI schema validation.
            UnsupportedSpecVersionError: Spec version is not OpenAPI 3.0+.
        """
        # Detect JSON vs YAML
        stripped = content.lstrip(b" \t\n\r\xef\xbb\xbf")
        is_json = (content_type is not None and "json" in content_type.lower()) or (
            stripped[:1] == b"{"
        )

        try:
            if is_json:
                spec_dict: dict[str, Any] = json.loads(content)
            else:
                loaded = yaml.safe_load(content)
                if loaded is None:
                    raise SpecParseError(
                        "YAML content is empty or null",
                        line=1,
                        column=1,
                    )
                if not isinstance(loaded, dict):
                    raise SpecParseError(
                        "YAML content is not a mapping (expected a dict)",
                        line=1,
                        column=1,
                    )
                spec_dict = loaded
        except json.JSONDecodeError as e:
            raise SpecParseError(
                str(e),
                line=e.lineno,
                column=e.colno,
            ) from e
        except yaml.YAMLError as e:
            line: int | None = None
            column: int | None = None
            if hasattr(e, "problem_mark") and e.problem_mark is not None:
                line = e.problem_mark.line + 1
                column = e.problem_mark.column + 1
            raise SpecParseError(
                str(e),
                line=line,
                column=column,
            ) from e

        # Validate against OpenAPI schema
        try:
            openapi_validate(spec_dict)
        except OpenAPIValidationError as e:
            details: list[dict[str, str]] = [
                {
                    "path": ".".join(str(p) for p in e.absolute_path)
                    if e.absolute_path
                    else "",
                    "message": e.message,
                },
            ]
            raise SpecValidationError(
                "OpenAPI spec validation failed",
                details=details,
            ) from e

        # Version check — must be OpenAPI 3.x
        openapi_version = spec_dict.get("openapi", "")
        if not isinstance(openapi_version, str) or not openapi_version.startswith("3."):
            raise UnsupportedSpecVersionError(
                f"Only OpenAPI 3.0+ is supported. Got: {openapi_version}",
                suggestion="Convert Swagger 2.0 to OpenAPI 3.0 using "
                "swagger2openapi",
            )

        return spec_dict

    def _count_endpoints(self, spec_dict: dict[str, Any]) -> int:
        """Count the number of HTTP operations in the spec.

        Iterates over all paths and methods, counting each valid HTTP
        method (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS) as one
        endpoint.

        Args:
            spec_dict: A parsed OpenAPI spec.

        Returns:
            The total number of operations.
        """
        count = 0
        paths = spec_dict.get("paths", {})
        if not isinstance(paths, dict):
            return 0
        http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue
            for method in path_item:
                if method.lower() in http_methods:
                    count += 1
        return count

    def _detect_content_type(self, filename: str) -> str:
        """Detect the MIME content type from a filename extension.

        Args:
            filename: The original filename (e.g. ``"spec.json"``).

        Returns:
            A MIME content-type string appropriate for the extension.
        """
        lower = filename.lower()
        if lower.endswith(".json"):
            return "application/json"
        if lower.endswith((".yaml", ".yml")):
            return "application/x-yaml"
        return "application/octet-stream"
