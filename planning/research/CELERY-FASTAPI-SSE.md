# Celery, FastAPI, SSE, WebSocket — Async Patterns Reference

> **For AI agents:** Reference for background job processing (Celery), real-time streaming (SSE), and bidirectional communication (WebSocket) in the MCPForge backend. Used by F1 (Celery), F2 (Celery + SSE), F3 (WebSocket playground), F4 (SSE), F5/F6/F7 (Celery).

---

## 1. Celery 5.4+ — Async Job Processing

### 1.1 Why Celery for MCPForge

For the AI Description Engine, security scanner, and analytics aggregation, we need:
- Long-running jobs (5-30s per description enhancement)
- Batch processing (200+ endpoints per spec)
- Retry on API failures (429, 500)
- Queue isolation (AI vs scanner vs analytics)
- Monitoring (Flower)
- Priority queues

Celery wins over alternatives for this:

| Feature | Celery | RQ | ARQ | Dramatiq |
|---|---|---|---|---|
| Maturity | 15+ years | 10+ years | 5+ years | 8+ years |
| Redis broker | ✅ | ✅ | ✅ | ✅ |
| Priority queues | ✅ | ❌ | ❌ | ✅ (basic) |
| Rate limiting | ✅ | ❌ | ❌ | ❌ |
| Task acks_late | ✅ | ✅ | ✅ | ✅ |
| Monitoring (Flower) | ✅ | ✅ | ❌ | ✅ |
| Time limits | ✅ (soft+hard) | ⚠️ | ⚠️ | ✅ |
| Concurrency | prefork/threads/async | fork | async-only | fork |
| Result backend | Redis/DB/S3 | Redis | Redis | Redis |

**MCPForge:** Use **Celery 5.4+ with Redis broker**.

### 1.2 Configuration

```python
# app/core/celery_app.py
from celery import Celery
from kombu import Queue

celery_app = Celery('mcpforge', broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_expires=3600,  # 1 hour
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_queue='default',
    task_queues=(
        Queue('high_priority', routing_key='high.*'),
        Queue('default', routing_key='default.*'),
        Queue('ai', routing_key='ai.*'),                # AI Engine
        Queue('scanner', routing_key='scanner.*'),     # Security Scanner
        Queue('analytics', routing_key='analytics.*'), # Analytics aggregation
    ),
    task_routes={
        'app.services.ai_description.tasks.*': {'queue': 'ai'},
        'app.services.security_scanner.tasks.*': {'queue': 'scanner'},
        'app.services.analytics.tasks.*': {'queue': 'analytics'},
    },
    beat_schedule={
        'aggregate-analytics': {
            'task': 'app.services.analytics.tasks.aggregate_hourly',
            'schedule': crontab(minute=5),  # every hour at :05
        },
        'create-tool-call-partitions': {
            'task': 'app.services.analytics.tasks.create_partitions',
            'schedule': crontab(hour=0, minute=30),  # daily
        },
        'cleanup-revoked-tokens': {
            'task': 'app.services.auth.tasks.cleanup_revoked_tokens',
            'schedule': crontab(hour=2, minute=0),  # daily
        },
    },
    task_soft_time_limit=300,  # 5 min default
    task_time_limit=330,       # 5.5 min default
    worker_max_tasks_per_child=10000,
    worker_prefetch_multiplier=1,
)
```

### 1.3 Task Pattern with Retry

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(RateLimitError, APIConnectionError, APITimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    acks_late=True,
)
async def enhance_tool_description(self, server_id: str, tool_name: str) -> dict:
    """Enhance a single tool description via LLM."""
    logger = get_logger(__name__)
    request_id = self.request.id
    logger.info("enhance_tool_start", server_id=server_id, tool_name=tool_name, request_id=request_id)
    
    try:
        async with async_session_factory() as session:
            # ... actual work ...
            result = await llm_client.chat_completion(...)
            # ... write back to DB ...
            await session.commit()
        return result
    except Exception as e:
        logger.error("enhance_tool_failed", server_id=server_id, tool_name=tool_name, error=str(e), request_id=request_id)
        raise self.retry(exc=e)
