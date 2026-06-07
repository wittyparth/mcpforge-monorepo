"""Symmetric encryption for at-rest secrets (e.g., API credentials).

Uses Fernet (AES-128-CBC + HMAC-SHA256) from `cryptography.fernet`. The master
key is loaded from `settings.ENCRYPTION_KEY` (env var). In production this is
a 32-byte url-safe base64 string generated via:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

When `ENCRYPTION_KEY` is unset (e.g., dev), a deterministic dev key is used
and a warning is emitted. NEVER use the dev key in production.
"""

from __future__ import annotations

import warnings

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_DEV_KEY = Fernet.generate_key()  # rotated per process; never for prod data


def _fernet() -> Fernet:
    """Return a Fernet instance bound to the configured master key."""
    if not settings.ENCRYPTION_KEY:
        warnings.warn(
            "ENCRYPTION_KEY is not set — using a process-local dev key. "
            "DO NOT use this in production: data cannot be decrypted after restart.",
            stacklevel=2,
        )
        return Fernet(_DEV_KEY)
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> bytes:
    """Encrypt a UTF-8 string, return the Fernet token as bytes."""
    if not isinstance(plaintext, str):
        raise TypeError(f"plaintext must be str, got {type(plaintext).__name__}")
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    """Decrypt a Fernet token, return the original UTF-8 string.

    Raises:
        InvalidToken: If the token is invalid, tampered with, or encrypted
            under a different key.
    """
    if not isinstance(ciphertext, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"ciphertext must be bytes, got {type(ciphertext).__name__}"
        )
    return _fernet().decrypt(bytes(ciphertext)).decode("utf-8")
