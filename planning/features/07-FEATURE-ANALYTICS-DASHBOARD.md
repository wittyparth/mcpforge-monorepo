# Feature 6 — Usage Analytics Dashboard

> **PRD reference:** § 7 Feature 6 (lines 473-517)
> **Build order:** Wave 2, Step 2
> **Estimated effort:** 5-6 days for one engineer

---

## 0. TL;DR

Per-server analytics showing how AI clients actually use the MCP server. Critical for iterating on tool descriptions and understanding real-world usage. The unique feature: a "Description Performance" panel that tracks whether AI-enhanced descriptions actually got called more after user edits.

Privacy by design: parameter VALUES are never stored. Only parameter NAMES appear in logs. Period.

---

## 1. Goals & Non-Goals

### 1.1 In scope
- `tool_calls` table (partitioned by day, with daily partitions auto-created)
- Per-call event recording (sampled to control volume)
- Aggregation rollups (hourly, daily) for fast dashboard queries
- Overview panel: total calls, unique sessions, error rate, avg response time, estimated token cost saved
- Per-tool breakdown: call count, success rate, avg latency, last called
- Error log: last 100 errors with sanitized messages
- Client breakdown: Claude Desktop vs Cursor vs Unknown
- Time series: 24h and 7d views
- CSV export
- Description performance tracking: track call-rate deltas after description edits
- Data retention: 7 days (free), 90 days (pro), 1 year (team, add-on)

### 1.2 Out of scope
- Real-time analytics (<1 min old) — v1.1
- Custom dashboards — v1.1
- Funnel analysis — v1.1
- Cost prediction — v1.2

---

## 2. Architecture

### 2.1 Event flow

```
Gateway tool call (F4)
  │
  │ async-fire (non-blocking)
  ▼
Celery task: record_tool_call
  │
  │ write to tool_calls table
  ▼
tool_calls table (partitioned by day)
  │
  │ every 5 min, Celery beat:
  ▼
Celery task: aggregate_hourly
  │
  │ INSERT INTO mcp_server_analytics_hourly
  ▼
mcp_server_analytics_hourly
  │
  │ read by GET /analytics
  ▼
Frontend (Recharts)
```

### 2.2 Data model

`tool_calls` is the raw event log. `mcp_server_analytics_hourly` is the pre-aggregated rollup.

Aggregation logic:
- Every 5 min: aggregate last hour of `tool_calls` → update `mcp_server_analytics_hourly` row
- Daily rollup: at 00:05 UTC, aggregate yesterday's hourly → `mcp_server_analytics_daily`
- Retention: drop partitions older than plan allows

---

## 3. Backend Changes

### 3.1 New files

```
app/services/analytics/
├── __init__.py
├── recorder.py              # record_tool_call
├── aggregator.py            # aggregate raw → rollups
├── queries.py               # read queries for dashboard
├── tasks.py                 # Celery tasks
└── partition_manager.py     # create/drop partitions

app/api/v1/endpoints/
└── analytics.py             # /servers/{id}/analytics/* (NEW)

app/schemas/
└── analytics.py             # AnalyticsOverview, ToolBreakdown, etc. (NEW)

app/models/
└── analytics.py             # ToolCall, AnalyticsRollupHourly, AnalyticsRollupDaily (NEW)

tests/
├── test_analytics_recorder.py    # 6 tests
├── test_analytics_aggregator.py  # 8 tests
├── test_analytics_queries.py     # 10 tests
└── test_analytics_endpoints.py   # 8 tests
```

### 3.2 Migration `0003_add_tool_calls.py`

