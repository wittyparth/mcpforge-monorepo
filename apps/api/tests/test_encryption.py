"""Tests for Fernet-based symmetric encryption."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.encryption import decrypt, encrypt


class TestRoundTrip:
    def test_encrypt_then_decrypt_returns_original(self) -> None:
        # Ensure we use a stable dev key for this test.
        with patch.dict(os.environ, {"ENCRYPTION_KEY": ""}, clear=False):
            plaintext = "sk_test_supersecret_apikey_12345"
            ciphertext = encrypt(plaintext)
            assert isinstance(ciphertext, bytes)
            assert plaintext.encode() not in ciphertext  # ciphertext != plaintext
            assert decrypt(ciphertext) == plaintext


class TestWithExplicitKey:
    def test_round_trip_with_explicit_key(self) -> None:
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"ENCRYPTION_KEY": key}, clear=False):
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
        with patch.dict(os.environ, {"ENCRYPTION_KEY": Fernet.generate_key().decode()}, clear=False):
            ciphertext = encrypt("top secret")
        with patch.dict(os.environ, {"ENCRYPTION_KEY": Fernet.generate_key().decode()}, clear=False):
            with pytest.raises(InvalidToken):
                decrypt(ciphertext)