```

### 1.4 Running Celery

**Worker:**
```bash
celery -A app.core.celery_app worker -Q ai,scanner,analytics -l info --concurrency=2
```

**Beat (for scheduled tasks):**
```bash
celery -A app.core.celery_app beat -l info
```

**Flower (monitoring, optional):**
```bash
celery -A app.core.celery_app flower --port=5555
```

**MCPForge deployment on Render:**
- Worker: separate Docker service
- Beat: separate Docker service
- Flower: optional, can be enabled for debugging

### 1.5 Testing Celery Tasks

```python
# Use eager mode for unit tests
@pytest.fixture
def celery_eager():
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = False

async def test_enhance_task(celery_eager):
    result = enhance_tool_description.apply(args=(str(server_id), "search_products"))
    assert result.successful()
    # Verify DB state
```

## 2. Server-Sent Events (SSE) in FastAPI

### 2.1 When to use SSE vs WebSocket
- **SSE:** Server → Client streaming (one-way), HTTP-based, auto-reconnect, simple
- **WebSocket:** Bidirectional, persistent connection, custom protocol

**MCPForge uses both:**
- **SSE** for the MCP gateway (per MCP spec) and build progress (F2)
- **WebSocket** for the playground (F3) for bidirectional tool calls

### 2.2 SSE with sse-starlette

**Add to pyproject.toml:**
```toml
"sse-starlette>=2.1.0"
```

**Basic SSE endpoint:**
```python
from sse_starlette.sse import EventSourceResponse
from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/stream")
async def stream(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            yield {"event": "message", "data": "hello"}
            await asyncio.sleep(1)
    
    return EventSourceResponse(
        event_generator(),
        ping=15,  # heartbeat every 15s
        headers={"X-Accel-Buffering": "no"}  # nginx compat
    )
```

### 2.3 SSE for Build Progress (F2 pattern)

```python
@app.get("/api/v1/servers/{id}/build-status")
async def build_status_sse(
    request: Request,
    server_id: UUID,
    current_user: User = Depends(get_current_user_required),
):
    """Stream build progress events via SSE."""
    
    async def event_generator():
        # Send initial event
        yield {
            "event": "connected",
            "data": json.dumps({"server_id": str(server_id)}),
        }
        
        # Subscribe to events
        queue = await sse_manager.subscribe(str(server_id))
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {
                        "event": event.get("event", "message"),
                        "data": json.dumps(event),
                        "id": str(uuid.uuid4()),
                    }
                except asyncio.TimeoutError:
                    # Heartbeat
                    yield {"event": "ping", "data": ""}
        finally:
            await sse_manager.unsubscribe(str(server_id), queue)
    
    return EventSourceResponse(event_generator(), ping=15)
```

### 2.4 SSE Manager (Redis pub/sub)

```python
# app/core/sse.py
import asyncio
import json
from collections import defaultdict
from app.core.redis import get_redis

class SSEManager:
    """Pub/sub for SSE events keyed by server_id."""
    
    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._listener_task = None
    
    async def publish(self, server_id: str, event: dict) -> None:
        """Publish an event to all subscribers (via Redis)."""
        r = await get_redis()
        await r.publish(f"sse:{server_id}", json.dumps(event, default=str))
    
    async def subscribe(self, server_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        self._subscribers[server_id].add(queue)
        # Ensure listener is running
        if not self._listener_task or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listener())
        return queue
    
    async def unsubscribe(self, server_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[server_id].discard(queue)
    
    async def _listener(self):
        """Background task that fans out Redis pub/sub to local queues."""
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.psubscribe("sse:*")
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            channel = message["channel"]
            if isinstance(channel, bytes):
                channel = channel.decode()
            server_id = channel.split(":", 1)[1]
            data = json.loads(message["data"])
            for queue in list(self._subscribers.get(server_id, set())):
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass  # drop if consumer is slow

sse_manager = SSEManager()
```

### 2.5 Frontend SSE consumption

```typescript
export function useBuildStatusSSE(serverId: string) {
  const [events, setEvents] = useState<BuildEvent[]>([]);
  const [status, setStatus] = useState<'idle' | 'running' | 'complete' | 'error'>('idle');
  
  useEffect(() => {
    const eventSource = new EventSource(`${API_URL}/api/v1/servers/${serverId}/build-status`, {
      withCredentials: true,  // send httpOnly cookies
    });
    
    eventSource.addEventListener('connected', (e) => {
      setStatus('running');
    });
    
    eventSource.addEventListener('tool_enhanced', (e) => {
      const event = JSON.parse(e.data);
      setEvents((prev) => [...prev, event]);
    });
    
    eventSource.addEventListener('ai_complete', (e) => {
      setStatus('complete');
      eventSource.close();
    });
    
    eventSource.addEventListener('error', (e) => {
      setStatus('error');
    });
    
    return () => eventSource.close();
  }, [serverId]);
  
  return { events, status };
}
```

### 2.6 SSE Gotchas

1. **Nginx config:** `proxy_buffering off; proxy_read_timeout 120s;`
2. **Cloudflare free:** 100s proxy timeout — SSE may drop
3. **Vercel:** 30s idle timeout — send heartbeat every 10-15s
4. **Connection limits:** ~10K per uvicorn worker
5. **Resume support:** Send `id:` field, client uses `Last-Event-ID` for reconnect

## 3. WebSocket in FastAPI

### 3.1 Basic WebSocket

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/playground/{slug}")
async def playground_websocket(
    websocket: WebSocket,
    slug: str,
    token: str = Query(...),
):
    # Auth via token query param
    try:
        payload = decode_access_token(token)
        user_id = payload["sub"]
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_json()
            # Process message
            response = await handle_message(...)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        pass
```

### 3.2 Auth considerations
- Cookies don't work with WebSocket (browser doesn't send them on `new WebSocket()`)
- Pass JWT in query param: `?token=...`
- Or use a subprotocol header (less common)
- For production, validate token, then accept connection

### 3.3 Nginx for WebSocket
```nginx
location /ws/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;  # 24h
    proxy_send_timeout 86400;
}
```

## 4. Database Partitioning (PostgreSQL)

For `tool_calls` table (F6) partitioned by day:

```python
# Create partition for a specific date
def create_partition(date: date) -> None:
    partition_name = f"tool_calls_{date.strftime('%Y_%m_%d')}"
    start = date.strftime('%Y-%m-%d')
    end = (date + timedelta(days=1)).strftime('%Y-%m-%d')
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF tool_calls
        FOR VALUES FROM ('{start}') TO ('{end}');
    """)

# Drop old partitions (retention)
def drop_old_partitions(retention_days: int) -> None:
    cutoff = date.today() - timedelta(days=retention_days)
    op.execute(f"DROP TABLE IF EXISTS tool_calls_{cutoff.strftime('%Y_%m_%d')};")
```

**Celery beat** runs `create_partitions` daily to ensure next 7 days exist.

## 5. Async Database Sessions

Always use `AsyncSession` with `async_session_factory`:

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Usage in Celery task
async def some_task():
    async with async_session_factory() as session:
        # ... use session ...
        await session.commit()
```

## 6. Structured Logging

```python
# app/core/logging.py
import structlog
import logging

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        # Strip sensitive data
        strip_sensitive_processor,
        # JSON in prod, colored in dev
        structlog.dev.ConsoleRenderer() if settings.is_development else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# Sensitive data filter
SENSITIVE_KEYS = {"authorization", "api_key", "password", "secret", "token", "cookie", "bearer"}

def strip_sensitive_processor(logger, method_name, event_dict):
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
        # Recursively check nested values
        if isinstance(event_dict[key], str):
            for pattern in SENSITIVE_PATTERNS:
                if pattern in event_dict[key].lower():
                    event_dict[key] = "[REDACTED]"
    return event_dict
```

## 7. Backpressure & Connection Pooling

For 100K+ concurrent SSE connections:
- Each connection uses ~5-10KB memory
- Use Redis pub/sub for broadcasting across multiple workers
- Load balancers need SSE stickiness (cookie-based) or Redis-backed sessions
- Practical limit: ~10K connections per uvicorn worker

## 8. References

- **Celery docs:** https://docs.celeryq.dev/
- **Celery best practices:** https://docs.celeryq.dev/en/stable/tutorials/task-cookbook.html
- **sse-starlette:** https://github.com/sysid/sse-starlette
- **FastAPI WebSockets:** https://fastapi.tiangolo.com/advanced/websockets/
- **structlog:** https://www.structlog.org/
- **SQLAlchemy 2.0 async:** https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **PostgreSQL partitioning:** https://www.postgresql.org/docs/current/ddl-partitioning.html
- **MCP transports:** https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
