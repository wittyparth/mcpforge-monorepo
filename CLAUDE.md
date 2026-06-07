# CLAUDE.md — Claude Code Specific Guidance

This is an alias of `AGENTS.md` for Claude Code's auto-discovery. Both files are kept in sync. If they differ, `AGENTS.md` wins.

## Claude Code workflow tips

1. **Read `AGENTS.md` first** in any new session. It has the full project context.
2. **Use the build/test commands** from AGENTS.md rather than guessing.
3. **Check `apps/api/app/models/` and `apps/web/lib/types/`** before adding new models/types — keep them in sync.
4. **Never commit without the user explicitly asking** — confirm first.
5. **Update AGENTS.md** when you learn something non-obvious about the codebase.
6. **Run `pnpm type-check` and `pnpm lint`** before reporting a task done.

## Common tasks

| Task                           | Command                                                                               |
| ------------------------------ | ------------------------------------------------------------------------------------- |
| Start everything locally       | `pnpm dev`                                                                            |
| Run only backend               | `pnpm dev:api`                                                                        |
| Run only frontend              | `pnpm dev:web`                                                                        |
| Backend tests                  | `cd apps/api && pytest`                                                               |
| Frontend tests                 | `cd apps/web && pnpm test`                                                            |
| DB migration                   | `cd apps/api && alembic revision --autogenerate -m "msg"` then `alembic upgrade head` |
| Generate TS types from backend | Start backend, then `cd apps/web && pnpm gen:api-types`                               |
| Format all code                | `pnpm format`                                                                         |
| Lint check                     | `pnpm lint`                                                                           |
| Type check                     | `pnpm type-check`                                                                     |
| Full CI check                  | `pnpm build && pnpm test && pnpm lint && pnpm type-check`                             |

## Project rules

- The user is the **solo builder**. Optimize for shipping speed + production quality.
- Use **Vercel** for frontend, **Render free tier** for backend, **Neon** for DB, **Upstash** for Redis. Don't suggest AWS unless asked.
- **Free/open-source tools only.** Don't recommend paid SaaS templates.
- **Phased development.** Don't try to build everything in one go. Suggest the next phase after the current one is done.
- The PRD (`../MCPForge_PRD.md`) is the spec, but the user has chosen to **defer** the 3-service split, KMS encryption, Celery, S3, advanced analytics. Don't add these back unless asked.
