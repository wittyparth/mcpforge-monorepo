"""Celery application factory for background jobs.

Three logical queues (consumed by separate worker pools in production,
one pool per queue in dev for simplicity):

- `ai`         — AI description enhancement (F2)
- `scanner`    — Security scans (F5)
- `analytics`  — Tool call analytics aggregation (F6)
- `default`    — Wave 0 / smoke-test queue

The free-tier worker process on Render runs all queues with low
concurrency; Phase 1.1 splits this into dedicated services.

Tasks MUST be idempotent — they may be retried on broker disconnect.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "mcpforge",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.services.ai_description.tasks",
        "app.services.auth.tasks",
        "app.services.analytics.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_routes={
        "app.services.ai_description.tasks.*": {"queue": "ai"},
        "app.services.security_scanner.tasks.*": {"queue": "scanner"},
        "app.services.analytics.tasks.*": {"queue": "analytics"},
        "app.services.auth.tasks.*": {"queue": "default"},
    },
    task_queues={
        "ai": {"exchange": "ai", "routing_key": "ai"},
        "scanner": {"exchange": "scanner", "routing_key": "scanner"},
        "analytics": {"exchange": "analytics", "routing_key": "analytics"},
        "default": {"exchange": "default", "routing_key": "default"},
    },
    beat_schedule={
        "create-tool-call-partitions": {
            "task": "app.services.analytics.tasks.create_partitions",
            "schedule": crontab(hour=0, minute=30),
        },
        "cleanup-revoked-tokens": {
            "task": "app.services.auth.tasks.cleanup_revoked_tokens",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)


def ping_workers(timeout: float = 2.0) -> bool:
    """Synchronously ping the Celery worker pool; return True if any respond.

    Used by the /health endpoint to surface worker liveness without async deps.
    A timeout (in seconds) bounds the call so a dead worker doesn't hang the
    health check.
    """
    try:
        replies = celery_app.control.ping(timeout=timeout)
        return bool(replies)
    except Exception:
        return False
