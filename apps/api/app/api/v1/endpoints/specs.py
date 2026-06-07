"""OpenAPI spec ingestion endpoints (F1) — route stubs.

These endpoints exist in the Wave 0 Skeleton but return 501 until F1
replaces them with real implementations. The contract is locked here
so F1 cannot drift.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/specs", tags=["specs"])


@router.post("/fetch", status_code=501)
async def fetch_spec() -> None:
    """Fetch an OpenAPI spec from a URL and return parsed tools.

    Pending F1 (OpenAPI Ingestion). See `planning/features/02-FEATURE-OPENAPI-INGESTION.md`.
    """
    raise NotImplementedFeatureError("OpenAPI Ingestion: pending F1")


@router.post("/upload", status_code=501)
async def upload_spec() -> None:
    """Upload an OpenAPI spec file (multipart, ≤5MB).

    Pending F1. Stores the spec in Cloudflare R2 and returns a SpecSource.
    """
    raise NotImplementedFeatureError("OpenAPI Ingestion: pending F1")


@router.get("/{spec_id}/tools", status_code=501)
async def get_spec_tools(spec_id: UUID) -> None:
    """Get the parsed tools list for a spec.

    Pending F1.
    """
    raise NotImplementedFeatureError("OpenAPI Ingestion: pending F1")


@router.get("/{spec_id}", status_code=501)
async def get_spec(spec_id: UUID) -> None:
    """Get a spec's metadata.

    Pending F1.
    """
    raise NotImplementedFeatureError("OpenAPI Ingestion: pending F1")


@router.delete("/{spec_id}", status_code=501)
async def delete_spec(spec_id: UUID) -> None:
    """Delete a spec (and its R2 blob).

    Pending F1.
    """
    raise NotImplementedFeatureError("OpenAPI Ingestion: pending F1")
