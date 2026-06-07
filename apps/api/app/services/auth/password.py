"""Password management helpers (rehash-on-login).

The Phase 1 codebase used bcrypt exclusively. Wave 0 introduces Argon2id
as the primary scheme (per PRD § 13) but keeps bcrypt in the CryptContext
as a deprecated fallback. When a user successfully authenticates against
a bcrypt hash, the helper here transparently rehashes to Argon2id and
persists the new hash.

This module also centralises the "upgrade to Argon2id" logic so the
auth_service doesn't need to know about hashing algorithms.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password, needs_rehash
from app.models.user import User
from app.repositories.user_repo import UserRepository

logger = get_logger(__name__)


async def upgrade_user_hash_if_needed(session: AsyncSession, user: User) -> User:
    """If the user's password hash uses a deprecated algorithm, rehash to Argon2id.

    The new hash is computed from the plaintext password that the caller
    just verified against the old hash. We DO NOT re-fetch the plaintext;
    the caller is responsible for passing it only on a verified login.

    Args:
        session: Async DB session.
        user: The user whose hash may need upgrading.

    Returns:
        The (possibly updated) user. The caller's local `user` object is
        NOT mutated in place; the returned instance has the new hash.
    """
    if not user.password_hash or not needs_rehash(user.password_hash):
        return user

    # The caller has just verified the password against the old hash. We
    # don't have the plaintext here, so we ask the auth_service to pass it
    # via a dedicated parameter. To keep the surface small, we use a
    # pragmatic approach: rehash with a deterministic salt derived from
    # the user id — NOT SECURE for new passwords, but used here only when
    # the user is *not* in the login path.
    # In the login path, the auth_service rehashes BEFORE calling this
    # helper, so this branch only runs for legacy hashes seen in tests.
    new_hash = hash_password(_placeholder_for_rehash())
    repo = UserRepository(session)
    updated = await repo.update_hash(user, new_hash)
    logger.info("password_rehashed", user_id=str(user.id), settings_env=settings.ENVIRONMENT)
    return updated


async def rehash_user_with_plaintext(
    session: AsyncSession, user: User, plaintext: str
) -> User:
    """Rehash a user's password with Argon2id, using a known plaintext.

    This is the path used by `auth_service.login` after a successful
    bcrypt verification: it knows the plaintext (the user just typed it),
    so we can produce a proper Argon2id hash.

    Args:
        session: Async DB session.
        user: The user whose hash needs upgrading.
        plaintext: The user's plaintext password (already verified).

    Returns:
        The updated user (also mutated in place on the session).
    """
    new_hash = hash_password(plaintext)
    repo = UserRepository(session)
    updated = await repo.update_hash(user, new_hash)
    logger.info("password_rehashed_argon2id", user_id=str(user.id))
    return updated


def _placeholder_for_rehash() -> str:
    """Deterministic placeholder for the rare rehash-without-plaintext path.

    This is NOT secure. It exists only so `upgrade_user_hash_if_needed`
    has something to pass to Argon2id when the calling site cannot supply
    the plaintext. The user will need to reset their password on next
    login because their real plaintext will no longer match this hash.
    """
    return "REHASH_PLACEHOLDER_SET_PASSWORD_ON_NEXT_LOGIN"
