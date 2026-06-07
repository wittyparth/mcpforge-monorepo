#!/bin/bash
# ──────────────────────────────────────────────────────────────────
# dev-start.sh — MCPForge API dev entrypoint (for Dockerfile.dev)
# ──────────────────────────────────────────────────────────────────
# Runs migrations, then starts uvicorn with --reload for hot-reload
# development. This replaces the production start.sh which does
# NOT use --reload.
#
# Why a separate script? start.sh is used in production (Render)
# and must NOT have --reload. This dev variant has --reload for
# local development convenience.
# ──────────────────────────────────────────────────────────────────
set -e

echo "=== Running database migrations ==="
uv run alembic upgrade head
echo "=== Migrations complete ==="

echo "=== Starting uvicorn (dev mode, --reload on) ==="
exec uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
