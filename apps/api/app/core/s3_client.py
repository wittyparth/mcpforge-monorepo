"""Async S3 client for AWS S3 (F1 spec storage).

Wraps aioboto3 to provide put/get/delete operations on the configured
S3 bucket. Each operation creates a fresh session/client because
aioboto3 does not support reusing clients across context managers.

All public methods are async and use structlog for structured logging.
"""

from __future__ import annotations

import aioboto3
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings
from app.core.exceptions import UpstreamError
from app.core.logging import get_logger

logger = get_logger(__name__)


class S3Client:
    """Async S3 client for AWS S3.

    Validates required settings on instantiation. Raises ``RuntimeError``
    with a descriptive message if any required environment variable is
    missing.

    In development environments where S3 is not available, check
    ``is_configured`` before calling operations to avoid noisy errors.
    """

    def __init__(self) -> None:
        self._bucket = settings.AWS_S3_BUCKET
        self._endpoint_url = settings.AWS_S3_ENDPOINT_URL or None

        missing: list[str] = []
        if not self._bucket:
            missing.append("AWS_S3_BUCKET")
        if not settings.AWS_ACCESS_KEY_ID:
            missing.append("AWS_ACCESS_KEY_ID")
        if not settings.AWS_SECRET_ACCESS_KEY:
            missing.append("AWS_SECRET_ACCESS_KEY")
        if not settings.AWS_REGION:
            missing.append("AWS_REGION")
        if missing:
            msg = f"S3Client is not configured: missing {', '.join(missing)}"
            logger.error("s3_client_init_failed", missing=missing)
            raise RuntimeError(msg)

        logger.info(
            "s3_client_init",
            bucket=self._bucket,
            region=settings.AWS_REGION,
            endpoint=bool(self._endpoint_url),
        )

    @property
    def is_configured(self) -> bool:
        """Check whether all required S3 environment variables are set.

        Returns:
            True if every required setting has a non-empty value.
        """
        return bool(
            settings.AWS_S3_BUCKET
            and settings.AWS_ACCESS_KEY_ID
            and settings.AWS_SECRET_ACCESS_KEY
            and settings.AWS_REGION
        )

    def _session(self) -> aioboto3.Session:
        """Create a new aioboto3 session.

        A fresh session is created per operation because aioboto3
        sessions are lightweight and not designed for reuse across
        context managers.
        """
        return aioboto3.Session()

    async def put_object(
        self, key: str, body: bytes, content_type: str = "application/json"
    ) -> None:
        """Upload ``body`` to the configured S3 bucket at ``key``.

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
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            ) as s3:
                await s3.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=body,
                    ContentType=content_type,
                )
        except (ClientError, EndpointConnectionError) as exc:
            logger.error("s3_put_failed", key=key, error=str(exc))
            raise UpstreamError(f"Failed to upload object: {exc}") from exc

    async def get_object(self, key: str) -> bytes:
        """Download the object at ``key`` from the configured S3 bucket.

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
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            ) as s3:
                response = await s3.get_object(
                    Bucket=self._bucket,
                    Key=key,
                )
                body: bytes = await response["Body"].read()
                return body
        except (ClientError, EndpointConnectionError) as exc:
            logger.error("s3_get_failed", key=key, error=str(exc))
            raise UpstreamError(f"Failed to download object: {exc}") from exc

    async def delete_object(self, key: str) -> None:
        """Delete the object at ``key`` from the configured S3 bucket.

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
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            ) as s3:
                await s3.delete_object(
                    Bucket=self._bucket,
                    Key=key,
                )
        except (ClientError, EndpointConnectionError) as exc:
            logger.error("s3_delete_failed", key=key, error=str(exc))
            raise UpstreamError(f"Failed to delete object: {exc}") from exc
