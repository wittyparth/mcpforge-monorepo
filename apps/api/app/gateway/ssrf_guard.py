"""SSRF Guard — prevents Server-Side Request Forgery attacks.

The ``SSRFGuard`` resolves hostnames to IP addresses and checks them
against a list of blocked private/reserved IP ranges so that the MCP
gateway cannot be tricked into making requests to internal services.
"""

from __future__ import annotations

import asyncio
import ipaddress
from urllib.parse import urlparse

from app.core.exceptions import SSRFBlockedError

# IPv4 ranges that are never reachable from the public internet
# (type narrowed in comments; ipaddress.ip_network() returns a union at
# the type level so the two lists are intentionally un-annotated)
_BLOCKED_IPV4 = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]

# IPv6 ranges that are private / link-local / loopback
_BLOCKED_IPV6 = [
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_ALL_BLOCKED: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    *_BLOCKED_IPV4,
    *_BLOCKED_IPV6,
]


class SSRFGuard:
    """Validates that URLs do not resolve to internal or reserved IP ranges."""

    async def assert_safe(self, url: str) -> None:
        """Check that *url* does not resolve to a blocked IP range.

        Steps:
        1. Parse the URL and validate the scheme (only ``http``/``https``).
        2. Resolve the hostname to one or more IP addresses.
        3. Reject if *any* resolved IP falls in a blocked range.

        Raises:
            SSRFBlockedError: If the scheme is invalid, the hostname
                cannot be resolved, or an IP is blocked.
        """
        parsed = urlparse(url)

        # -- Scheme validation ------------------------------------------------
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise SSRFBlockedError(
                f"URL scheme '{parsed.scheme}' is not allowed",
            )

        # -- Hostname extraction ----------------------------------------------
        hostname = parsed.hostname
        if not hostname:
            raise SSRFBlockedError("URL has no hostname")

        # -- DNS resolution ---------------------------------------------------
        loop = asyncio.get_event_loop()
        try:
            addrinfo = await loop.getaddrinfo(hostname, None)
        except OSError:
            raise SSRFBlockedError(f"Could not resolve hostname: {hostname}") from None

        # -- IP range checking ------------------------------------------------
        for _, _type, _proto, _canonname, sockaddr in addrinfo:
            ip_str: str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                # Not a valid IP address — skip this entry.
                continue

            for blocked_net in _ALL_BLOCKED:
                if ip in blocked_net:
                    raise SSRFBlockedError(
                        f"URL resolves to blocked IP: {ip_str}",
                    )
