# 09 — Feature 6: Usage Analytics Dashboard (Parallel Wave 2)

> **When to use:** After F4 lands. Can run in parallel with F3.
> **Produces:** Per-server analytics, time series charts, error log, description performance tracking.

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md
4. AGENTS.md
5. .planning/features/07-FEATURE-ANALYTICS-DASHBOARD.md
6. .planning/research/CELERY-FASTAPI-SSE.md (partitioning
   section)
7. .planning/09-INFRA-MIGRATIONS.md § 2.2 (tool_calls
   partitioning)
8. apps/api/alembic/versions/0003_add_tool_calls.py (from
   Skeleton — verify it creates partitions)
9. apps/api/app/gateway/tool_dispatcher.py (F4's, you'll wire
   analytics emission into it)
10. apps/web/src/app/(dashboard)/servers/[slug]/ (existing)

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Feature: F6 — Usage Analytics Dashboard
Feature plan: .planning/features/07-FEATURE-ANALYTICS-DASHBOARD.md
Build order: Parallel Wave 2 (with F3)
Prerequisites: F4 must be merged. Migration 0003 must be applied.
              tool_edit_history must exist (F2 creates it).

═══════════════════════════════════════════════════════════════════════
CRITICAL: PRIVACY
═══════════════════════════════════════════════════════════════════════

1. **Parameter VALUES are never stored in tool_calls.** Only
   parameter NAMES appear in logs (or not at all in v1.0).
2. **Error messages are sanitized** before writing to
   tool_calls.error_msg — strip Bearer tokens, API keys, Basic
   auth, query string credentials.
3. **Aggregate counts** (hourly/daily rollups) are safe to
   expose in dashboards.

═══════════════════════════════════════════════════════════════════════
DELIVERABLES
═══════════════════════════════════════════════════════════════════════

D1. **app/services/analytics/recorder.py** — record_tool_call
    (async, sanitizes errors, writes to tool_calls)
D2. **app/services/analytics/aggregator.py** — aggregate raw
    events into rollups
D3. **app/services/analytics/partition_manager.py** — creates
    next 7 days of partitions daily
D4. **app/services/analytics/tasks.py** — Celery tasks:
    - record_tool_call (called by F4 gateway)
    - aggregate_hourly (every 5 min via beat)
    - create_partitions (daily via beat)
    - cleanup_old_partitions (weekly via beat)
D5. **app/services/analytics/queries.py** — read queries for
    dashboard (use rollup tables for speed)
D6. **app/services/analytics/description_performance.py** —
    track if user's manual description edits increased call
    rates
D7. **app/schemas/analytics.py** — AnalyticsOverview,
    ToolBreakdownItem, ErrorLogItem, TimeSeriesPoint,
    ClientBreakdownItem
D8. **app/api/v1/endpoints/analytics.py** — replaces 501 stubs:
    - GET /api/v1/servers/{id}/analytics
    - GET /api/v1/servers/{id}/analytics/tools
    - GET /api/v1/servers/{id}/analytics/errors
    - GET /api/v1/servers/{id}/analytics/clients
    - GET /api/v1/servers/{id}/analytics/timeseries
    - GET /api/v1/servers/{id}/analytics/export.csv
D9. **Wire into F4 gateway** — after a successful tool call,
    fire-and-forget an `asyncio.create_task` to
    `record_tool_call(...)`. Must NOT block the response.
D10. **Update Celery beat schedule** in app/core/celery_app.py
    to include aggregate tasks
D11. **Frontend deps:** recharts (for charts), date-fns
D12. **Frontend route:**
    `/dashboard/servers/[slug]/analytics/page.tsx`
D13. **Frontend components** in
    `apps/web/src/components/analytics/`:
    - analytics-page.tsx
    - date-range-picker.tsx
    - overview-cards.tsx
    - tool-breakdown-table.tsx
    - error-log.tsx
    - client-breakdown-pie.tsx
    - time-series-chart.tsx (Recharts)
    - csv-export-button.tsx
    - description-performance-panel.tsx
    - empty-analytics.tsx
D14. **Frontend hooks** in `apps/web/src/hooks/use-analytics.ts`:
    - useAnalyticsOverview, useToolBreakdown, useErrorLog,
      useClientBreakdown, useTimeSeries, useDescriptionPerformance
D15. **Tests:** ≥30 backend, ≥5 Vitest, 1 Playwright
    (11-analytics.spec.ts)
D16. **Description performance** feature: given a server with
    tool_edit_history, compute the 7-day-before vs 7-day-after
    call rate delta. Show as: "After edit on DATE, this
    tool's call rate increased 34%."

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE
═══════════════════════════════════════════════════════════════════════

1. Schemas (analytics.py)
2. Recorder + sanitizer tests
3. Partition manager
4. Aggregator
5. Celery tasks + wire into beat
6. Queries
7. Description performance tracker
8. Endpoints
9. Wire into F4 gateway (coordinate with F4 if still in PR)
10. Verify migrations apply: alembic upgrade head
11. Verify partitions exist: SELECT * FROM pg_class WHERE
    relname LIKE 'tool_calls_%';
12. Frontend types + API + hooks
13. Frontend components
14. Frontend route
15. Vitest + Playwright
16. Full CI
17. Manual: call a server's tools 20 times, see analytics
    reflect within 5 minutes

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

[All from master template] Plus F6-specific:
[ ] Migration 0003 applied; partitions pre-created for next
    30 days
[ ] Recorder fires from gateway on every tool call (verify by
    calling a tool 10 times, see 10 rows in tool_calls)
[ ] Aggregator runs every 5 min (verify by running it manually,
    see rollup_hourly updated)
[ ] Partition creator runs daily (verify partitions exist
    for tomorrow)
[ ] CSV export works
[ ] Description performance tracking works
[ ] No parameter values ever in tool_calls (test: call a tool
    with {"api_key": "secret"}, verify secret NOT in DB)
[ ] 30+ backend tests passing
[ ] Performance: analytics overview endpoint returns in
    <100ms (uses rollup, not raw events)

═══════════════════════════════════════════════════════════════════════
REPORT BACK
═══════════════════════════════════════════════════════════════════════

[Standard format]
```

---

## Reviewer's checklist

1. **Privacy test** — register a tool call with credentials in the body, verify tool_calls.error_msg has them redacted.
2. **Aggregation speed** — call a tool 100 times, then `SELECT COUNT(*) FROM analytics_rollup_hourly WHERE hour_bucket > now() - interval '1 hour';` — should show aggregated counts.
3. **Partition management** — verify partitions exist for at least the next 7 days.
4. **Description performance** — edit a tool's description, wait for next AI run cycle, verify the performance panel shows the delta.
5. **CSV export** — download a CSV, verify parameter values are NOT in it.
6. **Charts** — verify time-series chart renders with real data, not loading state.
