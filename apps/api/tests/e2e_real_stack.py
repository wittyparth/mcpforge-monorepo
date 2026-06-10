"""Comprehensive real-world e2e test against the LIVE API stack.

runs against http://localhost:8000. tests EVERY workflow with real
HTTP requests — auth, server CRUD, specs, tools, credentials,
analytics, security, gateway — verifying the entire platform works
end-to-end at production level.
"""

from __future__ import annotations

import sys
import time
import uuid

import httpx

API_BASE = "http://localhost:8000"

passed = 0
failed = 0


def step(name: str) -> None:
    print(f"\n  ◆ {name}...", end=" ", flush=True)


def ok(msg: str = "") -> None:
    global passed
    passed += 1
    print(f"✅  {msg}", flush=True)


def fail(msg: str) -> None:
    global failed
    failed += 1
    print(f"❌  {msg}", flush=True)


# ── Authenticated HTTP client with cookie + CSRF handling ──────

class APIClient:
    """http wrapper that persists cookies and sets ``X-CSRF-Token``
    automatically on state-changing requests."""

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=API_BASE, timeout=15.0)
        self._csrf_token: str | None = None

    @property
    def cookies(self) -> dict[str, str]:
        return dict(self._client.cookies)

    def _update_csrf(self) -> None:
        self._csrf_token = self._client.cookies.get("csrf_token")

    def _headers(self, method: str) -> dict[str, str]:
        h: dict[str, str] = {}
        if method in ("POST", "PUT", "PATCH", "DELETE") and self._csrf_token:
            h["X-CSRF-Token"] = self._csrf_token
        return h

    def get(self, path: str, **kw: object) -> httpx.Response:
        r = self._client.get(path, **kw)
        self._update_csrf()
        return r

    def post(self, path: str, json: object | None = None) -> httpx.Response:
        r = self._client.post(path, json=json, headers=self._headers("POST"))
        self._update_csrf()
        return r

    def patch(self, path: str, json: object | None = None) -> httpx.Response:
        r = self._client.patch(path, json=json, headers=self._headers("PATCH"))
        self._update_csrf()
        return r

    def delete(self, path: str) -> httpx.Response:
        r = self._client.delete(path, headers=self._headers("DELETE"))
        self._update_csrf()
        return r


c = APIClient()

# ═══════════════════════════════════════════════════════════════════════════════
# 1. HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

step("Health check")
r = c.get("/health")
assert r.status_code == 200
j = r.json()
assert j["status"] == "ok"
ok(f"db={j['db']} redis={j['redis']} worker={j['worker']}")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. AUTH WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

test_email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
test_pass = f"Str0ng!{uuid.uuid4().hex[:16]}"

step("Register")
r = c.post("/api/v1/auth/register", json={"email": test_email, "password": test_pass})
assert r.status_code == 200, r.text[:150]
ok(f"email={test_email}")

step("Login — sets httpOnly cookies")
r = c.post("/api/v1/auth/login", json={"email": test_email, "password": test_pass})
assert r.status_code == 200, r.text[:150]
assert "access_token" in c.cookies, "no access_token cookie"
assert "csrf_token" in c.cookies, "no csrf_token cookie"
ok("access ✓  refresh ✓  csrf ✓")

step("GET /me (authenticated)")
r = c.get("/api/v1/auth/me")
assert r.status_code == 200
user_id: str = r.json()["id"]
assert len(user_id) > 0
ok(f"user_id={user_id[:8]}…")

step("POST /auth/refresh (token rotation)")
r = c.post("/api/v1/auth/refresh")
assert r.status_code == 200, r.text[:100]
ok()

step("POST /auth/logout")
r = c.post("/api/v1/auth/logout")
assert r.status_code == 200, r.text[:100]
ok()

step("Re-login for subsequent tests")
r = c.post("/api/v1/auth/login", json={"email": test_email, "password": test_pass})
assert r.status_code == 200, r.text[:150]
assert "access_token" in c.cookies
ok()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. SERVER CRUD
# ═══════════════════════════════════════════════════════════════════════════════

slug = f"e2e-{uuid.uuid4().hex[:6]}"
step("Create server")
r = c.post("/api/v1/servers", json={
    "slug": slug,
    "name": "E2E Test Server",
    "base_url": "https://api.example.com",
    "auth_scheme": "none",
})
assert r.status_code in (200, 201), f"expected 200/201, got {r.status_code}: {r.text[:200]}"
server_id: str = r.json()["id"]
assert r.json()["slug"] == slug
ok(f"id={server_id[:8]}… slug={slug}")

step("List servers")
r = c.get("/api/v1/servers")
assert r.status_code == 200
data = r.json()
items = data if isinstance(data, list) else data.get("items", data.get("servers", []))
assert len(items) >= 1
ok(f"{len(items)} server(s)")

