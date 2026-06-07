"""Async S3-compatible client for Cloudflare R2 (F1 spec storage).

Wraps aioboto3 to provide put/get/delete operations on the configured
R2 bucket. Each operation creates a fresh session/client because
aioboto3 does not support reusing clients across context managers.

All public methods are async and use structlog for structured logging.
"""

from __future__ import annotations

import aioboto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings
from app.core.exceptions import UpstreamError
from app.core.logging import get_logger

logger = get_logger(__name__)


class R2Client:
    """Async S3-compatible client for Cloudflare R2.

    Validates required settings on instantiation. Raises ``RuntimeError``
    with a descriptive message if any required environment variable is
    missing.

    In development environments where R2 is not available, check
    ``is_configured`` before calling operations to avoid noisy errors.
    """

    def __init__(self) -> None:
        self._bucket = settings.R2_BUCKET
        self._endpoint_url = settings.r2_endpoint

        missing: list[str] = []
        if not self._endpoint_url:
            missing.append("R2_ENDPOINT_URL or R2_ACCOUNT_ID")
        if not self._bucket:
            missing.append("R2_BUCKET")
        if not settings.R2_ACCESS_KEY_ID:
            missing.append("R2_ACCESS_KEY_ID")
        if not settings.R2_SECRET_ACCESS_KEY:
            missing.append("R2_SECRET_ACCESS_KEY")
        if missing:
            msg = f"R2Client is not configured: missing {', '.join(missing)}"
            logger.error("r2_client_init_failed", missing=missing)
            raise RuntimeError(msg)

        logger.info(
            "r2_client_init",
            bucket=self._bucket,
            endpoint=bool(self._endpoint_url),
        )

    @property
    def is_configured(self) -> bool:
        """Check whether all required R2 environment variables are set.

        Returns:
            True if every required setting has a non-empty value.
        """
        return bool(
            settings.R2_BUCKET
            and settings.r2_endpoint
            and settings.R2_ACCESS_KEY_ID
            and settings.R2_SECRET_ACCESS_KEY
        )

    def _session(self) -> aioboto3.Session:
        """Create a new aioboto3 session.

        A fresh session is created per operation because aioboto3
        sessions are lightweight and not designed for reuse across
        context managers.
        """
        return aioboto3.Session()

    def _client_config(self) -> BotoConfig:
        """Return the botocore config required by Cloudflare R2.

        R2 requires ``signature_version="s3v4"`` and path-style
        addressing.
        """
        return BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )

    async def put_object(
        self, key: str, body: bytes, content_type: str = "application/json"
    ) -> None:
        """Upload ``body`` to the configured R2 bucket at ``key``.

        Args:
            key: S3 object key path.
            body: Raw bytes to upload.
            content_type: MIME content-type header value.

        Raises:
            UpstreamError: If the S3 operation fails for any reason.
        """
        session = self._session()
        try:
            async with session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                config=self._client_config(),
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            ) as s3:
                await s3.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=body,
                    ContentType=content_type,
                )
        except (ClientError, EndpointConnectionError) as exc:
            logger.error("r2_put_failed", key=key, error=str(exc))
            raise UpstreamError(f"Failed to upload object: {exc}") from exc

    async def get_object(self, key: str) -> bytes:
        """Download the object at ``key`` from the configured R2 bucket.

        Args:
            key: S3 object key path.

        Returns:
            Object body as raw bytes.

        Raises:
            UpstreamError: If the S3 operation fails for any reason.
        """
        session = self._session()
        try:
            async with session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                config=self._client_config(),
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            ) as s3:
                response = await s3.get_object(
                    Bucket=self._bucket,
                    Key=key,
                )
                body: bytes = await response["Body"].read()
                return body
        except (ClientError, EndpointConnectionError) as exc:
            logger.error("r2_get_failed", key=key, error=str(exc))
            raise UpstreamError(f"Failed to download object: {exc}") from exc

    async def delete_object(self, key: str) -> None:
        """Delete the object at ``key`` from the configured R2 bucket.

        Args:
            key: S3 object key path.

        Raises:
            UpstreamError: If the S3 operation fails for any reason.
        """
        session = self._session()
        try:
            async with session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                config=self._client_config(),
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            ) as s3:
                await s3.delete_object(
                    Bucket=self._bucket,
                    Key=key,
                )
        except (ClientError, EndpointConnectionError) as exc:
            logger.error("r2_delete_failed", key=key, error=str(exc))
            raise UpstreamError(f"Failed to delete object: {exc}") from exc