```python
"""add tool_calls (partitioned) and analytics rollups"""
def upgrade():
    # tool_calls: raw events
    op.execute("""
        CREATE TABLE tool_calls (
            id UUID DEFAULT gen_random_uuid(),
            server_id UUID NOT NULL,
            tool_name VARCHAR(200) NOT NULL,
            status VARCHAR(20) NOT NULL,
            error_type VARCHAR(100),
            error_msg TEXT,
            latency_ms INT,
            response_size_bytes INT,
            client_name VARCHAR(100),
            called_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, called_at)
        ) PARTITION BY RANGE (called_at);
    """)
    op.create_index("idx_tool_calls_server_called", "tool_calls", ["server_id", "called_at"])
    op.create_index("idx_tool_calls_tool_called", "tool_calls", ["tool_name", "called_at"])
    op.create_index("idx_tool_calls_status_called", "tool_calls", ["status", "called_at"],
                    postgresql_where=sa.text("status != 'success'"))
    
    # Pre-create partitions for current + next month
    for i in range(-1, 31):
        date = date.today() + timedelta(days=i)
        partition_name = f"tool_calls_{date.strftime('%Y_%m_%d')}"
        start = date.strftime('%Y-%m-%d')
        end = (date + timedelta(days=1)).strftime('%Y-%m-%d')
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF tool_calls
            FOR VALUES FROM ('{start}') TO ('{end}');
        """)
    
    # Analytics rollups (not partitioned)
    op.create_table(
        "analytics_rollup_hourly",
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column("server_id", sa.UUID, sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(200), nullable=False),
        sa.Column("hour_bucket", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("total_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("timeout_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Integer, nullable=True),
        sa.Column("p95_latency_ms", sa.Integer, nullable=True),
        sa.Column("unique_clients", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("server_id", "tool_name", "hour_bucket", name="uq_rollup_hourly"),
    )
    op.create_index("idx_rollup_hourly_server_bucket", "analytics_rollup_hourly", ["server_id", "hour_bucket"])
    
    # Daily rollup
    op.create_table(
        "analytics_rollup_daily",
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column("server_id", sa.UUID, sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(200), nullable=False),
        sa.Column("day_bucket", sa.Date, nullable=False),
        sa.Column("total_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Integer, nullable=True),
        sa.Column("p95_latency_ms", sa.Integer, nullable=True),
        sa.UniqueConstraint("server_id", "tool_name", "day_bucket", name="uq_rollup_daily"),
    )
```

### 3.3 New models

```python
# app/models/analytics.py
class ToolCall(Base, TimestampMixin):
    __tablename__ = "tool_calls"  # partitioned
    __table_args__ = {"postgresql_partition_by": "RANGE (called_at)"}
    
    id: Mapped[UUID] = mapped_column(default=uuid4)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success | error | timeout
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class AnalyticsRollupHourly(Base):
    __tablename__ = "analytics_rollup_hourly"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    server_id: Mapped[UUID] = mapped_column(ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hour_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    timeout_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p95_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unique_clients: Mapped[int] = mapped_column(Integer, default=0)
```

### 3.4 Recorder service (the hot path)

```python
# app/services/analytics/recorder.py
class AnalyticsRecorder:
    async def record(self, server_id: UUID, tool_name: str, status: str, latency_ms: int | None, response_size: int | None, error_msg: str | None, client_name: str | None) -> None:
        # Sanitize error_msg (strip credentials)
        sanitized = sanitize_error(error_msg) if error_msg else None
        
        # Truncate error_msg to 500 chars
        if sanitized and len(sanitized) > 500:
            sanitized = sanitized[:500]
        
        async with async_session_factory() as session:
            record = ToolCall(
                server_id=server_id,
                tool_name=tool_name,
                status=status,
                error_type=classify_error(error_msg) if error_msg else None,
                error_msg=sanitized,
                latency_ms=latency_ms,
                response_size_bytes=response_size,
                client_name=client_name,
            )
            session.add(record)
            await session.commit()


def sanitize_error(error_msg: str) -> str:
    """Strip credentials from error messages before logging."""
    # Match Bearer tokens, API keys, Basic auth, query params with key/token
    patterns = [
        (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED]"),
        (r"Basic\s+[A-Za-z0-9+/=]+", "Basic [REDACTED]"),
        (r"(?i)(api[_-]?key|token|secret|password)=[^\s&]+", r"\1=[REDACTED]"),
        (r"(?i)authorization[:\s]+[^\s]+", "Authorization: [REDACTED]"),
    ]
    result = error_msg
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    return result
```

### 3.5 Aggregator

