"""Pydantic schemas for the OpenAPI spec ingestion flow (F1).

Schema authority: §4.4 of planning/features/02-FEATURE-OPENAPI-INGESTION.md
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_serializer


class ToolParameter(BaseModel):
    """A single parameter extracted from an OpenAPI operation.

    Maps to OpenAPI Parameter Object fields.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    in_: Literal["path", "query", "header", "cookie"] = Field(alias="in")
    required: bool
    description: str
    aliased_schema: dict[str, Any] = Field(
        default_factory=dict,
        serialization_alias="schema",
        description="JSON Schema for the field value",
    )
    example: Any | None = None


class SpecValidationErrorDetail(BaseModel):
    """A single validation error for a spec field (path-level).

    Renamed from SpecValidationError to avoid collision with
    app.core.exceptions.SpecValidationError.
    """

    path: str
    message: str
    line: int | None = None
    column: int | None = None


class SpecFetchErrorResponse(BaseModel):
    """Structured error response for spec fetch/validation failures."""

    error_code: str
    # One of: INVALID_URL, FETCH_TIMEOUT, INVALID_SPEC, TOO_LARGE, UNSUPPORTED_VERSION
    message: str
    details: list[SpecValidationErrorDetail] = Field(default_factory=list)
    suggestion: str | None = None


class ToolDefinition(BaseModel):
    """A single tool extracted from an OpenAPI operation.

    This is the *normalized* shape we feed into the MCP server builder.
    The original OpenAPI operation is stored alongside via `operation_id`
    for round-tripping.

    Backward compat: accepts both `method`/`http_method` and `path`/`http_path`
    on input. Serializes with both keys in output. The Python attribute is
    `tool.method` / `tool.path`; `tool.http_method` / `tool.http_path` are
    available as properties.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # ── Original fields (keep backward compat) ──────────────────────
    name: str = Field(..., description="Stable tool name, e.g., 'list_users'")
    description: str = Field(..., description="Description for LLM tool selection")
    input_schema: dict[str, Any] = Field(..., description="JSON Schema for tool arguments")
    base_url_override: str | None = Field(
        default=None,
        description="Override the server base URL for this tool only",
    )
    operation_id: str | None = Field(
        default=None,
        description="Original OpenAPI operationId, if any",
    )

    # ── New F1 fields (replace old http_method/http_path) ───────────
    # Accept both method/http_method on input; serialize as "method".
    # The @model_serializer below adds "http_method" / "http_path" to output.
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = Field(
        default="GET",
        validation_alias=AliasChoices("method", "http_method"),
        serialization_alias="method",
    )
    path: str = Field(
        default="",
        validation_alias=AliasChoices("path", "http_path"),
        serialization_alias="path",
    )
    original_operation_id: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    parameters: list[ToolParameter] = Field(default_factory=list)
    request_body_schema: dict[str, Any] | None = None
    response_schemas: dict[str, dict[str, Any]] = Field(default_factory=dict)
    security_requirements: list[dict[str, Any]] = Field(default_factory=list)
    selected: bool = False
    warnings: list[str] = Field(default_factory=list)

    # ── Backward-compat properties ──────────────────────────────────

    @property
    def http_method(self) -> str:
        """Backward-compat accessor: ``tool.http_method``."""
        return self.method

    @property
    def http_path(self) -> str:
        """Backward-compat accessor: ``tool.http_path``."""
        return self.path

    # ── Serializer: both old and new names in output ────────────────

    @model_serializer(mode="wrap")
    def _add_backward_compat_keys(self, nxt: Any) -> dict[str, Any]:
        result: dict[str, Any] = nxt(self)
        result["http_method"] = result.get("method", "")
        result["http_path"] = result.get("path", "")
        return result


class SpecUploadResponse(BaseModel):
    """Response for a successful spec upload/fetch."""

    spec_id: UUID
    title: str | None
    version: str | None
    openapi_version: str | None
    endpoint_count: int
    spec_size_bytes: int
    tools: list[ToolDefinition] = Field(default_factory=list)


class SpecToolListResponse(BaseModel):
    """Response for GET /api/v1/specs/{spec_id}/tools."""

    spec_id: UUID
    tools: list[ToolDefinition]


class SpecFetchRequest(BaseModel):
    """Request body for POST /specs/fetch."""

    url: str = Field(..., min_length=1, max_length=2000)
    headers: dict[str, str] | None = None


class SpecSourceResponse(BaseModel):
    """Response for GET /specs/{spec_id} — spec metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    source_type: str
    source_url: str | None = None
    r2_key: str | None = None
    title: str | None = None
    version: str | None = None
    openapi_version: str | None = None
    endpoint_count: int | None = None
    spec_size_bytes: int | None = None
    fetch_status: str = "pending"
    fetch_error: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
