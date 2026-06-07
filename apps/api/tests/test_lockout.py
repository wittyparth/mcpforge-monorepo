"""Tests for Redis-backed account lockout."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


# Same fake Redis helper as test_token_rotation.
class _FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}

    async def incr(self, key: str) -> int:
        cur = int(self.kv.get(key, "0")) + 1
        self.kv[key] = str(cur)
        return cur

    async def expire(self, key: str, ttl: int) -> None:  # noqa: ARG002
        return None

    async def ttl(self, key: str) -> int:
        # Pretend the key has 60s left; tests that need exact behavior
        # override this.
        return 60 if key in self.kv else -2

    async def exists(self, key: str) -> int:
        return 1 if key in self.kv else 0

    async def get(self, key: str) -> str | None:
        return self.kv.get(key)

    async def setex(self, key: str, ttl: int, value: bytes) -> None:  # noqa: ARG002
        self.kv[key] = value.decode() if isinstance(value, (bytes, bytearray)) else str(value)

    async def delete(self, key: str) -> None:
        self.kv.pop(key, None)


@pytest.fixture
def fake_redis():
    fr = _FakeRedis()

    async def _iter():
        yield fr

    with patch("app.services.auth.lockout._with_redis", _iter), \
         patch("app.services.auth.lockout.get_redis_pool", AsyncMock()):
        yield fr


class TestInitiallyUnlocked:
    @pytest.mark.asyncio
    async def test_new_account_is_not_locked(self, fake_redis) -> None:
        from app.services.auth.lockout import is_locked, get_status
        assert await is_locked("user@example.com") is False
        status = await get_status("user@example.com")
        assert status.locked is False
        assert status.attempts == 0


class TestFailureTracking:
    @pytest.mark.asyncio
    async def test_record_failure_increments_attempts(self, fake_redis) -> None:
        from app.services.auth.lockout import record_failure
        s = await record_failure("user@example.com")
        assert s.locked is False
        assert s.attempts == 1

    @pytest.mark.asyncio
    async def test_lock_after_max_attempts(self, fake_redis, monkeypatch) -> None:
        from app.core.config import settings
        from app.services.auth.lockout import record_failure, is_locked, get_status
        monkeypatch.setattr(settings, "LOCKOUT_MAX_ATTEMPTS", 3)
        for i in range(3):
            s = await record_failure("user@example.com")
            if i < 2:
                assert s.locked is False
            else:
                assert s.locked is True
        assert await is_locked("user@example.com") is True
        status = await get_status("user@example.com")
        assert status.locked is True
        assert status.retry_after > 0


class TestSuccessClears:
    @pytest.mark.asyncio
    async def test_record_success_resets_counter(self, fake_redis) -> None:
        from app.services.auth.lockout import record_failure, record_success, get_status
        await record_failure("user@example.com")
        await record_failure("user@example.com")
        await record_success("user@example.com")
        status = await get_status("user@example.com")
        assert status.locked is False
        assert status.attempts == 0