```python
@celery_app.task(name="app.services.analytics.tasks.aggregate_hourly")
def aggregate_hourly():
    """Every 5 min, aggregate last hour of tool_calls into rollup."""
    async def run():
        now = datetime.utcnow()
        hour_start = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        
        async with async_session_factory() as session:
            # Aggregate raw events
            result = await session.execute(text("""
                INSERT INTO analytics_rollup_hourly 
                    (id, server_id, tool_name, hour_bucket, total_calls, success_count, error_count, timeout_count, avg_latency_ms, p95_latency_ms, unique_clients)
                SELECT 
                    gen_random_uuid(),
                    server_id,
                    tool_name,
                    DATE_TRUNC('hour', called_at) as hour_bucket,
                    COUNT(*) as total_calls,
                    COUNT(*) FILTER (WHERE status = 'success') as success_count,
                    COUNT(*) FILTER (WHERE status = 'error') as error_count,
                    COUNT(*) FILTER (WHERE status = 'timeout') as timeout_count,
                    AVG(latency_ms)::INT as avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)::INT as p95_latency_ms,
                    COUNT(DISTINCT client_name) as unique_clients
                FROM tool_calls
                WHERE called_at >= :start AND called_at < :end
                GROUP BY server_id, tool_name, DATE_TRUNC('hour', called_at)
                ON CONFLICT (server_id, tool_name, hour_bucket)
                DO UPDATE SET
                    total_calls = EXCLUDED.total_calls,
                    success_count = EXCLUDED.success_count,
                    error_count = EXCLUDED.error_count,
                    timeout_count = EXCLUDED.timeout_count,
                    avg_latency_ms = EXCLUDED.avg_latency_ms,
                    p95_latency_ms = EXCLUDED.p95_latency_ms,
                    unique_clients = EXCLUDED.unique_clients;
            """), {"start": hour_start, "end": hour_end})
            await session.commit()
    
    asyncio.run(run())
```

### 3.6 Query layer

```python
class AnalyticsQueries:
    async def get_overview(self, server_id: UUID, range: str) -> AnalyticsOverview:
        """Returns: total_calls, unique_sessions, error_rate, avg_response_time, estimated_token_saved"""
        # Use the rollup table, not raw events
        days = {"7d": 7, "30d": 30, "90d": 90}[range]
        start = datetime.utcnow() - timedelta(days=days)
        
        # Aggregate from rollup_hourly
        result = await session.execute(text("""
            SELECT 
                SUM(total_calls) as total,
                AVG(CASE WHEN total_calls > 0 THEN success_count::FLOAT / total_calls ELSE 1 END) as success_rate,
                AVG(avg_latency_ms) as avg_latency
            FROM analytics_rollup_hourly
            WHERE server_id = :server_id AND hour_bucket >= :start
        """), {"server_id": server_id, "start": start})
        
        # Unique sessions: count distinct client_name from rollup
        ...
        
        # Token saved estimate: ~500 tokens per call (rough)
        estimated_tokens_saved = total * 500
        
        return AnalyticsOverview(
            total_calls=total,
            unique_sessions=...,
            error_rate=...,
            avg_response_time_ms=...,
            estimated_token_cost_saved=estimated_tokens_saved,
        )
    
    async def get_tool_breakdown(self, server_id: UUID, range: str) -> list[ToolBreakdownItem]:
        ...
    
    async def get_error_log(self, server_id: UUID, range: str, limit: int = 100) -> list[ErrorLogItem]:
        # Read from tool_calls (raw, since errors are rare)
        ...
    
    async def get_client_breakdown(self, server_id: UUID, range: str) -> list[ClientBreakdownItem]:
        ...
    
    async def get_time_series(self, server_id: UUID, range: str, granularity: str) -> list[TimeSeriesPoint]:
        # Read from appropriate rollup based on granularity
        ...
```

### 3.7 Description Performance tracking (unique feature)

```python
class DescriptionPerformanceTracker:
    """Track if user's manual edits to AI-enhanced descriptions actually improve call rates."""
    
    async def get_performance(self, server_id: UUID, tool_name: str) -> DescriptionPerformance:
        # Find the most recent edit to the tool's description
        edit = await session.execute(text("""
            SELECT changed_at, previous_value, new_value
            FROM tool_edit_history
            WHERE server_id = :server_id AND tool_name = :tool_name AND field = 'description'
            ORDER BY changed_at DESC LIMIT 1
        """), {"server_id": server_id, "tool_name": tool_name})
        
        if not edit:
            return DescriptionPerformance(no_edit=True)
        
        # Compute call rate 7 days before vs 7 days after
        edit_time = edit.changed_at
        before = await self._get_call_rate(server_id, tool_name, edit_time - timedelta(days=7), edit_time)
        after = await self._get_call_rate(server_id, tool_name, edit_time, edit_time + timedelta(days=7))
        
        if before == 0:
            delta_pct = None
        else:
            delta_pct = ((after - before) / before) * 100
        
        return DescriptionPerformance(
            tool_name=tool_name,
            edited_at=edit_time,
            before_call_rate=before,
            after_call_rate=after,
            delta_pct=delta_pct,
            message=f"After description update on {edit_time.date()}, this tool's call rate {'increased' if delta_pct > 0 else 'decreased'} {abs(delta_pct):.0f}%",
        )
```

