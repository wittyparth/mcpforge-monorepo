#!/bin/bash
# ──────────────────────────────────────────────────────────────────
# dev.sh — MCPForge single-command local dev
# ──────────────────────────────────────────────────────────────────
# Usage:
#   ./scripts/dev.sh               Start everything (docker build + up)
#   ./scripts/dev.sh --build        Force rebuild images
#   ./scripts/dev.sh --logs         Follow logs after starting
#   ./scripts/dev.sh --stop         Stop all services
#   ./scripts/dev.sh --help         Show this message
#
# What this does:
#   1. Starts Postgres 16 + Redis 7 + FastAPI + Celery Worker + Next.js
#   2. Runs DB migrations automatically
#   3. Enables hot-reload for both API (uvicorn --reload) and Web (turbopack)
#   4. Clean shutdown with Ctrl+C
# ──────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[dev]${NC} $1"; }
warn() { echo -e "${YELLOW}[dev]${NC} $1"; }
err()  { echo -e "${RED}[dev]${NC} $1"; }

# ── Help ─────────────────────────────────────────────────────────────
show_help() {
  sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //;s/^#$//'
  exit 0
}

# ── Parse args ────────────────────────────────────────────────────────
BUILD_FLAG=""
FOLLOW_LOGS=false
ACTION="up"

for arg in "$@"; do
  case "$arg" in
    --help|-h)    show_help ;;
    --build)      BUILD_FLAG="--build" ;;
    --logs|-l)    FOLLOW_LOGS=true ;;
    --stop)       ACTION="down" ;;
    --rebuild)    ACTION="rebuild" ;;
    *)            warn "Unknown arg: $arg"; show_help ;;
  esac
done

# ── Stop ──────────────────────────────────────────────────────────────
if [ "$ACTION" = "down" ]; then
  log "Stopping all services..."
  docker compose down
  log "Done. Postgres data volume is preserved (postgres_data)."
  exit 0
fi

# ── Rebuild ───────────────────────────────────────────────────────────
if [ "$ACTION" = "rebuild" ]; then
  log "Rebuilding all images from scratch..."
  docker compose build --no-cache
  log "Build complete."
  exit 0
fi

# ── Start ─────────────────────────────────────────────────────────────
log "Starting MCPForge dev environment..."
log ""
log "  ${CYAN}Postgres${NC}  → :5432"
log "  ${CYAN}Redis${NC}     → :6379"
log "  ${CYAN}API${NC}       → http://localhost:8000 (docs: /docs)"
log "  ${CYAN}Worker${NC}    → Celery (queues: default, ai, scanner, analytics)"
log "  ${CYAN}Web${NC}       → http://localhost:3000"
log ""
log "Press ${YELLOW}Ctrl+C${NC} to stop all services."
log ""

# Start all services. The api service runs migrations automatically
# via start-dev.sh before starting uvicorn.
if [ "$FOLLOW_LOGS" = true ]; then
  docker compose up $BUILD_FLAG
else
  docker compose up --detach $BUILD_FLAG
  log "All services started. Attach logs with:"
  log "  ${CYAN}docker compose logs -f${NC}"
  log "Or stop everything with:"
  log "  ${CYAN}./scripts/dev.sh --stop${NC}"
fi