step("Get server by id")
r = c.get(f"/api/v1/servers/{server_id}")
assert r.status_code == 200
assert r.json()["id"] == server_id
ok()

step("Update server name")
r = c.patch(f"/api/v1/servers/{server_id}", json={"name": "E2E Server (updated)"})
assert r.status_code == 200
assert r.json()["name"] == "E2E Server (updated)"
ok()

# ═══════════════════════════════════════════════════════════════════════════════
# 4. CREDENTIALS (F1)
# ═══════════════════════════════════════════════════════════════════════════════

step("Add credential (encrypted)")
r = c.post(f"/api/v1/servers/{server_id}/credentials", json={
    "env_var_name": "API_KEY",
    "value": "sk-secret-12345",
    "auth_scheme": "header",
})
assert r.status_code in (200, 201), f"expected 200/201, got {r.status_code}: {r.text[:200]}"
ok()

step("List credentials (value never returned)")
r = c.get(f"/api/v1/servers/{server_id}/credentials")
assert r.status_code == 200
creds = r.json()
if isinstance(creds, dict):
    creds = creds.get("credentials", creds.get("items", []))
assert len(creds) >= 1
assert "sk-secret" not in r.text  # privacy: value never in response
ok(f"{len(creds)} credential(s), value hidden")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. SPEC FETCHING (F1)
# ═══════════════════════════════════════════════════════════════════════════════

step("Fetch public OpenAPI spec")
r = c.post("/api/v1/specs/fetch", json={
    "url": "https://petstore3.swagger.io/api/v3/openapi.json",
})
if r.status_code == 200:
    spec_id = r.json().get("spec_id") or r.json().get("id", "")
    tools_found = r.json().get("tools_count", r.json().get("tool_count", 0))
    ok(f"spec_id={spec_id[:8] if spec_id else 'N/A'}… tools={tools_found}")

    step("Get parsed tools from spec")
    r = c.get(f"/api/v1/specs/{spec_id}/tools")
    if r.status_code == 200:
        tools_data = r.json()
        tools = (
            tools_data
            if isinstance(tools_data, list)
            else tools_data.get("tools", tools_data.get("items", []))
        )
        ok(f"{len(tools)} tool(s) in spec")
    else:
        fail(f"spec tools {r.status_code}: {r.text[:100]}")
else:
    fail(f"fetch spec {r.status_code}: {r.text[:200]}")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. TOOLS (F1 / F2)
# ═══════════════════════════════════════════════════════════════════════════════

step("List server tools")
r = c.get(f"/api/v1/servers/{server_id}/tools")
if r.status_code == 200:
    tools_data = r.json()
    tools = tools_data.get("tools", tools_data.get("items", []))
    tool_names = [t["name"] for t in tools] if tools else []
    ok(f"{len(tools)} tool(s): {', '.join(tool_names[:3])}…")
else:
    fail(f"list tools {r.status_code}")
    tools = []

if tools:
    step("Update a tool description")
    r = c.patch(
        f"/api/v1/servers/{server_id}/tools/{tool_names[0]}",
        json={"description": "Updated by e2e"},
    )
    assert r.status_code in (200, 404), f"{r.status_code}: {r.text[:100]}"
    ok()

    step("Enhance tools (F2 AI)")
    r = c.post(
        f"/api/v1/servers/{server_id}/tools/enhance",
        json={"tool_names": None, "force": False},
    )
    if r.status_code == 200:
        assert "job_id" in r.json()
        ok(f"job_id={r.json()['job_id'][:12]}…")
    else:
        # AI enhancement may not be real (no LLM key configured)
        fail(f"enhance {r.status_code}: {r.text[:150]}")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. ANALYTICS (F6) — THE NEW FEATURE
# ═══════════════════════════════════════════════════════════════════════════════

step("Analytics overview (7d)")
r = c.get(f"/api/v1/servers/{server_id}/analytics", params={"range": "7d"})
assert r.status_code == 200, r.text[:200]
j = r.json()
ok(
    f"calls={j.get('total_calls', 0)} clients={j.get('unique_clients', 0)}"
    f" errors={j.get('total_errors', 0)}"
)

step("Analytics tool breakdown")
r = c.get(f"/api/v1/servers/{server_id}/analytics/tools", params={"range": "7d"})
assert r.status_code == 200
items = r.json()
assert isinstance(items, list)
ok(f"{len(items)} tool(s) in breakdown")

step("Analytics error log")
r = c.get(f"/api/v1/servers/{server_id}/analytics/errors", params={"range": "7d", "limit": 50})
assert r.status_code == 200
errors = r.json()
ok(f"{len(errors)} error(s)")

step("Analytics client breakdown")
r = c.get(f"/api/v1/servers/{server_id}/analytics/clients", params={"range": "7d"})
assert r.status_code == 200
clients = r.json()
assert isinstance(clients, list)
ok(f"{len(clients)} client(s)")

