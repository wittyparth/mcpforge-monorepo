"""Tests for password hashing (Argon2id primary, bcrypt legacy fallback) and JWT."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    rehash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_uses_argon2id(self) -> None:
        h = hash_password("correct horse battery staple")
        assert h.startswith("$argon2")

    def test_verify_correct_password_returns_true(self) -> None:
        h = hash_password("hunter2-correct")
        assert verify_password("hunter2-correct", h) is True

    def test_verify_wrong_password_returns_false(self) -> None:
        h = hash_password("hunter2-correct")
        assert verify_password("hunter2-WRONG", h) is False

    def test_verify_invalid_hash_returns_false(self) -> None:
        # Garbage hash format should not raise — verify returns False.
        assert verify_password("anything", "not-a-hash") is False
        assert verify_password("anything", "$argon2id$v=19$invalid") is False

    def test_hash_is_unique_per_call(self) -> None:
        # Argon2id uses random salt → same input produces different hashes.
        a = hash_password("same-input")
        b = hash_password("same-input")
        assert a != b
        assert verify_password("same-input", a) is True
        assert verify_password("same-input", b) is True

    def test_rehash_returns_argon2id(self) -> None:
        h = rehash_password("still-a-good-password")
        assert h.startswith("$argon2")
        assert verify_password("still-a-good-password", h) is True

    def test_needs_rehash_on_fresh_argon2id_returns_false(self) -> None:
        h = hash_password("brand-new-hash")
        assert needs_rehash(h) is False

    def test_legacy_bcrypt_hash_triggers_rehash(self) -> None:
        # Construct a real bcrypt hash (passlib handles this) to simulate a
        # legacy user created during Phase 1.
        from passlib.hash import bcrypt
        legacy = bcrypt.hash("legacy-password")
        assert legacy.startswith("$2b$") or legacy.startswith("$2a$")
        assert needs_rehash(legacy) is True
        # We can still verify the legacy hash directly.
        assert verify_password("legacy-password", legacy) is True


class TestAccessToken:
    def test_create_and_decode_roundtrip(self) -> None:
        user_id = str(uuid.uuid4())
        token = create_access_token(subject=user_id)
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_extra_claims_are_preserved(self) -> None:
        token = create_access_token(subject="u-1", extra_claims={"role": "admin"})
        payload = decode_token(token)
        assert payload["role"] == "admin"


class TestRefreshToken:
    def test_refresh_token_has_unique_jti(self) -> None:
        user_id = str(uuid.uuid4())
        t1 = create_refresh_token(subject=user_id)
        t2 = create_refresh_token(subject=user_id)
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        assert p1["jti"] != p2["jti"]
        assert p1["type"] == "refresh"
        assert p2["type"] == "refresh"

    def test_refresh_token_accepts_explicit_jti(self) -> None:
        token = create_refresh_token(subject="u-1", jti="my-custom-jti-12345")
        payload = decode_token(token)
        assert payload["jti"] == "my-custom-jti-12345"

    def test_expired_token_raises(self) -> None:
        # Manually construct an expired token by monkeypatching the encoder.
        from jose import jwt

        from app.core.config import settings
        expired = jwt.encode(
            {
                "sub": "u-1",
                "exp": datetime.now(UTC) - timedelta(seconds=10),
                "iat": datetime.now(UTC) - timedelta(seconds=20),
                "type": "refresh",
                "jti": "x",
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(JWTError):
            decode_token(expired)
