"""Tests for SSRFGuard (F2 — SSRF protection).

All DNS resolution is mocked via ``unittest.mock.patch`` so tests are
deterministic and never make real network calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import SSRFBlockedError
from app.gateway.ssrf_guard import SSRFGuard


def _mock_addrinfo(ip: str) -> list[tuple]:
    """Return a fake ``getaddrinfo`` result tuple for *ip*."""
    import socket

    return [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0)),
    ]


def _mock_addrinfo_v6(ip: str) -> list[tuple]:
    """Return a fake ``getaddrinfo`` result tuple for an IPv6 *ip*."""
    import socket

    return [
        (socket.AF_INET6, socket.SOCK_STREAM, 0, "", (ip, 0, 0, 0)),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Private IPv4 ranges
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_private_ip_10_x() -> None:
    """10.0.0.0/8 should be blocked."""
    guard = SSRFGuard()
    url = "http://10.0.0.1/api"

    with (
        patch.object(
            SSRFGuard,
            "assert_safe",
            wraps=guard.assert_safe,
        ) as _spy,
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(return_value=_mock_addrinfo("10.0.0.1")),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


@pytest.mark.asyncio
async def test_private_ip_172_16_x() -> None:
    """172.16.0.0/12 should be blocked."""
    guard = SSRFGuard()
    url = "http://172.16.0.1/api"

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(return_value=_mock_addrinfo("172.16.0.1")),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


@pytest.mark.asyncio
async def test_private_ip_192_168_x() -> None:
    """192.168.0.0/16 should be blocked."""
    guard = SSRFGuard()
    url = "http://192.168.1.1/admin"

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(return_value=_mock_addrinfo("192.168.1.1")),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


@pytest.mark.asyncio
async def test_loopback() -> None:
    """127.0.0.0/8 (loopback) should be blocked."""
    guard = SSRFGuard()
    url = "http://127.0.0.1/health"

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(return_value=_mock_addrinfo("127.0.0.1")),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


@pytest.mark.asyncio
async def test_aws_metadata() -> None:
    """169.254.0.0/16 (AWS metadata) should be blocked."""
    guard = SSRFGuard()
    url = "http://169.254.169.254/latest/meta-data"

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(
                    return_value=_mock_addrinfo("169.254.169.254"),
                ),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


@pytest.mark.asyncio
async def test_zero_ip() -> None:
    """0.0.0.0/8 should be blocked."""
    guard = SSRFGuard()
    url = "http://0.0.0.0/spec"

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(return_value=_mock_addrinfo("0.0.0.0")),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


# ═══════════════════════════════════════════════════════════════════════════
# IPv6 ranges
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ipv6_loopback() -> None:
    """::1/128 (IPv6 loopback) should be blocked."""
    guard = SSRFGuard()
    url = "http://[::1]/api"

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(return_value=_mock_addrinfo_v6("::1")),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


@pytest.mark.asyncio
async def test_ipv6_ula() -> None:
    """fc00::/7 (IPv6 ULA) should be blocked."""
    guard = SSRFGuard()
    url = "http://[fc00::1]/api"

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(return_value=_mock_addrinfo_v6("fc00::1")),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


@pytest.mark.asyncio
async def test_ipv6_link_local() -> None:
    """fe80::/10 (IPv6 link-local) should be blocked."""
    guard = SSRFGuard()
    url = "http://[fe80::1]/api"

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=AsyncMock(
                getaddrinfo=AsyncMock(return_value=_mock_addrinfo_v6("fe80::1")),
            ),
        ),
        pytest.raises(SSRFBlockedError) as exc,
    ):
        await guard.assert_safe(url)

    assert "blocked" in str(exc.value.message).lower()


# ═══════════════════════════════════════════════════════════════════════════
# Public IP — allowed
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_public_ip_allowed() -> None:
    """A public IP (93.184.216.34) should NOT be blocked."""
    guard = SSRFGuard()
    url = "http://93.184.216.34/spec.json"

    with patch(
        "asyncio.get_event_loop",
        return_value=AsyncMock(
            getaddrinfo=AsyncMock(
                return_value=_mock_addrinfo("93.184.216.34"),
            ),
        ),
    ):
        # Should not raise
        await guard.assert_safe(url)
