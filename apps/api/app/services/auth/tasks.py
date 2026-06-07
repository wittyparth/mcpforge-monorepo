"""Celery tasks for auth maintenance.

`cleanup_revoked_tokens` is a placeholder; the real cleanup runs
implicitly via Redis TTL on the `rt:used:*` keys. We keep the task
registered so the Celery beat scheduler has a periodic job to point
at — useful for future additions (e.g., "reap revoked jti's from a
DB table once we add one").
"""

from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.services.auth.tasks.cleanup_revoked_tokens")
def cleanup_revoked_tokens() -> dict[str, int]:
    """No-op: revoked tokens expire via Redis TTL.

    Kept as a registered task so the Celery beat schedule has a job
    pointing at this module. Future work: switch from Redis-only to a
    hybrid Redis + DB approach for audit durability, and have this task
    truncate the DB table.
    """
    logger.info("cleanup_revoked_tokens_invoked", note="redis_ttl_handles_expiry")
    return {"revoked": 0}
