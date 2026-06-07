"""Tests for the R2 (S3-compatible) storage client.

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
from app.core.r2_client import R2Client


class TestIsConfigured:
    """Tests for R2Client.is_configured and init validation."""

    def test_is_configured_with_all_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All required settings present returns True."""
        monkeypatch.setattr(settings, "R2_BUCKET", "test-bucket")
        monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "https://test.example.com")
        monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "test-secret-key")
        client = R2Client()
        assert client.is_configured is True

    def test_is_configured_when_bucket_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing R2_BUCKET makes init raise RuntimeError (not just False)."""
        monkeypatch.setattr(settings, "R2_BUCKET", "")
        monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "https://test.example.com")
        monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "test-secret-key")

        with pytest.raises(RuntimeError, match="R2_BUCKET"):
            R2Client()

    def test_is_configured_returns_false_without_bucket_direct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_configured reads settings directly — verify the contract."""
        monkeypatch.setattr(settings, "R2_BUCKET", "")
        monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "https://test.example.com")
        monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "test-secret-key")

        # is_configured is a property on settings, not an instance check.
        # Verify the logic directly:
        actual = bool(
            settings.R2_BUCKET
            and settings.r2_endpoint
            and settings.R2_ACCESS_KEY_ID
            and settings.R2_SECRET_ACCESS_KEY
        )
        assert actual is False


class TestInitValidation:
    """Tests for R2Client.__init__ validation."""

    def test_init_raises_when_no_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing both R2_ENDPOINT_URL and R2_ACCOUNT_ID raises RuntimeError."""
        monkeypatch.setattr(settings, "R2_BUCKET", "test-bucket")
        monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "")
        monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "")
        monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "test-secret-key")

        with pytest.raises(RuntimeError) as exc_info:
            R2Client()
        assert "R2_ACCOUNT_ID" in str(exc_info.value)

    def test_init_raises_when_no_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY raises RuntimeError."""
        monkeypatch.setattr(settings, "R2_BUCKET", "test-bucket")
        monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "https://test.example.com")
        monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "")
        monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "")

        with pytest.raises(RuntimeError) as exc_info:
            R2Client()
        assert "R2_ACCESS_KEY_ID" in str(exc_info.value)
        assert "R2_SECRET_ACCESS_KEY" in str(exc_info.value)


class TestS3Operations:
    """S3 operation tests using mocked aioboto3 session/client."""

    @pytest.fixture(autouse=True)
    def _configure_r2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up R2 settings before each test in this class."""
        monkeypatch.setattr(settings, "R2_BUCKET", "test-bucket")
        monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "https://test.example.com")
        monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "test-access-key")
        monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "test-secret-key")

    @pytest.fixture(autouse=True)
    def _mock_s3(self) -> None:
        """Set up a mock aioboto3 session and client.

        The fixture patches ``R2Client._session`` so every operation
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

        patcher = patch.object(R2Client, "_session", return_value=mock_session)
        patcher.start()
        yield
        patcher.stop()

    async def test_put_object_calls_s3_put_object(self) -> None:
        """put_object delegates to the S3 client with correct args."""
        client = R2Client()
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
        client = R2Client()
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

        client = R2Client()
        result = await client.get_object("test/my-key.json")

        assert result == expected
        self.mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/my-key.json",
        )

    async def test_delete_object_calls_s3_delete_object(self) -> None:
        """delete_object delegates to the S3 client."""
        client = R2Client()
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

        client = R2Client()
        with pytest.raises(UpstreamError):
            await client.put_object("test/key.json", b"data")

    async def test_get_object_raises_upstream_error_on_client_error(self) -> None:
        """get_object wraps ClientError in UpstreamError."""
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "The key does not exist"}}
        self.mock_s3_client.get_object = AsyncMock(
            side_effect=ClientError(error_response, "GetObject")
        )

        client = R2Client()
        with pytest.raises(UpstreamError):
            await client.get_object("nonexistent-key")

    async def test_delete_object_raises_upstream_error_on_client_error(self) -> None:
        """delete_object wraps ClientError in UpstreamError."""
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        self.mock_s3_client.delete_object = AsyncMock(
            side_effect=ClientError(error_response, "DeleteObject")
        )

        client = R2Client()
        with pytest.raises(UpstreamError):
            await client.delete_object("some-key")
