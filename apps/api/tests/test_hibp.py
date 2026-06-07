"""Tests for HIBP k-anonymity password breach check (uses respx)."""

from __future__ import annotations

import hashlib

import httpx
import pytest
import respx

from app.core.config import settings
from app.services.auth.hibp import HIBPResult, check_password_breached

# SHA-1 of "password" — a well-known breached password.
_PASSWORD_SHA1 = hashlib.sha1(b"password", usedforsecurity=False).hexdigest().upper()
_PREFIX = _PASSWORD_SHA1[:5]
_SUFFIX = _PASSWORD_SHA1[5:]


@pytest.fixture
def hibp_off(monkeypatch):
    monkeypatch.setattr(settings, "HIBP_ENABLED", True)


class TestBreachedPassword:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_breached_when_hash_found(self, hibp_off) -> None:
        # The HIBP response is "<SUFFIX>:<COUNT>" per line, for ALL suffixes
        # that share the requested prefix. We include our target suffix.
        respx.route(host="api.pwnedpasswords.com").mock(
            return_value=httpx.Response(200, text=f"XXXXX:3\r\n{_SUFFIX}:9999\r\nYYYYY:1\r\n")
        )
        result = await check_password_breached("password")
        assert isinstance(result, HIBPResult)
        assert result.breached is True
        assert result.count == 9999


class TestCleanPassword:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_not_breached_when_hash_absent(self, hibp_off) -> None:
        respx.route(host="api.pwnedpasswords.com").mock(
            return_value=httpx.Response(200, text="XXXXX:3\r\nYYYYY:1\r\n")
        )
        result = await check_password_breached("a-truly-unique-password-2026-xyzzy-9999")
        assert result.breached is False
        assert result.count == 0


class TestNetworkErrorFailsOpen:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_not_breached_on_500(self, hibp_off) -> None:
        respx.route(host="api.pwnedpasswords.com").mock(return_value=httpx.Response(500))
        result = await check_password_breached("anything")
        # Network failure → fail OPEN (don't block registration).
        assert result.breached is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_not_breached_on_timeout(self, hibp_off) -> None:
        respx.route(host="api.pwnedpasswords.com").mock(
            side_effect=httpx.ConnectError("nope")
        )
        result = await check_password_breached("anything")
        assert result.breached is False


class TestDisabled:
    @pytest.mark.asyncio
    async def test_disabled_returns_false(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "HIBP_ENABLED", False)
        result = await check_password_breached("password")
        assert result.breached is False
        assert result.count == 0


class TestPrivacyGuarantee:
    @pytest.mark.asyncio
    @respx.mock
    async def test_only_5_char_prefix_is_sent(self, hibp_off, monkeypatch) -> None:
        """The plaintext password must NEVER appear in the outgoing request URL."""
        captured_urls: list[str] = []

        def _capture(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return httpx.Response(200, text="XXXXX:1\r\n")

        respx.route(host="api.pwnedpasswords.com").mock(side_effect=_capture)
        await check_password_breached("my-very-secret-password")
        assert len(captured_urls) == 1
        url = captured_urls[0]
        assert "my-very-secret-password" not in url
        # The URL should end with the 5-char SHA-1 prefix of the password.
        digest = hashlib.sha1(
            b"my-very-secret-password", usedforsecurity=False
        ).hexdigest().upper()
        assert url.endswith(digest[:5])
