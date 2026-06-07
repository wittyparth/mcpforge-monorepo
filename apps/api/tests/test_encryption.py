"""Tests for Fernet-based symmetric encryption."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.encryption import decrypt, encrypt


class TestRoundTrip:
    def test_encrypt_then_decrypt_returns_original(self) -> None:
        # Use a stable, explicit key for this test so we can decrypt later.
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"ENCRYPTION_KEY": key}):
            from app.core.config import Settings
            Settings.model_config["env_file"] = None
            plaintext = "sk_test_supersecret_apikey_12345"
            ciphertext = encrypt(plaintext)
            assert isinstance(ciphertext, bytes)
            assert plaintext.encode() not in ciphertext
            assert decrypt(ciphertext) == plaintext


class TestWithExplicitKey:
    def test_round_trip_with_explicit_key(self) -> None:
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"ENCRYPTION_KEY": key}):
            assert decrypt(encrypt("hello")) == "hello"
            assert decrypt(encrypt("")) == ""


class TestInputTypes:
    def test_encrypt_requires_str(self) -> None:
        with pytest.raises(TypeError):
            encrypt(b"bytes-not-allowed")  # type: ignore[arg-type]

    def test_decrypt_requires_bytes(self) -> None:
        with pytest.raises(TypeError):
            decrypt("string-not-allowed")  # type: ignore[arg-type]


class TestInvalidToken:
    def test_decrypt_with_wrong_key_raises(self) -> None:
        # Encrypt with key A, attempt to decrypt with key B → InvalidToken.
        # Use the Fernet API directly (not the app's cached instance) so
        # the key rotation scenario is testable.
        from cryptography.fernet import Fernet as FernetInstance
        key_a = FernetInstance(Fernet.generate_key())
        key_b = FernetInstance(Fernet.generate_key())
        ciphertext = key_a.encrypt(b"top secret")
        with pytest.raises(InvalidToken):
            key_b.decrypt(ciphertext)
