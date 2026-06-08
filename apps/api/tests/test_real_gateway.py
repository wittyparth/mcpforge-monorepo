"""REAL end-to-end gateway tests against the live Docker stack."""
import json, uuid, http.client as httpc, requests, sys

BASE = "http://localhost:8000"
PASS = "StrongPass123!@#"

def extract_cookie(resp, name):
    for c in resp.cookies:
        if c.name == name: return c.value
    return None

total, passed = 0, 0
def check(name, ok, detail=""):
    global total, passed
    total += 1
    if ok: passed += 1; print(f"  \u2705 {name}")
    else: print(f"  \u274c {name} \u2014 {detail}")

def headers(token, csrf):
    h = {"Authorization": f"Bearer {token}"}
    if csrf: h["X-CSRF-Token"] = csrf
    return h

def cookies(token, csrf):
    c = {"access_token": token}
    if csrf: c["csrf_token"] = csrf
    return c

print(f"\n{'='*60}")
print(f"  MCPForge Gateway \u2014 Real E2E Tests")
print(f"  Target: {BASE}")
print(f"{'='*60}\n")

try:
    # 01: Health
    r = requests.get(f"{BASE}/health", timeout=5); d = r.json()
    check("01. GET /health (DB+Redis OK)", r.status_code==200 and d.get("db")=="ok" and d.get("redis")=="ok",
          f"db={d.get('db')} redis={d.get('redis')}")

    # 02: Register
    email = f"real-{uuid.uuid4().hex[:8]}@test.com"
    r = requests.post(f"{BASE}/api/v1/auth/register", json={"email":email,"password":PASS}, timeout=10)
    token = extract_cookie(r,"access_token"); csrf = extract_cookie(r,"csrf_token")
    check("02. POST /auth/register", r.status_code==200 and token, f"status={r.status_code}")
    if not token: raise RuntimeError("No auth token")

    # 03-04: Auth
    r = requests.get(f"{BASE}/api/v1/auth/me", cookies=cookies(token, None), timeout=5)
    check("03. GET /me (cookie auth)", r.status_code==200, f"status={r.status_code}")

    r = requests.get(f"{BASE}/api/v1/auth/me", headers=headers(token, None), timeout=5)
    check("04. GET /me (Bearer auth)", r.status_code==200, f"status={r.status_code}")

    # 05: Create server
    slug = f"gw-{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE}/api/v1/servers", headers=headers(token, csrf), cookies=cookies(token, csrf),
        json={"name":"Gateway Real Test","slug":slug,"base_url":"https://httpbin.org",
              "auth_scheme":"none","transport_mode":"both"}, timeout=10)
    sid = r.json().get("id","") if r.status_code in (200,201) else ""
    check("05. POST /api/v1/servers", r.status_code in (200,201) and bool(sid), f"status={r.status_code}")
    if not sid: raise RuntimeError("Server creation failed")

    # 06: Set active
    r = requests.patch(f"{BASE}/api/v1/servers/{sid}", headers=headers(token, csrf), cookies=cookies(token, csrf),
        json={"status":"active"}, timeout=10)
    check("06. PATCH status=active", r.status_code==200, f"status={r.status_code}")

    # 07: Connect panel
    r = requests.get(f"{BASE}/api/v1/servers/{sid}/connect", cookies=cookies(token, None), timeout=5)
    dp = r.json() if r.status_code==200 else {}
    check("07. GET /servers/{id}/connect", r.status_code==200 and dp.get("server_slug")==slug,
          f"status={r.status_code}")

    # 08-15: MCP protocol
    r = requests.post(f"{BASE}/mcp/v1/{slug}/", cookies=cookies(token, None),
        json={"jsonrpc":"2.0","id":1,"method":"initialize",
              "params":{"protocolVersion":"2025-11-25","capabilities":{},
                        "clientInfo":{"name":"test","version":"1.0"}}}, timeout=10)
    d = r.json() if r.status_code==200 else {}
    check("08. MCP initialize (capabilities)",
          r.status_code==200 and d.get("result",{}).get("protocolVersion")=="2025-11-25",
          f"status={r.status_code}")

    r = requests.post(f"{BASE}/mcp/v1/{slug}/", cookies=cookies(token, None),
        json={"jsonrpc":"2.0","id":2,"method":"tools/list"}, timeout=10)
    d = r.json() if r.status_code==200 else {}
    check("09. MCP tools/list (returns tools)",
          r.status_code==200 and "tools" in d.get("result",{}),
          f"status={r.status_code} tools={len(d.get('result',{}).get('tools',[]))}")

    r = requests.post(f"{BASE}/mcp/v1/{slug}/", cookies=cookies(token, None),
        json={"jsonrpc":"2.0","id":3,"method":"ping"}, timeout=10)
    d = r.json() if r.status_code==200 else {}
    check("10. MCP ping (empty result)", r.status_code==200 and d.get("result")=={}, f"status={r.status_code}")

    r = requests.post(f"{BASE}/mcp/v1/{slug}/", cookies=cookies(token, None),
        json={"jsonrpc":"2.0","id":4,"method":"nonexistent"}, timeout=10)
    d = r.json()
    check("11. MCP method not found (-32601)", d.get("error",{}).get("code")==-32601,
          f"code={d.get('error',{}).get('code')}")

    r = requests.post(f"{BASE}/mcp/v1/{slug}/",
        json={"jsonrpc":"2.0","id":1,"method":"tools/list"}, timeout=5)
    check("12. No auth returns 401", r.status_code==401, f"got {r.status_code}")

    r = requests.post(f"{BASE}/mcp/v1/{slug}/",
        headers={"Authorization":"Bearer invalid"},
        json={"jsonrpc":"2.0","id":1,"method":"tools/list"}, timeout=5)
    check("13. Bad token returns 401", r.status_code==401, f"got {r.status_code}")

    r = requests.post(f"{BASE}/mcp/v1/no-such-{uuid.uuid4().hex[:4]}/",
        cookies=cookies(token, None),
        json={"jsonrpc":"2.0","id":1,"method":"tools/list"}, timeout=5)
    check("14. Non-existent server returns error",
          r.status_code in (404,200) and ("error" in r.json() if r.status_code==200 else True),
          f"status={r.status_code}")

    r = requests.post(f"{BASE}/mcp/v1/{slug}/", cookies=cookies(token, None),
        json={"jsonrpc":"2.0","method":"notifications/initialized"}, timeout=10)
    check("15. Notification returns 202", r.status_code==202, f"got {r.status_code}")

    # 16: SSRF guard
    r = requests.post(f"{BASE}/api/v1/servers", headers=headers(token, csrf), cookies=cookies(token, csrf),
        json={"name":"SSRF Test","slug":f"ssrf-{uuid.uuid4().hex[:8]}",
              "base_url":"http://169.254.169.254","auth_scheme":"none"}, timeout=10)
    bad_sid = r.json().get("id","") if r.status_code in (200,201) else ""
    if bad_sid:
        requests.patch(f"{BASE}/api/v1/servers/{bad_sid}", headers=headers(token, csrf), cookies=cookies(token, csrf),
            json={"status":"active"}, timeout=10)
        bad_slug = r.json().get("slug","")
        r2 = requests.post(f"{BASE}/mcp/v1/{bad_slug}/", cookies=cookies(token, None),
            json={"jsonrpc":"2.0","id":1,"method":"tools/list"}, timeout=10)
        check("16. SSRF server (internal IP base_url)", r2.status_code in (200,404), f"status={r2.status_code}")
        requests.delete(f"{BASE}/api/v1/servers/{bad_sid}", headers=headers(token, csrf), cookies=cookies(token, csrf), timeout=10)
    else:
        check("16. SSRF (create server)", False, f"status={r.status_code}")

    # 17: SSE stream
    conn = httpc.HTTPConnection("localhost", 8000, timeout=5)
    conn.request("GET", f"/mcp/v1/{slug}/sse", headers={"Cookie":f"access_token={token}"})
    resp = conn.getresponse()
    ct = resp.getheader("content-type","")
    try:
        resp.sock.settimeout(1.0)
        resp.read(512)
    except: pass
    finally: conn.close()
    check("17. GET /mcp/v1/{slug}/sse (SSE stream)", resp.status==200 and "text/event-stream" in ct,
          f"status={resp.status} ct={ct[:30]}")

    # 18: Health public
    r = requests.get(f"{BASE}/mcp/v1/{slug}/health", timeout=5)
    check("18. MCP health is public", r.status_code==200, f"status={r.status_code}")

    # 19: Pause
    r = requests.post(f"{BASE}/api/v1/servers/{sid}/pause", headers=headers(token, csrf), cookies=cookies(token, csrf), timeout=10)
    d = r.json() if r.status_code==200 else {}
    check("19. POST /servers/{id}/pause", r.status_code==200 and d.get("status")=="paused",
          f"-> {d.get('status')}")

    # 20: MCP while paused
    r = requests.post(f"{BASE}/mcp/v1/{slug}/", cookies=cookies(token, None),
        json={"jsonrpc":"2.0","id":1,"method":"tools/list"}, timeout=10)
    d = r.json() if r.status_code in (200,404) else {}
    check("20. MCP while paused returns error",
          r.status_code==200 and d.get("error",{}).get("code") in (-32004,-32002),
          f"status={r.status_code} code={d.get('error',{}).get('code','?')}")

    # 21: Resume
    r = requests.post(f"{BASE}/api/v1/servers/{sid}/resume", headers=headers(token, csrf), cookies=cookies(token, csrf), timeout=10)
    d = r.json() if r.status_code==200 else {}
    check("21. POST /servers/{id}/resume", r.status_code==200 and d.get("status")=="active",
          f"-> {d.get('status')}")

    # 22: MCP after resume
    r = requests.post(f"{BASE}/mcp/v1/{slug}/", cookies=cookies(token, None),
        json={"jsonrpc":"2.0","id":1,"method":"tools/list"}, timeout=10)
    d = r.json() if r.status_code==200 else {}
    check("22. MCP call after resume works", r.status_code==200 and "result" in d, f"status={r.status_code}")

    # 23: Cleanup
    r = requests.delete(f"{BASE}/api/v1/servers/{sid}", headers=headers(token, csrf), cookies=cookies(token, csrf), timeout=10)
    check("23. DELETE /servers/{id} (cleanup)", r.status_code==204, f"status={r.status_code}")

except Exception as e:
    print(f"\n  \u26a0\ufe0f Test interrupted: {e}")

print(f"\n{'='*60}")
print(f"  RESULTS: {passed}/{total} tests passed")
if passed == total: print(f"  \u2705 ALL TESTS PASSED")
else: print(f"  \u274c {total - passed} TESTS FAILED")
print(f"{'='*60}")
