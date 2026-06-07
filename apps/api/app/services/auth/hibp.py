"""Have I Been Pwned (HIBP) password breach check.

Uses the HIBP Pwned Passwords range API with k-anonymity: we send only
the first 5 characters of the SHA-1 hash of the password, and the API
returns all hash suffixes that share that prefix. We compare the full
hash locally. The plaintext password never leaves the process.

Reference: https://haveibeenpwned.com/API/v3#PwnedPasswords
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# The HIBP range API requires a User-Agent identifying the consumer.
_USER_AGENT = "MCPForge-PasswordCheck/1.0 (security-research)"


@dataclass(frozen=True, slots=True)
class HIBPResult:
    """Result of a HIBP check.

    Attributes:
        breached: True if the password appears in HIBP.
        count: Number of times the password appears (0 if not breached).
    """

    breached: bool
    count: int


def _sha1_hex(password: str) -> str:
    """Return the SHA-1 hex digest of a UTF-8 string (uppercased per HIBP spec)."""
    return hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()


async def check_password_breached(
    password: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 5.0,
) -> HIBPResult:
    """Check whether a password has appeared in known breaches via HIBP.

    Uses the k-anonymity range API: the first 5 characters of the SHA-1
    hash are sent to HIBP, and the response is matched locally against
    the full hash. The plaintext password never leaves the process.

    Args:
        password: Plain-text password to check.
        client: Optional pre-configured httpx.AsyncClient (for testing with
            respx). A new client is created per call if not provided.
        timeout: Request timeout in seconds.

    Returns:
        HIBPResult with `breached=True` if the password is in HIBP.

    Note:
        On any network error, this function fails OPEN (returns
        `breached=False`) and logs a warning. We never want a HIBP outage
        to block user registration.
    """
    if not settings.HIBP_ENABLED:
        return HIBPResult(breached=False, count=0)

    digest = _sha1_hex(password)
    prefix, suffix = digest[:5], digest[5:]
    url = f"{settings.HIBP_API_URL}/{prefix}"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=timeout)
    try:
        resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("hibp_check_failed", error=str(exc), url=url)
        return HIBPResult(breached=False, count=0)
    finally:
        if owns_client and client is not None:
            await client.aclose()

    # Response format: "<SUFFIX_HEX>:<COUNT>\r\n" per line
    for line in resp.text.splitlines():
        if ":" not in line:
            continue
        remote_suffix, _, count_str = line.partition(":")
        if remote_suffix.strip().upper() == suffix:
            try:
                count = int(count_str.strip())
            except ValueError:
                count = 1
            return HIBPResult(breached=True, count=count)

    return HIBPResult(breached=False, count=0)
