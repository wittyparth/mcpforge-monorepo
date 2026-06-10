#!/bin/bash
set -e

echo "=== Running database migrations ==="
alembic upgrade head
echo "=== Migrations complete ==="

# ── Multi-process container: uvicorn (web) + celery (worker) ──────────
# Render free tier runs ONE container per service, so we run both
# processes inside the same container. They share the same lifecycle:
# when the container sleeps or restarts, both processes restart together.
#
# Limitation: when the free tier container sleeps after 15min of
# inactivity, Celery tasks queued during the sleep window will be
# processed by Upstash Redis only when the next request wakes the
# container up. This is acceptable for low-volume background jobs.

echo "=== Starting Celery worker (background) ==="
celery -A app.core.celery_app worker \
    -Q default,ai,scanner,analytics \
    -l info \
    --concurrency=2 \
    --pool=solo \
    > /tmp/celery.log 2>&1 &
CELERY_PID=$!
echo "Celery worker started with PID ${CELERY_PID}"

trap 'echo "Stopping Celery worker (PID ${CELERY_PID})"; kill -TERM ${CELERY_PID} 2>/dev/null || true; wait ${CELERY_PID} 2>/dev/null || true; exit' INT TERM

echo "=== Starting uvicorn (foreground) ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
