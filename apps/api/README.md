# MCPForge API

FastAPI backend for MCPForge — a SaaS that converts OpenAPI specs into AI-optimized MCP servers.

## Architecture

This app consolidates three services from the PRD into one FastAPI process:

- **Main API** (`/api/v1/...`) — User management, auth, server CRUD
- **MCP Gateway** (`/mcp/v1/{slug}/...`) — Hosted MCP protocol endpoints
- **Playground Proxy** (`/ws/playground/{slug}`) — WebSocket-based MCP playground

## Quick Start

```bash
# Clone and enter directory
cd apps/api

# Install dependencies
uv sync

# Copy environment config
cp .env.example .env
# Edit .env with your PostgreSQL and Redis connection strings

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for Swagger UI.

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check app

# Type check
uv run mypy app

# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Run migrations
uv run alembic upgrade head
```

## Docker

```bash
# Build
docker build -t mcpforge-api .

# Run
docker run -p 8000:8000 mcpforge-api
```

## Deployment

See `render.yaml` for Render Blueprint configuration. The API is designed to deploy on Render free tier.

## Project Structure

```
apps/api/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── core/                 # Config, security, DB, Redis, exceptions, logging
│   ├── api/v1/              # REST API endpoints
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   ├── repositories/        # Data access layer
│   ├── gateway/             # MCP protocol implementation
│   └── playground/          # WebSocket playground
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── Dockerfile               # Multi-stage build
├── render.yaml              # Render Blueprint
├── pyproject.toml           # Python project config
└── README.md
```

## Phase 1 Status

| Feature                                     | Status                      |
| ------------------------------------------- | --------------------------- |
| Auth (register, login, refresh, logout, me) | ✅ Done                     |
| MCP Server CRUD                             | ✅ Done                     |
| Health endpoints                            | ✅ Done                     |
| MCP Gateway (SSE + HTTP)                    | 🟡 Minimal (echo tool only) |
| WebSocket Playground                        | 🟡 Minimal (echo tool only) |
| AI Description Engine                       | ❌ Phase 2                  |
| Security Scanner                            | ❌ Phase 2                  |
| Analytics Dashboard                         | ❌ Phase 2                  |
| Teams & Collaboration                       | ❌ Phase 2                  |
| Credential Encryption                       | 🟡 Schema only, Phase 2     |

## Tech Stack

- Python 3.12 + FastAPI 0.115
- SQLAlchemy 2.0 (async) + asyncpg
- Redis (redis.asyncio)
- Alembic for migrations
- JWT auth (httpOnly cookies)
- Pydantic v2 + pydantic-settings
- pytest + httpx (async tests)
- Ruff + Mypy (strict)
- Docker (multi-stage)