For v1.0, this requires a `tool_edit_history` table to track edits. Add to migration `0002_add_ai_enhancement.py`:
```python
op.create_table(
    "tool_edit_history",
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("server_id", sa.UUID, sa.ForeignKey("mcp_servers.id", ondelete="CASCADE")),
    sa.Column("tool_name", sa.String(200), nullable=False),
    sa.Column("field", sa.String(100), nullable=False),
    sa.Column("previous_value", sa.Text, nullable=True),
    sa.Column("new_value", sa.Text, nullable=True),
    sa.Column("changed_by", sa.String(20), nullable=False),  # 'ai' | 'user'
    sa.Column("changed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
)
```

Whenever a tool's description/parameters/return_description is updated, insert a row here.

---

## 4. Frontend Changes

### 4.1 New components

```
src/components/analytics/
├── analytics-page.tsx                # Main dashboard (NEW)
├── date-range-picker.tsx             # 7d / 30d / 90d selector
├── overview-cards.tsx                # Top row: total, sessions, error rate, latency
├── tool-breakdown-table.tsx          # Per-tool stats
├── error-log.tsx                     # Last 100 errors
├── client-breakdown-pie.tsx          # Claude Desktop vs Cursor
├── time-series-chart.tsx             # Recharts line chart
├── csv-export-button.tsx             # Download CSV
├── description-performance-panel.tsx # Unique feature
└── empty-analytics.tsx               # "No calls yet"
```

### 4.2 New hooks

```typescript
// src/hooks/use-analytics.ts (NEW)
export function useAnalyticsOverview(serverId: string, range: '7d' | '30d' | '90d') { ... }
export function useToolBreakdown(serverId: string, range: string) { ... }
export function useErrorLog(serverId: string, range: string, page: number) { ... }
export function useClientBreakdown(serverId: string, range: string) { ... }
export function useTimeSeries(serverId: string, range: string, granularity: 'hour' | 'day') { ... }
export function useDescriptionPerformance(serverId: string, toolName: string) { ... }
```

### 4.3 New route

`/dashboard/servers/[slug]/analytics/page.tsx`

---

## 5. Database / Migration Plan

Migration `0003_add_tool_calls.py` (specified above).

---

## 6. Environment Variables

No new env vars.

---

## 7. Observability

```python
logger.info("tool_call_recorded", server_id=server_id, tool=tool_name, status=status, latency_ms=latency_ms)
logger.info("analytics_aggregated", hour_bucket=hour_start.isoformat(), rows_updated=count)
```

---

## 8. Edge Cases

| Case | Response |
|---|---|
| tool_calls partition missing for today | Celery task creates it; recorder logs warning |
| Aggregation runs late (worker down) | Next run aggregates the gap |
| Server deleted with old tool_calls | Cascade delete handles it |
| User has 7d retention but query asks for 30d | Return 403 or 400, "Upgrade to Pro for 30-day retention" |
| Recording fails (DB down) | Don't fail the gateway request; just log error |
| Error msg contains 10KB stack trace | Truncate to 500 chars in recorder |
| Same tool called 10K times in 1 hour | Aggregation handles it; rollup updated |

---

## 9. Definition of Done

- [ ] Migration `0003_add_tool_calls.py` creates partitions
- [ ] Recorder fires from gateway on every tool call
- [ ] Aggregator runs every 5 min via Celery beat
- [ ] All 6 endpoints work
- [ ] Frontend dashboard renders all panels
- [ ] CSV export works
- [ ] Description performance tracking works
- [ ] No parameter values ever appear in tool_calls
- [ ] Playwright E2E: call a tool 10 times, see it in analytics
- [ ] Performance: overview endpoint returns in <100ms (uses rollup)

---

## 10. Build Sequence

1. Migrations
2. Models
3. Recorder (writes to tool_calls)
4. Wire recorder into gateway
5. Aggregator Celery task
6. Celery beat schedule
7. Partition manager
8. Query layer
9. Endpoints
10. Description performance tracker
11. Frontend components + hooks + route
12. E2E tests
13. Manual: deploy a server, call it 10 times from playground, see analytics

---

*See `features/03-FEATURE-AI-DESCRIPTION-ENGINE.md` for how tool edits trigger edit history.*
