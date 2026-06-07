# @mcpforge/shared-types

Auto-generated TypeScript types from the MCPForge API's OpenAPI schema.

## Usage

Import the types in any TypeScript file:

```ts
import type { paths, components } from '@mcpforge/shared-types';

// Path-based types
type RegisterRequest =
  paths['/api/v1/auth/register']['post']['requestBody']['content']['application/json'];
type RegisterResponse =
  paths['/api/v1/auth/register']['post']['responses']['200']['content']['application/json'];

// Component-based types
type User = components['schemas']['UserResponse'];
```

## Regenerating

After backend changes, regenerate the types:

```bash
# 1. Make sure backend is running locally
cd apps/api && .venv/bin/uvicorn app.main:app --port 8000 &

# 2. Fetch the latest OpenAPI schema and regenerate
cd packages/shared-types
pnpm fetch
pnpm generate
```

Or in one command from the monorepo root:

```bash
cd packages/shared-types && pnpm fetch && pnpm generate
```

## CI

In CI, the types are regenerated automatically whenever the backend schema changes. This package is checked in (not gitignored) so that:

- Frontend can build even when the backend isn't running
- Type changes are visible in code review
- Breaking changes are caught at PR time

## Files

- `openapi.json` — The raw OpenAPI schema from the backend
- `api-types.d.ts` — Generated TypeScript types (1064 lines, 30+ schemas)
- `package.json` — Package config with the `fetch` and `generate` scripts
