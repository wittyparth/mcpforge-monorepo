# MCPForge Web

The Next.js 15 frontend for MCPForge — a SaaS platform that converts any OpenAPI spec into an AI-optimized MCP server.

## Tech Stack

- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS v4
- **UI Components:** shadcn/ui (manually installed, no CLI)
- **State Management:** Zustand (client) + TanStack Query (server)
- **Forms:** react-hook-form + Zod
- **Auth:** JWT in httpOnly cookies (set by backend)
- **Package Manager:** pnpm

## Getting Started

```bash
# From the monorepo root
pnpm install
pnpm dev:web
```

Or navigate into the app:

```bash
cd apps/web
pnpm dev
```

The dev server starts at `http://localhost:3000`.

## Environment Variables

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Required variables:

| Variable              | Description         | Default                 |
| --------------------- | ------------------- | ----------------------- |
| `NEXT_PUBLIC_API_URL` | Backend FastAPI URL | `http://localhost:8000` |
| `NEXT_PUBLIC_APP_URL` | Frontend URL        | `http://localhost:3000` |

## Scripts

| Command           | Description                  |
| ----------------- | ---------------------------- |
| `pnpm dev`        | Start dev server             |
| `pnpm build`      | Production build             |
| `pnpm start`      | Start production server      |
| `pnpm lint`       | Run ESLint                   |
| `pnpm type-check` | Run TypeScript type checking |

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── (auth)/             # Auth pages (login, register)
│   ├── (dashboard)/        # Dashboard pages (servers, settings)
│   └── page.tsx            # Landing page
├── components/
│   ├── ui/                 # shadcn/ui components
│   ├── auth/               # Auth form components
│   ├── dashboard/          # Dashboard components
│   └── landing/            # Landing page sections
├── hooks/                  # Custom React hooks
├── lib/                    # Utilities (api client, validators)
├── stores/                 # Zustand stores
└── types/                  # TypeScript type definitions
```

## Adding a shadcn/ui Component

Since we don't use the shadcn CLI (it conflicts with monorepo), add components manually:

1. Create the component file in `src/components/ui/`
2. Install any required Radix UI primitives
3. Follow the existing component patterns

## Architecture

- **Server Components** by default. Add `"use client"` only when needed.
- **Auth:** Backend sets httpOnly JWT cookies. Frontend sends credentials via `fetch` with `credentials: 'include'`.
- **API Client:** Typed fetch wrapper in `lib/api.ts` with error handling.
- **Forms:** react-hook-form + Zod schemas for validation.

## Vercel Deployment

This app is ready for Vercel. Set environment variables:

```
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
NEXT_PUBLIC_APP_URL=https://your-app.vercel.app
```