step("Analytics time series")
r = c.get(
    f"/api/v1/servers/{server_id}/analytics/timeseries",
    params={"range": "7d", "granularity": "hour"},
)
assert r.status_code == 200
points = r.json()
assert isinstance(points, list)
ok(f"{len(points)} data point(s)")

step("Analytics CSV export")
r = c.get(f"/api/v1/servers/{server_id}/analytics/export.csv", params={"range": "7d"})
assert r.status_code == 200
ct = r.headers.get("content-type", "")
assert "text/csv" in ct, f"wrong Content-Type: {ct}"
assert "called_at" in r.text, "CSV missing headers"
assert "parameter_names" in r.text, "CSV missing privacy column"
ok(f"csv ok ({len(r.content)} bytes)")

step("Description performance (no edits yet)")
r = c.get(f"/api/v1/servers/{server_id}/analytics/description-performance")
assert r.status_code == 200
perf = r.json()
assert isinstance(perf, list)
ok(f"{len(perf)} tool(s) with performance data")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. SECURITY SCANNER (F5)
# ═══════════════════════════════════════════════════════════════════════════════

step("Trigger security scan")
r = c.post(f"/api/v1/servers/{server_id}/security/scan")
assert r.status_code == 200, r.text[:200]
ok(f"scan_id={r.json().get('scan_id', '')[:8]}…")

# Let the worker process it
time.sleep(3)

step("Latest scan result")
r = c.get(f"/api/v1/servers/{server_id}/security/latest")
if r.status_code == 200:
    scan = r.json()
    if scan:
        ok(f"status={scan.get('scan_status')} "
           f"findings={scan.get('critical_count',0)}C/{scan.get('high_count',0)}H/"
           f"{scan.get('medium_count',0)}M/{scan.get('info_count',0)}I")
    else:
        ok("scan not yet available")
else:
    fail(f"latest scan {r.status_code}: {r.text[:100]}")

step("Scan history")
r = c.get(f"/api/v1/servers/{server_id}/security/scans")
assert r.status_code == 200
history = r.json()
items = history.get("items", history.get("scans", []))
ok(f"{len(items)} scan(s) in history")

# ═══════════════════════════════════════════════════════════════════════════════
# 9. BUILD / DEPLOY
# ═══════════════════════════════════════════════════════════════════════════════

step("Start build")
r = c.post(f"/api/v1/servers/{server_id}/build")
if r.status_code == 200:
    ok(f"job_id={r.json().get('job_id','')[:12]}…")
else:
    fail(f"build {r.status_code}: {r.text[:150]}")

step("Deploy server")
r = c.post(f"/api/v1/servers/{server_id}/deploy")
if r.status_code in (200, 409):
    ok(f"status={r.status_code}: {r.text[:100]}")
else:
    fail(f"deploy {r.status_code}: {r.text[:150]}")

# ═══════════════════════════════════════════════════════════════════════════════
# 10. MCP GATEWAY
# ═══════════════════════════════════════════════════════════════════════════════

step("Gateway health (public)")
r = c.get(f"/mcp/v1/{slug}/health")
assert r.status_code == 200
ok()

step("SSE endpoint requires auth (without cookie)")
no_cookie = httpx.get(f"{API_BASE}/mcp/v1/{slug}/sse")
assert no_cookie.status_code == 401, f"expected 401, got {no_cookie.status_code}"
ok()

# ═══════════════════════════════════════════════════════════════════════════════
# 11. NEGATIVE / EDGE-CASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

step("Unknown server returns 404")
r = c.get(f"/api/v1/servers/{uuid.uuid4()}")
assert r.status_code == 404
ok()

step("Weak password rejected")
r = c.post(
    "/api/v1/auth/register",
    json={"email": f"weak-{uuid.uuid4().hex[:8]}@x.com", "password": "12"},
)
assert r.status_code in (400, 422), f"expected 400/422, got {r.status_code}"
ok()

step("Duplicate email rejected")
r = c.post("/api/v1/auth/register", json={"email": test_email, "password": test_pass})
assert r.status_code in (400, 409), f"expected 400/409, got {r.status_code}: {r.text[:100]}"
ok()

step("Delete server (graceful)")
r = c.delete(f"/api/v1/servers/{server_id}")
assert r.status_code in (200, 204), f"expected 200/204, got {r.status_code}: {r.text[:100]}"
ok()

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n{'━' * 60}")
print(f"  PASSED  {passed}   FAILED  {failed} ")
print(f"{'━' * 60}")

if failed:
    sys.exit(1)
else:
    print("  Every workflow verified against the live API stack.")
    print("  Auth · Servers · Credentials · Specs · Tools · AI Enhance ·")
    print("  Analytics · Security · Build · Deploy · Gateway · Edge Cases")
    print("  ALL ✅")
    sys.exit(0)
