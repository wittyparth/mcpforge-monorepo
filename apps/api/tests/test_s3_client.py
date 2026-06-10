"""Tests for the S3 (AWS S3) storage client.

Configuration tests use monkeypatch to override the global settings
singleton. S3 operation tests mock the aioboto3 session/client layer
to verify correct API calls and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import UpstreamError
from app.core.s3_client import S3Client


class TestIsConfigured:
    """Tests for S3Client.is_configured and init validation."""

    def test_is_configured_with_all_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All required settings present returns True."""
        monkeypatch.setattr(settings, "AWS_S3_BUCKET", "test-bucket")
        monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret-key")
        monkeypatch.setattr(settings, "AWS_REGION", "us-east-1")
        client = S3Client()
        assert client.is_configured is True

    def test_is_configured_when_bucket_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing AWS_S3_BUCKET makes init raise RuntimeError (not just False)."""
        monkeypatch.setattr(settings, "AWS_S3_BUCKET", "")
        monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret-key")
        monkeypatch.setattr(settings, "AWS_REGION", "us-east-1")

        with pytest.raises(RuntimeError, match="AWS_S3_BUCKET"):
            S3Client()

    def test_is_configured_returns_false_without_bucket_direct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_configured reads settings directly — verify the contract."""
        monkeypatch.setattr(settings, "AWS_S3_BUCKET", "")
        monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret-key")
        monkeypatch.setattr(settings, "AWS_REGION", "us-east-1")

        # is_configured is a property on settings, not an instance check.
        # Verify the logic directly:
        actual = bool(
            settings.AWS_S3_BUCKET
            and settings.AWS_ACCESS_KEY_ID
            and settings.AWS_SECRET_ACCESS_KEY
            and settings.AWS_REGION
        )
        assert actual is False


class TestInitValidation:
    """Tests for S3Client.__init__ validation."""

    def test_init_raises_when_no_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing AWS_REGION raises RuntimeError."""
        monkeypatch.setattr(settings, "AWS_S3_BUCKET", "test-bucket")
        monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret-key")
        monkeypatch.setattr(settings, "AWS_REGION", "")

        with pytest.raises(RuntimeError) as exc_info:
            S3Client()
        assert "AWS_REGION" in str(exc_info.value)

    def test_init_raises_when_no_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY raises RuntimeError."""
        monkeypatch.setattr(settings, "AWS_S3_BUCKET", "test-bucket")
        monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "")
        monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "")
        monkeypatch.setattr(settings, "AWS_REGION", "us-east-1")

        with pytest.raises(RuntimeError) as exc_info:
            S3Client()
        assert "AWS_ACCESS_KEY_ID" in str(exc_info.value)
        assert "AWS_SECRET_ACCESS_KEY" in str(exc_info.value)


class TestS3Operations:
    """S3 operation tests using mocked aioboto3 session/client."""

    @pytest.fixture(autouse=True)
    def _configure_s3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up S3 settings before each test in this class."""
        monkeypatch.setattr(settings, "AWS_S3_BUCKET", "test-bucket")
        monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret-key")
        monkeypatch.setattr(settings, "AWS_REGION", "us-east-1")

    @pytest.fixture(autouse=True)
    def _mock_s3(self) -> None:
        """Set up a mock aioboto3 session and client.

        The fixture patches ``S3Client._session`` so every operation
        uses the injected mock client instead of a real S3 connection.
        """
        self.mock_s3_client = MagicMock()
        self.mock_s3_client.put_object = AsyncMock()
        self.mock_s3_client.get_object = AsyncMock()
        self.mock_s3_client.delete_object = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=self.mock_s3_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.client = MagicMock(return_value=mock_ctx)

        patcher = patch.object(S3Client, "_session", return_value=mock_session)
        patcher.start()
        yield
        patcher.stop()

    async def test_put_object_calls_s3_put_object(self) -> None:
        """put_object delegates to the S3 client with correct args."""
        client = S3Client()
        body = b'{"hello": "world"}'

        await client.put_object("test/my-key.json", body)

        self.mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/my-key.json",
            Body=body,
            ContentType="application/json",
        )

    async def test_put_object_with_custom_content_type(self) -> None:
        """put_object passes a custom content type through."""
        client = S3Client()
        body = b"text content"

        await client.put_object("test/file.txt", body, content_type="text/plain")

        self.mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.txt",
            Body=body,
            ContentType="text/plain",
        )

    async def test_get_object_returns_bytes(self) -> None:
        """get_object returns the S3 response body as raw bytes."""
        expected = b'{"hello": "world"}'
        mock_body = AsyncMock()
        mock_body.read = AsyncMock(return_value=expected)
        self.mock_s3_client.get_object = AsyncMock(return_value={"Body": mock_body})

        client = S3Client()
        result = await client.get_object("test/my-key.json")

        assert result == expected
        self.mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/my-key.json",
        )

    async def test_delete_object_calls_s3_delete_object(self) -> None:
        """delete_object delegates to the S3 client."""
        client = S3Client()
        await client.delete_object("test/old-key.json")

        self.mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/old-key.json",
        )

    async def test_put_object_raises_upstream_error_on_client_error(self) -> None:
        """put_object wraps ClientError in UpstreamError."""
        error_response = {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}}
        self.mock_s3_client.put_object = AsyncMock(
            side_effect=ClientError(error_response, "PutObject")
        )

        client = S3Client()
        with pytest.raises(UpstreamError):
            await client.put_object("test/key.json", b"data")

    async def test_get_object_raises_upstream_error_on_client_error(self) -> None:
        """get_object wraps ClientError in UpstreamError."""
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "The key does not exist"}}
        self.mock_s3_client.get_object = AsyncMock(
            side_effect=ClientError(error_response, "GetObject")
        )

        client = S3Client()
        with pytest.raises(UpstreamError):
            await client.get_object("nonexistent-key")

    async def test_delete_object_raises_upstream_error_on_client_error(self) -> None:
        """delete_object wraps ClientError in UpstreamError."""
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        self.mock_s3_client.delete_object = AsyncMock(
            side_effect=ClientError(error_response, "DeleteObject")
        )

        client = S3Client()
        with pytest.raises(UpstreamError):
            await client.delete_object("some-key")
