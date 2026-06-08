"""OpenAPI spec ingestion endpoints (F1).

Six endpoints for the OpenAPI ingestion flow:
- POST /specs/fetch          — Fetch a spec from a URL
- POST /specs/upload         — Upload a spec file (multipart)
- GET  /specs/{spec_id}/tools — Get parsed tool list
- POST /specs/{spec_id}/select-tools — Select tools and create an MCP server
- GET  /specs/{spec_id}      — Get spec metadata
- DELETE /specs/{spec_id}    — Delete a spec
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ForbiddenError, NotFoundError, UpstreamError
from app.core.logging import get_logger
from app.core.r2_client import R2Client
from app.models.user import User
from app.repositories.spec_repo import SpecRepository
from app.schemas.mcp_server import MCPServerResponse, ToolSelectionRequest
from app.schemas.openapi_spec import (
    SpecFetchRequest,
    SpecSourceResponse,
    SpecToolListResponse,
    SpecUploadResponse,
    ToolDefinition,
)
from app.services.mcp_server_service import MCPServerService
from app.services.openapi_fetcher import OpenAPIFetcher
from app.services.spec_analyzer import SpecAnalyzer
from app.services.tool_generator import ToolGenerator

logger = get_logger(__name__)

router = APIRouter(prefix="/specs", tags=["specs"])


class _AsyncSpecAnalyzer:
    """Adapter: wraps sync SpecAnalyzer to match the async Protocol.

    The ``OpenAPIFetcher`` constructor is typed with a ``SpecAnalyzer``
    Protocol that declares ``async def extract_tools``.  The real
    ``SpecAnalyzer`` from ``app.services.spec_analyzer`` is synchronous, so
    this adapter wraps each call in an async shim.
    """

    def __init__(self) -> None:
        self._inner = SpecAnalyzer()

    async def extract_tools(self, spec_dict: dict[str, Any]) -> list[ToolDefinition]:
        """Async wrapper around the sync ``SpecAnalyzer.extract_tools``."""
        return self._inner.extract_tools(spec_dict)


class _NoopR2Client:
    """In-memory R2 client for development without R2 infrastructure.

    Stores spec content in a process-local dict so tools, select-tools,
    and delete operations all work correctly during development.
    Data is lost on restart — acceptable for dev mode.
    """

    is_configured: bool = False
    _store: dict[str, bytes] = {}

    async def put_object(self, key: str, body: bytes) -> None:
        self._store[key] = body
        logger.info("r2_dev_stored", key=key, bytes=len(body))

    async def get_object(self, key: str) -> bytes:
        content = self._store.get(key)
        if content is None:
            logger.warning("r2_dev_miss", key=key)
        return content or b""

    async def delete_object(self, key: str) -> None:
        self._store.pop(key, None)
        logger.info("r2_dev_deleted", key=key)


def _build_r2() -> R2Client:
    """Return a configured R2 client, falling back to a no-op in dev."""
    try:
        return R2Client()
    except RuntimeError:
        logger.info("r2_not_configured_using_noop_client")
        return _NoopR2Client()  # type: ignore[return-value]


def _build_fetcher(session: AsyncSession) -> OpenAPIFetcher:
    """Construct an OpenAPIFetcher with all required dependencies."""
    return OpenAPIFetcher(
        r2=_build_r2(),
        spec_repo=SpecRepository(session),
        analyzer=_AsyncSpecAnalyzer(),
    )


@router.post("/fetch", response_model=SpecUploadResponse, status_code=200)
async def fetch_spec(
    body: SpecFetchRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SpecUploadResponse:
    """Fetch an OpenAPI spec from a URL, parse, validate, and return extracted tools.

    The spec is downloaded from the provided URL, validated against OpenAPI 3.0+,
    stored in Cloudflare R2, and analyzed for MCP tool definitions.
    """
    logger.info("fetch_spec_started", url=body.url, user_id=str(current_user.id))
    fetcher = _build_fetcher(session)
    result = await fetcher.fetch_from_url(
        user_id=current_user.id,
        url=body.url,
        headers=body.headers,
    )
    logger.info("fetch_spec_succeeded", spec_id=str(result.spec_id))
    return result


@router.post("/upload", response_model=SpecUploadResponse, status_code=201)
async def upload_spec(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SpecUploadResponse:
    """Upload an OpenAPI spec file (multipart, JSON or YAML, ≤5MB).

    The uploaded file is parsed, validated against OpenAPI 3.0+, stored in
    Cloudflare R2, and analyzed for MCP tool definitions.
    """
    content = await file.read()
    filename = file.filename or "spec.yaml"
    logger.info(
        "upload_spec_started",
        filename=filename,
        size_bytes=len(content),
        user_id=str(current_user.id),
    )
    fetcher = _build_fetcher(session)
    result = await fetcher.upload(
        user_id=current_user.id,
        file_content=content,
        filename=filename,
    )
    logger.info("upload_spec_succeeded", spec_id=str(result.spec_id))
    return result


@router.get("/{spec_id}/tools", response_model=SpecToolListResponse)
async def get_spec_tools(
    spec_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SpecToolListResponse:
    """Get the parsed list of MCP tools extracted from a spec.

    Fetches the spec content from Cloudflare R2, re-parses it, and extracts
    tool definitions. Verifies the requesting user owns the spec.
    """
    repo = SpecRepository(session)
    spec = await repo.get_by_id(spec_id)
    if not spec:
        raise NotFoundError("Spec not found")
    if spec.user_id != current_user.id:
        raise ForbiddenError("You do not own this spec")
    if not spec.r2_key:
        raise NotFoundError("Spec has no stored content")

    r2 = _build_r2()
    content = await r2.get_object(spec.r2_key)
    if not content:
        raise NotFoundError("Spec content not available (R2 not configured)")
    spec_dict: dict[str, Any] = json.loads(content)

    analyzer = SpecAnalyzer()
    tools = analyzer.extract_tools(spec_dict)

    logger.info(
        "get_spec_tools_succeeded",
        spec_id=str(spec.id),
        tool_count=len(tools),
    )

    return SpecToolListResponse(
        spec_id=spec.id,
        tools=tools,
    )


@router.post("/{spec_id}/select-tools", response_model=MCPServerResponse, status_code=201)
async def select_tools(
    spec_id: UUID,
    body: ToolSelectionRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerResponse:
    """Select tools from a spec and create a new MCP server.

    Re-parses the spec from R2, applies the user's tool selection and
    customizations, generates the MCP tools configuration, and creates
    a new MCPServer with that configuration.
    """
    repo = SpecRepository(session)
    spec = await repo.get_by_id(spec_id)
    if not spec:
        raise NotFoundError("Spec not found")
    if spec.user_id != current_user.id:
        raise ForbiddenError("You do not own this spec")
    if not spec.r2_key:
        raise NotFoundError("Spec has no stored content")

    # Re-parse spec from R2 for a fresh analysis
    r2 = _build_r2()
    content = await r2.get_object(spec.r2_key)
    if not content:
        raise NotFoundError("Spec content not available (R2 not configured)")
    spec_dict: dict[str, Any] = json.loads(content)

    # Extract all tools and apply user selection
    analyzer = SpecAnalyzer()
    all_tools = analyzer.extract_tools(spec_dict)

    selected_names = set(body.selected_tool_names)
    for tool in all_tools:
        tool.selected = tool.name in selected_names

    selected_count = sum(1 for t in all_tools if t.selected)
    logger.info(
        "select_tools_selection",
        spec_id=str(spec.id),
        total_tools=len(all_tools),
        selected_count=selected_count,
    )

    # Build tools config with customizations
    generator = ToolGenerator()
    tools_config = generator.build_tools_config(all_tools, body.customizations)

    # Determine spec_url based on source type
    spec_url: str | None = spec.source_url if spec.source_type == "url" else None

    # Create MCP server
    svc = MCPServerService(session)
    server = await svc.create_server(
        user_id=current_user.id,
        slug=body.slug,
        name=body.name,
        base_url=body.base_url,
        description=body.description,
        spec_url=spec_url,
        auth_scheme=body.auth_scheme,
        auth_header_name=body.auth_header_name,
        tools_config=tools_config,
        transport_mode=body.transport_mode,
    )
    # Servers start as "active" — they are ready to use immediately.
    # The AI enhancement pipeline (F2) is triggered explicitly via
    # POST /tools/enhance, which transitions status to "in_progress",
    # then "review" on completion.
    server.status = "active"
    await session.flush()

    logger.info(
        "select_tools_server_created",
        spec_id=str(spec.id),
        server_id=str(server.id),
        slug=body.slug,
    )

    return MCPServerResponse.model_validate(server)


@router.get("/{spec_id}", response_model=SpecSourceResponse)
async def get_spec(
    spec_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SpecSourceResponse:
    """Get a spec's metadata.

    Returns metadata about the fetched/uploaded OpenAPI spec including
    title, version, endpoint count, and fetch status.
    """
    repo = SpecRepository(session)
    spec = await repo.get_by_id(spec_id)
    if not spec:
        raise NotFoundError("Spec not found")
    if spec.user_id != current_user.id:
        raise ForbiddenError("You do not own this spec")
    return SpecSourceResponse.model_validate(spec)


@router.delete("/{spec_id}", status_code=204, response_model=None)
async def delete_spec(
    spec_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a spec and its stored content.

    Deletes the spec content from Cloudflare R2 (best-effort — if the R2
    object is missing, we log a warning and continue) and removes the
    metadata row from the database.
    """
    repo = SpecRepository(session)
    spec = await repo.get_by_id(spec_id)
    if not spec:
        raise NotFoundError("Spec not found")
    if spec.user_id != current_user.id:
        raise ForbiddenError("You do not own this spec")

    # Best-effort R2 delete
    if spec.r2_key:
        try:
            r2 = _build_r2()
            await r2.delete_object(spec.r2_key)
        except RuntimeError:
            logger.warning(
                "spec_delete_r2_not_configured",
                spec_id=str(spec.id),
            )
        except UpstreamError:
            logger.warning(
                "spec_delete_r2_failed_continuing",
                spec_id=str(spec.id),
                r2_key=spec.r2_key,
            )

    await repo.delete(spec)
    logger.info("spec_deleted", spec_id=str(spec.id))
