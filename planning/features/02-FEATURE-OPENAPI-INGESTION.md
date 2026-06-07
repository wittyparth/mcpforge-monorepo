# Feature 1 — OpenAPI Spec Ingestion

> **PRD reference:** § 7 Feature 1 (lines 237-261)
> **Build order:** Wave 1, Step 1 (the product doesn't exist without this)
> **Estimated effort:** 4-6 days for one engineer

---

## 0. TL;DR

The entry point for all server creation. User provides an OpenAPI spec (URL or file upload), the system fetches/validates it, extracts MCP tool definitions, and presents a Tool Workspace where the user can curate which endpoints become tools. After curation, the server is persisted with `status="draft"` (not "building" — that comes after the AI Engine runs in F2).

This feature ships the **builder shell** but does not yet ship the AI Description Engine (F2) or the actual gateway execution (F4). The user CAN complete the ingestion and curation, but to actually deploy the server they need F2 + F4 + F5. F1 unblocks F2, F4, F5, F6.

---

## 1. Goals & Non-Goals

### 1.1 In scope (v1.0)
- Fetch OpenAPI from a public URL
- Upload OpenAPI file (JSON or YAML, ≤5MB)
- Validate against OpenAPI 3.0+ schema
- Surface specific validation errors (not generic "invalid spec")
- Parse and extract all endpoints as candidate tools
- Group by tag, color-code by HTTP method
- Allow per-tool selection/deselection
- Default selection: all GET endpoints selected, all DELETE deselected
- Auto-generate tool name from `{method}_{path_segments}` when `operationId` missing
- Show warning badges for: missing `operationId`, missing description, untagged endpoints
- Persist spec to S3/R2 for later use (AI Engine re-reads)
- Persist tools_config to `mcp_servers.tools_config` JSONB
- Create initial `server_versions` snapshot
- **Detect large specs (200+ endpoints) and warn** before user commits to selecting all

### 1.2 Out of scope (defer to v1.1+)
- OpenAPI 2.0 (Swagger) — v1.1
- Spec editing (modify and re-upload) — v1.1
- Multi-spec composition (combine 2+ specs into 1 server) — v1.2
- Spec versioning (track changes between fetches) — v1.1
- Spec marketplace — v2.0

---

## 2. User Stories

- As an API developer, I can paste a public OpenAPI spec URL and see the parsed tools within 5 seconds.
- As an API developer, I can drag-and-drop or browse to upload an OpenAPI file (JSON or YAML, ≤5MB).
- As an API developer, I see specific validation errors (line number, field name) when my spec is malformed — not a generic "invalid" message.
- As an API developer, I see a Tool Workspace with all endpoints grouped by tag, with color-coded HTTP methods and checkboxes to include/exclude each.
- As an API developer, I see a yellow warning badge on tools missing `operationId` (auto-generated names are not ideal).
- As an API developer, I can deselect DELETE endpoints to exclude destructive operations.
- As an API developer, I see a summary badge: "12 tools selected • 8 excluded."
- As an API developer, I see a warning when my spec has 200+ endpoints, recommending I select 10-30 key tools.
- As an API developer, I can name my server (pre-filled from `info.title`).
- As an API developer, I can configure authentication (None / API Key / Bearer Token / Basic Auth / OAuth2) and provide credentials.
- As an API developer, I can click "Test Connection" to verify my credentials work before saving.
- As an API developer, I see a real-time progress stream during server build (SSE).
- As a user with a spec behind Basic Auth, I can provide fetch credentials (stored only in session, not persisted).

---

## 3. Architecture Diagram

```
┌────────────────┐         ┌─────────────────┐
│  Browser       │         │  Main API       │
│  (Next.js)     │         │  (FastAPI)      │
│                │         │                 │
│  /servers/new  │         │  specs.py       │
│  Form:         │         │  ├─ POST /specs/fetch   ──────► OpenAPIFetcher.fetch_from_url()
│  - spec URL    │         │  │                       │
│  - or upload   │         │  │                       ▼
│  - server name │         │  │              ┌────────────────┐
│  - auth config │         │  │              │  httpx client  │
│                │         │  │              │  GET spec_url  │
│  Tool Workspace│         │  │              └────────┬───────┘
│  - tag groups  │         │  │                       │
│  - tool rows   │         │  │              ┌────────▼───────┐
│  - counters    │         │  │              │  prance.       │
│                │         │  │              │  ResolvingParser│
│  Build progress│◄────────┼──┼──────────────┤  (validates +  │
│  (SSE stream)  │  GET    │  │              │   resolves $ref)│
│                │ /build  │  │              └────────┬───────┘
└────────────────┘ status  │  │                       │
                           │  │              ┌────────▼───────┐
                           │  │              │  SpecAnalyzer  │
                           │  │              │  extract_tools │
                           │  │              └────────┬───────┘
                           │  │                       │
                           │  │              ┌────────▼───────┐
                           │  └──────────────┤  mcp_servers   │
                           │  POST /specs/   │  INSERT        │
                           │  {id}/tools     │  tools_config  │
                           │                 │  (JSONB)       │
                           │                 └────────────────┘
                           │
                           │  Cloudflare R2: full spec stored
                           └─► r2.put_object(bucket, key, spec_json)
```

### 3.1 Data flow

1. User submits spec URL → `POST /api/v1/specs/fetch` with `{url, headers?}` (for auth-protected specs)
2. `OpenAPIFetcher.fetch_from_url()`:
   - Validates URL is public, not internal (SSRF prevention, but for fetch)
   - `httpx.AsyncClient` GET with 10s timeout, follow redirects (max 3)
   - Returns raw bytes
3. `validate_spec_content(content, content_type)`:
   - Detect JSON vs YAML
   - If YAML, parse with `yaml.safe_load` (DONE: not `yaml.load` — security)
   - If parse fails, return specific error: `{line: 23, column: 5, message: "mapping values are not allowed here"}`
   - Validate with `openapi_spec_validator.validate(spec_dict)`
   - If validate fails, return all errors with path + message
4. `parse_spec(spec_dict, base_url)`:
   - Use `prance.ResolvingParser` for $ref resolution
   - Set recursion limit high (default 20) for deeply nested specs
   - Returns fully resolved spec dict
5. `SpecAnalyzer.extract_tools(resolved_spec, server_id)`:
   - Iterate `spec['paths']` → for each method → build tool dict:
     ```python
     {
         "name": operation.get("operationId") or f"{method}_{path_normalized}",
         "method": method.upper(),
         "path": path,
         "description": operation.get("description", "").strip() or operation.get("summary", ""),
         "tags": operation.get("tags", []),
         "parameters": [],  # built from path, query, header, body params
         "request_body_schema": operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema"),
         "responses_schema": operation.get("responses", {}),
         "selected_by_default": method.upper() in {"GET"} and method.upper() not in {"DELETE"},
     }
     ```
   - Build a flat list of tools + a tag-grouped structure
6. `POST /api/v1/specs/{id}/select-tools` with `{tools: [{name, selected: true/false, custom_name?: string}]}`
7. Update `mcp_servers.tools_config` with the user-curated selection
8. If spec is large (>5MB) and user selected all → warn before save (return 200 with `warning` field, UI shows confirm)
9. `POST /api/v1/servers/{id}/build` → status = "building", Celery task enqueued (initially just logs progress; F2 wires up the actual AI work)
10. `GET /api/v1/servers/{id}/build-status` → SSE stream of progress events

---

## 4. Backend Changes

### 4.1 New dependencies (add to `apps/api/pyproject.toml`)

```toml
"openapi-spec-validator>=0.9.0",
"prance>=25.0.0",
"cryptography>=44.0.0",  # for credential encryption
"boto3>=1.35.0",  # for S3/R2 (R2 is S3-compatible)
"tenacity>=9.0.0",  # for retry helpers
```

Dev:
```toml
"respx>=0.22.0",  # for mocking httpx in tests
"freezegun>=1.5.0",  # for time-sensitive tests
```

### 4.2 New files

```
apps/api/app/
├── services/
│   ├── openapi_fetcher.py           # URL fetch + validate (NEW)
│   ├── spec_analyzer.py             # extract tools (NEW)
│   ├── tool_generator.py            # OpenAPI op → MCP tool def (NEW)
│   ├── credential_service.py        # encrypt/decrypt API keys (NEW)
│   └── ingestion_service.py         # orchestrates the 3 above (NEW)
├── api/v1/endpoints/
│   ├── specs.py                     # /api/v1/specs/* routes (NEW)
│   ├── tools.py                     # /api/v1/servers/{id}/tools (NEW)
│   └── credentials.py               # /api/v1/servers/{id}/credentials (NEW)
├── schemas/
│   ├── openapi_spec.py              # SpecFetchRequest, ToolDefinition, etc. (NEW)
│   ├── credential.py                # CredentialCreate, CredentialResponse (NEW)
│   └── tool.py                      # ToolUpdateRequest (NEW)
├── repositories/
│   ├── credential_repo.py           # CredentialRepository (NEW)
│   └── spec_repo.py                 # SpecRepository — stores fetched specs (NEW; full spec in R2)
└── core/
    ├── encryption.py                # Fernet helpers (NEW)
    └── s3_client.py                 # Async S3 client wrapper (NEW)

apps/api/tests/
├── test_openapi_fetcher.py          # 8 tests (NEW)
├── test_spec_analyzer.py            # 12 tests (NEW)
├── test_tool_generator.py           # 6 tests (NEW)
├── test_credential_service.py       # 6 tests (NEW)
└── test_specs_endpoints.py          # 10 tests (NEW)
```

### 4.3 New SQLAlchemy models

#### `app/models/spec.py` (NEW)

```python
class SpecSource(Base, UUIDMixin, TimestampMixin):
    """A fetched/uploaded OpenAPI spec. Persisted for re-use across server builds."""
    __tablename__ = "spec_sources"
    
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'url' | 'upload'
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # original URL if applicable
    storage_url: Mapped[str] = mapped_column(String(500), nullable=False)  # S3/R2 key
    title: Mapped[str] = mapped_column(String(200), nullable=False)  # from spec['info']['title']
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)  # from spec['info']['version']
    openapi_version: Mapped[str] = mapped_column(String(20), nullable=False)  # '3.0.0', '3.1.0', etc.
    endpoint_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tag_count: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # dedupe
    
    # Server relationship (one spec can be used to build many servers? v1.0: no, 1:1)
    server_id: Mapped[UUID | None] = mapped_column(ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True)
    
    __table_args__ = (
        Index("idx_spec_user_sha", "user_id", "sha256_hash"),
    )
```

Add to `app/models/__init__.py` exports.

### 4.4 New Pydantic schemas

#### `app/schemas/openapi_spec.py` (NEW)

```python
class SpecFetchRequest(BaseModel):
    url: HttpUrl  # validated as URL
    headers: dict[str, str] = {}  # for Basic Auth on the spec URL
    timeout_seconds: int = Field(default=10, ge=1, le=30)

class SpecUploadResponse(BaseModel):
    spec_id: UUID
    title: str
    version: str | None
    openapi_version: str
    endpoint_count: int
    tag_count: int
    size_bytes: int
    sha256_hash: str
    tools: list[ToolDefinition]  # the parsed tools

class SpecValidationError(BaseModel):
    path: str  # JSON path to the field
    message: str
    line: int | None = None  # for YAML/JSON parse errors
    column: int | None = None

class SpecFetchErrorResponse(BaseModel):
    error_code: str  # 'INVALID_URL' | 'FETCH_TIMEOUT' | 'INVALID_SPEC' | 'TOO_LARGE' | 'UNSUPPORTED_VERSION'
    message: str
    details: list[SpecValidationError] = []
    suggestion: str | None = None  # user-friendly next-step guidance

class ToolDefinition(BaseModel):
    name: str  # MCP tool name (snake_case)
    original_operation_id: str | None
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    path: str
    summary: str | None
    description: str
    tags: list[str]
    parameters: list[ToolParameter]
    request_body_schema: dict | None  # JSON Schema
    response_schemas: dict[str, dict]  # status_code → schema
    security_requirements: list[dict]
    selected: bool  # default selection logic
    warnings: list[str] = []  # ['missing_operation_id', 'no_description', 'untagged']

class ToolParameter(BaseModel):
    name: str
    in_: Literal["path", "query", "header", "cookie"] = Field(alias="in")
    required: bool
    description: str
    schema_: dict = Field(alias="schema")  # JSON Schema
    example: Any | None = None

class ToolSelectionRequest(BaseModel):
    tools: list[ToolSelectionItem]
    server_name: str = Field(min_length=1, max_length=200)
    server_description: str | None = Field(default=None, max_length=2000)
    base_url: HttpUrl
    auth_scheme: Literal["none", "api_key", "bearer", "basic", "oauth2"]
    auth_header_name: str | None = Field(default=None, max_length=100)  # for api_key
    transport_mode: Literal["sse", "streamable_http", "both"] = "sse"

class ToolSelectionItem(BaseModel):
    name: str  # the tool name
    selected: bool
    custom_name: str | None = None  # user can rename
```

#### `app/schemas/credential.py` (NEW)

```python
class CredentialCreateRequest(BaseModel):
    env_var_name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    value: str = Field(min_length=1)  # plaintext, server encrypts immediately
    auth_scheme: Literal["api_key", "bearer", "basic", "oauth2"]
    auth_header_name: str | None = None

class CredentialTestRequest(BaseModel):
    env_var_name: str  # which env var to test
    test_value: str  # the value to test (NOT stored)

class CredentialTestResponse(BaseModel):
    success: bool
    status_code: int | None
    response_time_ms: int
    error: str | None = None  # sanitized, no credentials

class CredentialResponse(BaseModel):
    id: UUID
    env_var_name: str
    auth_scheme: str
    auth_header_name: str | None
    created_at: datetime
    rotated_at: datetime | None
    last_used_at: datetime | None
    # NEVER includes value
```

#### `app/schemas/tool.py` (NEW)

```python
class ToolUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    parameters: list[ToolParameter] | None = None
    return_description: str | None = None
    enabled: bool | None = None

class ToolResponse(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameter]
    return_description: str | None
    method: str
    path: str
    tags: list[str]
    enabled: bool
    ai_enhanced: bool
    quality_score: int | None  # 0-100, None if not yet scored
    last_updated_at: datetime
    last_updated_by: str  # 'user' | 'ai' | 'initial'
```

### 4.5 New endpoints

| Method | Path | Handler | Request | Response | Errors |
|---|---|---|---|---|---|
| POST | `/api/v1/specs/fetch` | `fetch_spec` | `SpecFetchRequest` | `SpecUploadResponse` (with parsed tools) | 400 INVALID_URL, 422 INVALID_SPEC (with details), 413 TOO_LARGE, 502 UPSTREAM_ERROR |
| POST | `/api/v1/specs/upload` | `upload_spec` | multipart: `file`, optional `server_id` | `SpecUploadResponse` | 400 INVALID_FILE, 413 TOO_LARGE, 422 INVALID_SPEC |
| GET | `/api/v1/specs/{spec_id}` | `get_spec` | — | `SpecUploadResponse` | 404 |
| POST | `/api/v1/specs/{spec_id}/select-tools` | `select_tools` | `ToolSelectionRequest` | `MCPServerResponse` (created or updated) | 400, 404, 409 (too many tools) |
| GET | `/api/v1/servers/{id}/tools` | `list_tools` | — | `list[ToolResponse]` | 401, 404 |
| PATCH | `/api/v1/servers/{id}/tools/{name}` | `update_tool` | `ToolUpdateRequest` | `ToolResponse` | 400, 401, 404 |
| POST | `/api/v1/servers/{id}/credentials` | `add_credential` | `CredentialCreateRequest` | `CredentialResponse` | 400, 401, 404 |
| GET | `/api/v1/servers/{id}/credentials` | `get_credentials` | — | `list[CredentialResponse]` (no values!) | 401, 404 |
| POST | `/api/v1/servers/{id}/credentials/test` | `test_credential` | `CredentialTestRequest` | `CredentialTestResponse` | 400, 401, 404 |
| DELETE | `/api/v1/servers/{id}/credentials` | `delete_credential` | query: `env_var_name` | 204 | 401, 404 |

**Note:** credentials are added at server creation OR after. They're referenced from `mcp_servers.credential_id` (current model) — multiple credentials per server deferred to v1.1.

### 4.6 New services — pseudocode

#### `app/services/openapi_fetcher.py` (NEW, ~150 lines)

```python
class OpenAPIFetcher:
    """Fetches OpenAPI specs from URLs or bytes, validates them, stores them."""
    
    def __init__(self, r2_client: R2Client, session: AsyncSession):
        self.r2 = r2_client
        self.repo = SpecRepository(session)
        self.max_size = settings.MAX_SPEC_SIZE_BYTES  # 5MB default
        self.timeout = settings.MAX_SPEC_FETCH_TIMEOUT_SECONDS  # 10s default
    
    async def fetch_from_url(self, user_id: UUID, url: str, headers: dict) -> SpecSource:
        # 1. Validate URL
        if not self._is_valid_url(url):
            raise InvalidURLError("URL must be HTTPS and not internal IP")
        
        # 2. Fetch with timeout
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers)
            except httpx.TimeoutException:
                raise FetchTimeoutError(f"Spec fetch exceeded {self.timeout}s timeout")
        
        # 3. Size check
        content = response.content
        if len(content) > self.max_size:
            raise SpecTooLargeError(f"Spec is {len(content)} bytes, max is {self.max_size}")
        
        # 4. Parse and validate
        spec_dict = self._parse_content(content, response.headers.get("content-type"))
        # raises SpecValidationError with specific errors
        
        # 5. Hash for dedup
        sha = hashlib.sha256(content).hexdigest()
        
        # 6. Check if user already has this spec
        existing = await self.repo.get_by_user_and_hash(user_id, sha)
        if existing:
            return existing  # dedup
        
        # 7. Store in S3/R2
        r2_key = f"specs/{user_id}/{sha}.json"
        await self.r2.put_object(bucket=settings.R2_BUCKET, key=r2_key, body=content)
        
        # 8. Persist metadata
        return await self.repo.create(
            user_id=user_id,
            source_type="url",
            source_url=url,
            storage_url=r2_key,
            title=spec_dict.get("info", {}).get("title", "Untitled"),
            version=spec_dict.get("info", {}).get("version"),
            openapi_version=spec_dict.get("openapi", "unknown"),
            endpoint_count=len(self._count_endpoints(spec_dict)),
            tag_count=len(self._count_tags(spec_dict)),
            raw_size_bytes=len(content),
            sha256_hash=sha,
        )
    
    async def upload(self, user_id: UUID, file: UploadFile) -> SpecSource:
        # 1. Read file
        content = await file.read()
        if len(content) > self.max_size:
            raise SpecTooLargeError(...)
        
        # 2. Parse
        spec_dict = self._parse_content(content, file.content_type)
        
        # 3. Same as above (dedup, store, persist)
        return await self._store(user_id, content, spec_dict, source_type="upload")
    
    def _parse_content(self, content: bytes, content_type: str | None) -> dict:
        # 1. Detect format
        is_json = (
            content_type and "json" in content_type.lower()
        ) or content.lstrip().startswith(b"{")
        
        try:
            if is_json:
                spec_dict = json.loads(content)
            else:
                spec_dict = yaml.safe_load(content)  # safe_load, NOT load
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise SpecParseError(str(e), line=getattr(e, 'problem_mark', None) and e.problem_mark.line + 1)
        
        # 2. Validate with openapi-spec-validator
        try:
            openapi_spec_validator.validate(spec_dict)
        except OpenAPIValidationError as e:
            raise SpecValidationError(
                message=str(e),
                details=[
                    SpecValidationDetail(
                        path=".".join(str(p) for p in err.absolute_path),
                        message=err.message,
                    )
                    for err in e.errors
                ]
            )
        
        # 3. Check version
        version = spec_dict.get("openapi", "")
        if not version.startswith("3."):
            raise UnsupportedSpecVersionError(
                f"Only OpenAPI 3.0+ supported. Got: {version}",
                suggestion="Convert Swagger 2.0 to OpenAPI 3.0 using a tool like swagger2openapi",
            )
        
        return spec_dict
    
    def _is_valid_url(self, url: str) -> bool:
        # Must be HTTPS (allow http for localhost dev)
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            return False
        # Resolve hostname, block internal IPs
        try:
            ip = socket.gethostbyname(parsed.hostname)
        except socket.gaierror:
            return False
        if ipaddress.ip_address(ip).is_private:
            return False
        return True
```

#### `app/services/spec_analyzer.py` (NEW, ~200 lines)

```python
class SpecAnalyzer:
    """Extracts MCP tool definitions from a parsed OpenAPI spec."""
    
    def extract_tools(self, spec_dict: dict) -> list[ToolDefinition]:
        # 1. Resolve $refs
        resolved = self._resolve_refs(spec_dict)
        
        # 2. Iterate paths
        tools = []
        for path, path_item in resolved.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                    continue
                if not isinstance(operation, dict):
                    continue
                tool = self._build_tool(path, method, operation, resolved)
                tools.append(tool)
        
        # 3. Auto-name tools without operationId
        tools = self._assign_unique_names(tools)
        
        # 4. Compute default selection
        for tool in tools:
            tool.selected = self._default_selected(tool)
        
        return tools
    
    def _build_tool(self, path: str, method: str, operation: dict, spec: dict) -> ToolDefinition:
        op_id = operation.get("operationId")
        name = op_id or self._name_from_path(method, path)
        
        params = self._extract_parameters(operation.get("parameters", []), spec)
        body_schema = self._extract_request_body_schema(operation.get("requestBody"), spec)
        response_schemas = self._extract_responses(operation.get("responses", {}), spec)
        
        warnings = []
        if not op_id:
            warnings.append("missing_operation_id")
        if not (operation.get("description") or operation.get("summary")):
            warnings.append("no_description")
        if not operation.get("tags"):
            warnings.append("untagged")
        
        return ToolDefinition(
            name=name,
            original_operation_id=op_id,
            method=method.upper(),
            path=path,
            summary=operation.get("summary"),
            description=(operation.get("description") or operation.get("summary") or "").strip(),
            tags=operation.get("tags", []),
            parameters=params,
            request_body_schema=body_schema,
            response_schemas=response_schemas,
            security_requirements=operation.get("security", []),
            selected=False,  # computed later
            warnings=warnings,
        )
    
    def _name_from_path(self, method: str, path: str) -> str:
        # e.g., "GET /users/{id}/orders" → "get_users_id_orders"
        parts = [p.strip("{}") for p in path.split("/") if p]
        return f"{method.lower()}_{'_'.join(parts)}"
    
    def _assign_unique_names(self, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        # If two tools end up with the same name, append a counter
        seen = {}
        for tool in tools:
            base = tool.name
            if base not in seen:
                seen[base] = 0
            else:
                seen[base] += 1
                tool.name = f"{base}_{seen[base]}"
        return tools
    
    def _default_selected(self, tool: ToolDefinition) -> bool:
        # GET → selected, DELETE → deselected, others → selected if has params (safer)
        if tool.method == "GET":
            return True
        if tool.method == "DELETE":
            return False
        return True  # POST/PUT/PATCH selected by default; user can deselect
    
    def _resolve_refs(self, spec: dict) -> dict:
        # Use prance for full resolution
        # Falls back to jsonref for inline handling
        try:
            parser = ResolvingParser(spec_dict=spec, backend="openapi-spec-validator", strict=False)
            return parser.specification
        except Exception as e:
            # Log and fall back to unresolved (some refs may be broken)
            logger.warning("ref_resolution_failed", error=str(e))
            return spec
```

#### `app/services/tool_generator.py` (NEW, ~100 lines)

```python
class ToolGenerator:
    """Converts a user-curated ToolDefinition list into MCP tool_config stored in mcp_servers.tools_config."""
    
    def build_tools_config(self, tools: list[ToolDefinition], customizations: dict[str, dict] | None = None) -> dict:
        """
        Returns a JSON-serializable dict matching the format stored in mcp_servers.tools_config.
        
        Format:
        {
          "version": 1,
          "tools": [
            {
              "name": "search_products",
              "description": "...",
              "method": "GET",
              "path": "/products/search",
              "tags": ["products"],
              "inputSchema": {  # JSON Schema for tool arguments
                "type": "object",
                "properties": {
                  "query": {"type": "string", "description": "..."},
                  "limit": {"type": "integer", "description": "...", "default": 20}
                },
                "required": ["query"]
              },
              "annotations": {
                "readOnlyHint": true,
                "destructiveHint": false,
                "idempotentHint": true,
                "openWorldHint": false
              },
              "request_body_schema": {...},  # for POST/PUT/PATCH
              "response_schemas": {...},
              "security_requirements": [...]
            }
          ]
        }
        """
        config = {
            "version": 1,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "generator": "spec_analyzer_v1",
            "tools": []
        }
        
        for tool in tools:
            if not tool.selected:
                continue
            
            # Apply customizations (renames, etc.)
            tool_name = (customizations or {}).get(tool.name, {}).get("name", tool.name)
            
            # Build inputSchema by combining path params, query params, headers, and body
            input_schema = self._build_input_schema(tool)
            
            # Annotations per MCP spec
            annotations = {
                "readOnlyHint": tool.method in {"GET", "HEAD", "OPTIONS"},
                "destructiveHint": tool.method == "DELETE",
                "idempotentHint": tool.method in {"GET", "PUT", "DELETE", "HEAD", "OPTIONS"},
                "openWorldHint": False,
            }
            
            config["tools"].append({
                "name": tool_name,
                "description": tool.description,
                "method": tool.method,
                "path": tool.path,
                "tags": tool.tags,
                "inputSchema": input_schema,
                "annotations": annotations,
                "request_body_schema": tool.request_body_schema,
                "response_schemas": tool.response_schemas,
                "security_requirements": tool.security_requirements,
            })
        
        return config
    
    def _build_input_schema(self, tool: ToolDefinition) -> dict:
        """Builds the JSON Schema for tool arguments.
        
        Path/query/header params → top-level properties
        Body params → top-level properties (or nested under 'body' for clarity)
        """
        properties = {}
        required = []
        
        for param in tool.parameters:
            properties[param.name] = {
                **param.schema_,
                "description": param.description,
            }
            if param.example is not None:
                properties[param.name]["example"] = param.example
            if param.required:
                required.append(param.name)
        
        # Body params: merge top-level OR nest under 'body'
        if tool.request_body_schema:
            body_props = tool.request_body_schema.get("properties", {})
            for prop_name, prop_schema in body_props.items():
                # Prefix with body_ to avoid collision with path params
                prefixed = f"body_{prop_name}"
                properties[prefixed] = {
                    **prop_schema,
                    "description": prop_schema.get("description", f"Body parameter: {prop_name}"),
                }
                if prop_name in tool.request_body_schema.get("required", []):
                    required.append(prefixed)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
```

#### `app/services/credential_service.py` (NEW, ~120 lines)

```python
class CredentialService:
    """Encrypts, stores, retrieves, tests API credentials."""
    
    def __init__(self, session: AsyncSession):
        self.repo = CredentialRepository(session)
    
    def encrypt_value(self, plaintext: str) -> bytes:
        return encrypt(plaintext)  # from app.core.encryption
    
    def decrypt_value(self, ciphertext: bytes) -> str:
        return decrypt(ciphertext)
    
    async def add_credential(self, server_id: UUID, user_id: UUID, env_var_name: str, value: str, auth_scheme: str, auth_header_name: str | None) -> Credential:
        # 1. Validate env_var_name format
        if not re.match(r"^[A-Z][A-Z0-9_]*$", env_var_name):
            raise ValidationError("env_var_name must be uppercase letters, digits, underscores; start with letter")
        
        # 2. Check for existing credential with same env_var_name for this server
        existing = await self.repo.get_by_server_and_env(server_id, env_var_name)
        if existing:
            raise ConflictError(f"Credential for {env_var_name} already exists; use rotate instead")
        
        # 3. Encrypt
        encrypted = self.encrypt_value(value)
        
        # 4. Create
        credential = await self.repo.create(
            server_id=server_id,
            user_id=user_id,
            env_var_name=env_var_name,
            encrypted_value=encrypted,
            encryption_key_id="default",  # for future Fernet key rotation tracking
            auth_scheme=auth_scheme,
            auth_header_name=auth_header_name,
        )
        
        # 5. Audit log
        # (Audit log model added in F7; for now log via structlog)
        logger.info("credential_added", server_id=str(server_id), env_var_name=env_var_name, user_id=str(user_id))
        
        # 6. Return WITHOUT plaintext value
        return credential
    
    async def test_credential(self, server: MCPServer, test_value: str) -> CredentialTestResponse:
        """Tests the credential by making a dry-run request to the server's base_url."""
        # 1. Build request based on auth_scheme
        headers = self._build_auth_headers(server.auth_scheme, test_value, server.auth_header_name)
        
        # 2. Use a known-safe endpoint (e.g., HEAD on base_url, or OPTIONS)
        test_url = server.base_url.rstrip("/")
        if server.tools_config.get("tools"):
            # Try the first GET tool
            for tool in server.tools_config["tools"]:
                if tool["method"] == "GET":
                    test_url += tool["path"]
                    break
        
        # 3. Make request with timeout
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(test_url, headers=headers)
            elapsed_ms = int((time.time() - start) * 1000)
            return CredentialTestResponse(
                success=response.status_code < 400,
                status_code=response.status_code,
                response_time_ms=elapsed_ms,
                error=None if response.status_code < 400 else f"HTTP {response.status_code}",
            )
        except httpx.TimeoutException:
            return CredentialTestResponse(
                success=False,
                status_code=None,
                response_time_ms=int((time.time() - start) * 1000),
                error="Connection timed out (5s)",
            )
        except httpx.RequestError as e:
            return CredentialTestResponse(
                success=False,
                status_code=None,
                response_time_ms=int((time.time() - start) * 1000),
                error=f"Network error: {type(e).__name__}",
            )
    
    def _build_auth_headers(self, scheme: str, value: str, header_name: str | None) -> dict[str, str]:
        if scheme == "api_key":
            return {header_name or "X-API-Key": value}
        elif scheme == "bearer":
            return {"Authorization": f"Bearer {value}"}
        elif scheme == "basic":
            encoded = base64.b64encode(value.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        elif scheme == "oauth2":
            return {"Authorization": f"Bearer {value}"}
        return {}
    
    def get_decrypted_for_gateway(self, credential: Credential) -> str:
        """Called ONLY by the gateway service. Never logged or returned to API."""
        return self.decrypt_value(credential.encrypted_value)
```

#### `app/core/encryption.py` (NEW, ~25 lines)

```python
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

def _get_fernet() -> Fernet:
    if not settings.ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY not set")
    return Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode("utf-8"))

def decrypt(ciphertext: bytes) -> str:
    try:
        return _get_fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("Invalid encryption token — key may have rotated") from e
```

#### `app/core/s3_client.py` (NEW, ~80 lines)

```python
import aioboto3
from app.core.config import settings

class R2Client:
    """Async Cloudflare R2 client. Uses the S3-compatible API via aioboto3.
    
    R2 is S3-compatible, so we use aioboto3 with the R2-specific endpoint URL.
    R2 doesn't require region; we hardcode 'auto'.
    """
    
    def __init__(self):
        self.session = aioboto3.Session()
        self.bucket = settings.R2_BUCKET
        # R2 endpoint: https://<accountid>.r2.cloudflarestorage.com
        self.endpoint_url = settings.R2_ENDPOINT_URL or (
            f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            if settings.R2_ACCOUNT_ID else None
        )
        if not self.endpoint_url:
            raise RuntimeError("R2_ENDPOINT_URL or R2_ACCOUNT_ID must be set")
    
    async def put_object(self, key: str, body: bytes, content_type: str = "application/json") -> None:
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",  # R2 uses 'auto'
        ) as s3:
            await s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
    
    async def get_object(self, key: str) -> bytes:
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        ) as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()
```

### 4.7 New repositories

#### `app/repositories/spec_repo.py` (NEW, ~80 lines)

```python
class SpecRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, **kwargs) -> SpecSource:
        spec = SpecSource(**kwargs)
        self.session.add(spec)
        await self.session.commit()
        await self.session.refresh(spec)
        return spec
    
    async def get_by_id(self, spec_id: UUID) -> SpecSource | None:
        result = await self.session.execute(select(SpecSource).where(SpecSource.id == spec_id))
        return result.scalar_one_or_none()
    
    async def get_by_user_and_hash(self, user_id: UUID, sha: str) -> SpecSource | None:
        result = await self.session.execute(
            select(SpecSource)
            .where(SpecSource.user_id == user_id, SpecSource.sha256_hash == sha)
        )
        return result.scalar_one_or_none()
    
    async def list_by_user(self, user_id: UUID, skip: int = 0, limit: int = 20) -> list[SpecSource]:
        result = await self.session.execute(
            select(SpecSource)
            .where(SpecSource.user_id == user_id)
            .order_by(SpecSource.created_at.desc())
            .offset(skip).limit(limit)
        )
        return result.scalars().all()
```

#### `app/repositories/credential_repo.py` (NEW, ~80 lines)

```python
class CredentialRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, **kwargs) -> Credential:
        cred = Credential(**kwargs)
        self.session.add(cred)
        await self.session.commit()
        await self.session.refresh(cred)
        return cred
    
    async def get_by_id(self, cred_id: UUID) -> Credential | None:
        ...
    
    async def get_by_server(self, server_id: UUID) -> list[Credential]:
        ...
    
    async def get_by_server_and_env(self, server_id: UUID, env_var: str) -> Credential | None:
        ...
    
    async def delete(self, cred: Credential) -> None:
        await self.session.delete(cred)
        await self.session.commit()
    
    async def rotate(self, cred: Credential, new_encrypted_value: bytes) -> Credential:
        cred.encrypted_value = new_encrypted_value
        cred.rotated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(cred)
        return cred
```

### 4.8 Test plan

| File | Test count | Coverage |
|---|---|---|
| `test_openapi_fetcher.py` | 8 | valid URL fetch, invalid URL (private IP), timeout, too large, invalid JSON, invalid YAML, valid spec parse, dedup |
| `test_spec_analyzer.py` | 12 | simple GET extraction, POST with body, multiple params, path params, header params, missing operationId, $ref resolution, circular refs (no crash), large spec (300+ endpoints), tag grouping, default selection (GET in, DELETE out), warning badges |
| `test_tool_generator.py` | 6 | basic tool config, with customizations, POST with body params, mixed path+query params, response schemas, annotations correctness |
| `test_credential_service.py` | 6 | encrypt/decrypt roundtrip, invalid env_var_name (lowercase), duplicate credential, test connection (mocked HTTP), auth header building for each scheme, audit log |
| `test_specs_endpoints.py` | 10 | fetch happy, fetch invalid, upload happy, upload too large, select tools happy, select tools with conflict, list tools, update tool, add credential, delete credential |
| `test_encryption.py` | 4 | encrypt+decrypt roundtrip, wrong key fails, empty string, unicode |
| `test_s3_client.py` | 4 | put/get roundtrip (with moto mock), endpoint_url for R2, content-type preserved, error handling |

**Mocking strategy:**
- `respx` for httpx mocking
- `moto` for S3/R2 mocking (R2 uses the S3 protocol, so moto works)
- `openapi_spec_validator` accepts a real spec, so most tests use a hardcoded test spec

---

## 5. Frontend Changes

### 5.1 New dependencies (add to `apps/web/package.json`)

```json
{
  "dependencies": {
    "monaco-editor": "^0.52.0",
    "@monaco-editor/react": "^4.6.0",
    "react-resizable-panels": "^2.1.0",
    "@radix-ui/react-tabs": "^1.1.0",
    "@radix-ui/react-scroll-area": "^1.2.0",
    "@radix-ui/react-switch": "^1.1.0",
    "@radix-ui/react-toggle-group": "^1.1.0"
  },
  "devDependencies": {
    "vitest": "^2.1.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/user-event": "^14.5.0",
    "jsdom": "^25.0.0"
  }
}
```

### 5.2 New pages

| Path | Component | Notes |
|---|---|---|
| `/dashboard/servers/new` | Modify existing | Add tabs: "From OpenAPI" / "Manual" (manual deferred to v1.2) |
| `/dashboard/servers/[slug]` | Replace placeholder | Tabs: Tools / Playground / Analytics / Settings / Security |
| `/dashboard/servers/[slug]/tools` | NEW | Tool workspace + description editor (F1 + F2) |

### 5.3 New components

```
src/components/
├── builder/                                (NEW)
│   ├── spec-input.tsx                      # Tab: URL vs Upload
│   ├── spec-url-input.tsx                  # URL field + fetch button
│   ├── spec-upload-input.tsx               # Drag-drop file input
│   ├── spec-validation-errors.tsx          # Display errors from /specs/fetch
│   ├── tool-workspace.tsx                  # Main container
│   ├── tool-tag-group.tsx                  # Collapsible tag section
│   ├── tool-row.tsx                        # Single tool with checkbox, method badge, path, description
│   ├── tool-warnings.tsx                   # Yellow warning badges
│   ├── tool-summary.tsx                    # "12 tools selected • 8 excluded"
│   ├── large-spec-warning.tsx              # "200+ endpoints, consider selecting 10-30"
│   ├── server-config-form.tsx              # name, description, auth scheme, transport
│   ├── auth-scheme-selector.tsx            # RadioGroup for auth scheme
│   ├── credential-input.tsx                # env_var_name + value + test button
│   ├── credential-test-result.tsx          # Status + timing display
│   ├── build-progress-modal.tsx            # SSE-driven progress events
│   └── build-step-indicator.tsx            # Parsing → AI → Security → Ready
├── shared/                                 (NEW)
│   ├── http-method-badge.tsx               # Color-coded GET/POST/PUT/PATCH/DELETE
│   ├── copy-to-clipboard.tsx               # Reusable
│   ├── empty-state.tsx                     # Reusable
│   └── loading-spinner.tsx                 # Reusable
└── ui/
    ├── tabs.tsx                            # NEW shadcn primitive
    ├── scroll-area.tsx                     # NEW shadcn primitive
    ├── switch.tsx                          # NEW shadcn primitive
    └── toggle-group.tsx                    # NEW shadcn primitive
```

### 5.4 New hooks

```typescript
// src/hooks/use-spec.ts (NEW)
export function useFetchSpec() {
  return useMutation({
    mutationFn: (input: { url: string; headers?: Record<string, string> }) =>
      api.specs.fetch(input),
  });
}

export function useUploadSpec() {
  return useMutation({
    mutationFn: (file: File) => api.specs.upload(file),
  });
}

export function useSpec(specId: string | null) {
  return useQuery({
    queryKey: ['spec', specId],
    queryFn: () => api.specs.get(specId!),
    enabled: !!specId,
  });
}

export function useSelectTools() {
  return useMutation({
    mutationFn: ({ specId, selection }: { specId: string; selection: ToolSelectionRequest }) =>
      api.specs.selectTools(specId, selection),
    onSuccess: (server) => {
      queryClient.invalidateQueries({ queryKey: ['servers'] });
      router.push(`/dashboard/servers/${server.slug}/tools`);
    },
  });
}

export function useBuildServer() {
  return useMutation({
    mutationFn: (serverId: string) => api.servers.build(serverId),
  });
}

// src/hooks/use-build-status.ts (NEW)
export function useBuildStatus(serverId: string) {
  // Uses EventSource (SSE) — not TanStack Query
  // Returns { events: BuildEvent[], status: 'idle' | 'building' | 'complete' | 'error' }
}

// src/hooks/use-tools.ts (NEW)
export function useServerTools(serverId: string) {
  return useQuery({
    queryKey: ['server-tools', serverId],
    queryFn: () => api.servers.listTools(serverId),
  });
}

export function useUpdateTool(serverId: string) {
  return useMutation({
    mutationFn: ({ toolName, updates }: { toolName: string; updates: ToolUpdateRequest }) =>
      api.servers.updateTool(serverId, toolName, updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['server-tools', serverId] }),
  });
}

// src/hooks/use-credentials.ts (NEW)
export function useAddCredential(serverId: string) { ... }
export function useTestCredential(serverId: string) { ... }
export function useGetCredentials(serverId: string) { ... }
export function useDeleteCredential(serverId: string) { ... }
```

### 5.5 New types

```typescript
// src/types/api.ts — add to existing file

export interface ToolDefinition {
  name: string;
  original_operation_id: string | null;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS';
  path: string;
  summary: string | null;
  description: string;
  tags: string[];
  parameters: ToolParameter[];
  request_body_schema: any | null;
  response_schemas: Record<string, any>;
  security_requirements: any[];
  selected: boolean;
  warnings: string[];
}

export interface SpecUploadResponse {
  spec_id: string;
  title: string;
  version: string | null;
  openapi_version: string;
  endpoint_count: number;
  tag_count: number;
  size_bytes: number;
  sha256_hash: string;
  tools: ToolDefinition[];
}

export interface SpecValidationError {
  path: string;
  message: string;
  line?: number;
  column?: number;
}

export interface SpecFetchErrorResponse {
  error_code: 'INVALID_URL' | 'FETCH_TIMEOUT' | 'INVALID_SPEC' | 'TOO_LARGE' | 'UNSUPPORTED_VERSION';
  message: string;
  details: SpecValidationError[];
  suggestion?: string;
}

export interface ToolSelectionRequest {
  tools: { name: string; selected: boolean; custom_name?: string }[];
  server_name: string;
  server_description?: string;
  base_url: string;
  auth_scheme: 'none' | 'api_key' | 'bearer' | 'basic' | 'oauth2';
  auth_header_name?: string;
  transport_mode: 'sse' | 'streamable_http' | 'both';
}

// src/lib/validators.ts — add Zod schemas
export const specUrlSchema = z.object({
  url: z.string().url().refine(u => u.startsWith('https://') || u.startsWith('http://'), 'Must be a valid URL'),
  headers: z.record(z.string()).optional(),
});

export const toolSelectionSchema = z.object({
  tools: z.array(z.object({
    name: z.string(),
    selected: z.boolean(),
    custom_name: z.string().optional(),
  })),
  server_name: z.string().min(1).max(200),
  server_description: z.string().max(2000).optional(),
  base_url: z.string().url(),
  auth_scheme: z.enum(['none', 'api_key', 'bearer', 'basic', 'oauth2']),
  auth_header_name: z.string().max(100).optional(),
  transport_mode: z.enum(['sse', 'streamable_http', 'both']),
});
```

### 5.6 Update `lib/api.ts`

Add to `api` object:
```typescript
specs: {
  fetch: (input: { url: string; headers?: Record<string, string> }) =>
    request<SpecUploadResponse>('/api/v1/specs/fetch', { method: 'POST', body: input }),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<SpecUploadResponse>('/api/v1/specs/upload', { method: 'POST', body: formData });
  },
  get: (specId: string) => request<SpecUploadResponse>(`/api/v1/specs/${specId}`),
  selectTools: (specId: string, selection: ToolSelectionRequest) =>
    request<MCPServer>(`/api/v1/specs/${specId}/select-tools`, { method: 'POST', body: selection }),
},
servers: {
  // ... existing ...
  build: (serverId: string) => request<{ job_id: string }>(`/api/v1/servers/${serverId}/build`, { method: 'POST' }),
  listTools: (serverId: string) => request<ToolResponse[]>(`/api/v1/servers/${serverId}/tools`),
  updateTool: (serverId: string, toolName: string, updates: ToolUpdateRequest) =>
    request<ToolResponse>(`/api/v1/servers/${serverId}/tools/${toolName}`, { method: 'PATCH', body: updates }),
  credentials: {
    list: (serverId: string) => request<CredentialResponse[]>(`/api/v1/servers/${serverId}/credentials`),
    add: (serverId: string, input: CredentialCreateRequest) =>
      request<CredentialResponse>(`/api/v1/servers/${serverId}/credentials`, { method: 'POST', body: input }),
    test: (serverId: string, input: CredentialTestRequest) =>
      request<CredentialTestResponse>(`/api/v1/servers/${serverId}/credentials/test`, { method: 'POST', body: input }),
    delete: (serverId: string, envVarName: string) =>
      request<void>(`/api/v1/servers/${serverId}/credentials?env_var_name=${envVarName}`, { method: 'DELETE' }),
  },
},
```

### 5.7 Update `app/(dashboard)/servers/new/page.tsx`

Convert from single-form to multi-step:

1. **Step 1: Spec Source** (URL or upload)
   - On success → Step 2
   - On error → show validation errors
2. **Step 2: Tool Workspace**
   - Display tools grouped by tag
   - User can toggle each
   - Show summary
3. **Step 3: Server Config**
   - Name, description, base URL (pre-filled from `servers` field)
   - Auth scheme + credentials
   - Test connection button
4. **Step 4: Build**
   - Show progress
   - Redirect to server detail on complete

### 5.8 Test plan (Playwright + Vitest)

**Playwright E2E (in `tests/e2e/`):**
- `01-create-from-url.spec.ts`: register → create server from public OpenAPI URL (e.g., a test spec) → see tools → select subset → save → land on server detail
- `02-upload-spec.spec.ts`: register → upload a small spec file → verify parsing → continue flow
- `03-invalid-spec.spec.ts`: paste invalid spec URL → see specific validation errors

**Vitest component tests:**
- `ToolRow.test.tsx`: renders method badge correctly, checkbox toggles, warning badge shows
- `HttpMethodBadge.test.tsx`: color codes GET/POST/etc correctly
- `ToolSummary.test.tsx`: updates count correctly
- `SpecValidationErrors.test.tsx`: displays each error type

---

## 6. Database / Migration Plan

New migration: `0009_add_spec_sources.py` (NOT 0002 — that's reserved for F2's AI changes; this gets a later number to keep migrations ordered by feature).

```python
"""add spec_sources table"""
def upgrade() -> None:
    op.create_table(
        "spec_sources",
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column("user_id", sa.UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("storage_url", sa.String(500), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("openapi_version", sa.String(20), nullable=False),
        sa.Column("endpoint_count", sa.Integer, nullable=False),
        sa.Column("tag_count", sa.Integer, nullable=False),
        sa.Column("raw_size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("server_id", sa.UUID, sa.ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_spec_user_sha", "spec_sources", ["user_id", "sha256_hash"])
    op.create_index("idx_spec_server", "spec_sources", ["server_id"])

def downgrade() -> None:
    op.drop_index("idx_spec_server", table_name="spec_sources")
    op.drop_index("idx_spec_user_sha", table_name="spec_sources")
    op.drop_table("spec_sources")
```

Also need: alter `mcp_servers` to add `spec_source_id` column.
- `spec_source_id` UUID NULL REFERENCES spec_sources(id) ON DELETE SET NULL

---

## 7. Environment Variables

| Var | Required? | Default | Notes |
|---|---|---|---|
| `ENCRYPTION_KEY` | Yes (prod) | (dev fallback for testing only) | Fernet key. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `R2_BUCKET` | Yes | `mcpforge-specs-dev` | Cloudflare R2 bucket name |
| `R2_ACCESS_KEY_ID` | Yes | (empty) | From R2 API token |
| `R2_SECRET_ACCESS_KEY` | Yes | (empty) | From R2 API token |
| `R2_ACCOUNT_ID` | Yes | (empty) | Used to derive R2 endpoint URL |
| `R2_ENDPOINT_URL` | No | (auto-derived) | Override only if you use a custom R2 domain |
| `MAX_SPEC_SIZE_BYTES` | No | `5242880` (5MB) | |
| `MAX_SPEC_FETCH_TIMEOUT_SECONDS` | No | `10` | |

Update `apps/api/.env.example` to include all of these.

---

## 8. Observability

### 8.1 Structured logs

```python
# All F1 services log structured events
logger.info("spec_fetch_started", user_id=str(user_id), url=url, request_id=request_id)
logger.info("spec_fetch_succeeded", user_id=str(user_id), url=url, size_bytes=len(content), endpoint_count=count, request_id=request_id, duration_ms=duration)
logger.error("spec_fetch_failed", user_id=str(user_id), url=url, error_code="TIMEOUT", error=str(e), request_id=request_id)

logger.info("tools_extracted", server_id=str(server_id), total=len(tools), selected=sum(t.selected for t in tools), request_id=request_id)
logger.info("tool_selected", user_id=str(user_id), server_id=str(server_id), tool_name=name, action="select"|"deselect", request_id=request_id)
logger.info("server_built", user_id=str(user_id), server_id=str(server_id), tools_count=count, request_id=request_id)
```

### 8.2 Metrics (counted in DB, not Prometheus yet)

- `mcp_servers.total_calls` — incremented by gateway (F4)
- `mcp_servers.monthly_calls` — incremented by gateway (F4)
- `spec_sources.endpoint_count` — at parse time
- We can derive total_specs_fetched, total_servers_built from these

### 8.3 Sentry

If `SENTRY_DSN` set, exception from `openapi_fetcher.parse_content()` automatically captured. Add breadcrumb:
```python
sentry_sdk.add_breadcrumb(category="spec_ingestion", message=f"Parsed {endpoint_count} tools", level="info")
```

---

## 9. Edge Cases & Failure Modes

| Edge case | Detection | Response |
|---|---|---|
| URL returns 404 | httpx status check | Return 502 with `error_code=UPSTREAM_ERROR`, suggestion: "Spec URL returned 404. Verify the URL is correct." |
| URL returns HTML (not JSON/YAML) | Content-Type + first byte check | Return 422 with `error_code=INVALID_SPEC`, suggestion: "The URL didn't return JSON or YAML. Did you mean to upload a file?" |
| URL behind private IP (SSRF attempt) | DNS resolution + IP check | Return 400 with `error_code=INVALID_URL`, suggestion: "URLs to private IPs are not allowed." |
| Spec is 5.5MB | `len(content)` check | Return 413 with `error_code=TOO_LARGE`, suggestion: "Spec exceeds 5MB limit." |
| Spec is valid OpenAPI 2.0 | Version check | Return 422 with `error_code=UNSUPPORTED_VERSION`, suggestion: "We support OpenAPI 3.0+. Convert with swagger2openapi." |
| Spec has circular $refs | prance resolution | Log warning, return tools with `$ref` markers, frontend shows banner |
| Spec has 500+ endpoints | Endpoint count | Log warning, allow user to proceed, but show prominent "consider selecting 10-30 key tools" |
| User selects all 500 tools | Frontend check | Show confirm modal: "You've selected 500 tools. This may produce a low-quality server. Consider selecting 10-30 key tools." |
| Concurrent spec fetches (same user, same URL) | Frontend debounce | Disable fetch button while in-flight |
| Network error during upload | S3 client catches | Return 502, log error |
| S3 bucket not configured | S3 client init check | Return 500 with helpful message: "Spec storage not configured. Set S3_* env vars." |
| `ENCRYPTION_KEY` not set in prod | `RuntimeError` at startup | App fails to start with clear error |
| User adds 2 credentials with same env_var_name | Service check | Return 409 Conflict, suggest using rotate endpoint |
| Tool name collision after auto-generation | Service check | Auto-suffix `_2`, `_3`, etc. |
| Spec has parameters with same name in path and query | Schema builder | Prefix query with `query_`, path with `path_` to avoid collision |
| Spec has request body with no JSON content-type | Service check | Tool has no `request_body_schema`, documented in description |
| User doesn't provide base_url | Frontend validation | Form error: "Base URL is required" |
| User provides base_url with trailing slash | Frontend normalization | Strip trailing slash before save |
| User provides base_url with internal IP | Service check | Return 400 (SSRF prevention) |

---

## 10. Definition of Done

- [ ] `apps/api/pyproject.toml` has new deps
- [ ] Migration `0009_add_spec_sources.py` created and reversible
- [ ] `app/models/spec.py` exists and exports from `models/__init__.py`
- [ ] `app/core/encryption.py` implemented and unit-tested
- [ ] `app/core/s3_client.py` implemented and unit-tested (with moto)
- [ ] `app/services/openapi_fetcher.py` implemented with 8 tests passing
- [ ] `app/services/spec_analyzer.py` implemented with 12 tests passing
- [ ] `app/services/tool_generator.py` implemented with 6 tests passing
- [ ] `app/services/credential_service.py` implemented with 6 tests passing
- [ ] `app/repositories/spec_repo.py` and `credential_repo.py` implemented
- [ ] `app/api/v1/endpoints/specs.py` implemented with 10 endpoint tests passing
- [ ] `app/api/v1/endpoints/credentials.py` implemented
- [ ] `app/api/v1/endpoints/tools.py` implemented
- [ ] All env vars added to `apps/api/.env.example`
- [ ] All Sentry / log breadcrumbs added
- [ ] Frontend: `apps/web/package.json` has new deps
- [ ] Frontend: all shadcn primitives added (`tabs`, `scroll-area`, `switch`, `toggle-group`)
- [ ] Frontend: `lib/api.ts` extended with specs + tools + credentials methods
- [ ] Frontend: `lib/validators.ts` has specUrlSchema, toolSelectionSchema
- [ ] Frontend: `hooks/use-spec.ts`, `use-tools.ts`, `use-credentials.ts`, `use-build-status.ts` implemented
- [ ] Frontend: builder components (`spec-input`, `tool-workspace`, `tool-row`, etc.) implemented with Vitest tests
- [ ] Frontend: `app/(dashboard)/servers/new/page.tsx` refactored to multi-step flow
- [ ] Frontend: `app/(dashboard)/servers/[slug]/page.tsx` replaced with tabbed layout
- [ ] Frontend: `app/(dashboard)/servers/[slug]/tools/page.tsx` implemented (tool list with checkboxes, description editor)
- [ ] Playwright E2E tests pass: create-from-url, upload-spec, invalid-spec
- [ ] Manual test: paste Stripe OpenAPI URL → see ~150 tools → select 20 → save → land on server detail
- [ ] Manual test: upload a malformed spec → see specific line/column error
- [ ] CI: `pnpm type-check && pnpm lint && pnpm test` all pass
- [ ] Backend tests: 50+ tests for F1
- [ ] Frontend: no `any`, no `@ts-ignore`, no `@ts-expect-error`
- [ ] Backend: no `Any` types, no `as any`, no `# type: ignore`

---

## 11. Build Sequence (for AI agents)

Each step is atomic. Verify before moving to next.

### Step 1: Foundation
- [ ] Add deps to `apps/api/pyproject.toml`: `openapi-spec-validator`, `prance`, `cryptography`, `boto3` (or `aioboto3`), `tenacity`
- [ ] Add deps to dev: `respx`, `freezegun`, `moto[s3]`
- [ ] Run `uv sync` and verify
- [ ] Add env vars to `apps/api/.env.example`

### Step 2: Encryption core
- [ ] Create `app/core/encryption.py`
- [ ] Create `app/core/config.py` addition: `ENCRYPTION_KEY: str = ""` with validator (must be non-empty in production)
- [ ] Create `tests/test_encryption.py` with 4 tests
- [ ] Run `pytest tests/test_encryption.py -v` — all pass

### Step 3: S3 client
- [ ] Create `app/core/r2_client.py` with `aioboto3` (NOT `boto3`, which is sync)
- [ ] Create `tests/test_r2_client.py` with 4 tests using moto
- [ ] Run `pytest tests/test_r2_client.py -v` — all pass

### Step 4: Spec model
- [ ] Create `app/models/spec.py` with `SpecSource` model
- [ ] Update `app/models/__init__.py` to export it
- [ ] Create migration `0009_add_spec_sources.py`
- [ ] Run `alembic upgrade head` — succeeds
- [ ] Run `alembic downgrade -1` then `alembic upgrade head` — both succeed

### Step 5: OpenAPI fetcher service
- [ ] Create `app/services/openapi_fetcher.py` (~150 lines)
- [ ] Create `tests/test_openapi_fetcher.py` with 8 tests using `respx` for HTTP mocking
- [ ] Use a sample real spec (small, e.g., a petstore variant) for happy path tests
- [ ] Test invalid URL, timeout, too large, invalid JSON, invalid YAML
- [ ] Run `pytest tests/test_openapi_fetcher.py -v` — all pass

### Step 6: Spec analyzer service
- [ ] Create `app/services/spec_analyzer.py` (~200 lines)
- [ ] Create `tests/test_spec_analyzer.py` with 12 tests
- [ ] Test with multiple real OpenAPI fixtures (saved as JSON files in `tests/fixtures/`)
- [ ] Run `pytest tests/test_spec_analyzer.py -v` — all pass

### Step 7: Tool generator service
- [ ] Create `app/services/tool_generator.py` (~100 lines)
- [ ] Create `tests/test_tool_generator.py` with 6 tests
- [ ] Run `pytest tests/test_tool_generator.py -v` — all pass

### Step 8: Credential service
- [ ] Create `app/services/credential_service.py` (~120 lines)
- [ ] Create `app/repositories/credential_repo.py` (~80 lines)
- [ ] Create `tests/test_credential_service.py` with 6 tests
- [ ] Run `pytest tests/test_credential_service.py -v` — all pass

### Step 9: Schemas
- [ ] Create `app/schemas/openapi_spec.py` with all schemas from § 4.4
- [ ] Create `app/schemas/credential.py`
- [ ] Create `app/schemas/tool.py`
- [ ] Add `__all__` exports

### Step 10: Endpoints
- [ ] Create `app/repositories/spec_repo.py`
- [ ] Create `app/api/v1/endpoints/specs.py` with 5 endpoints
- [ ] Create `app/api/v1/endpoints/tools.py` with 3 endpoints
- [ ] Create `app/api/v1/endpoints/credentials.py` with 4 endpoints
- [ ] Update `app/api/v1/router.py` to include new routers
- [ ] Create `tests/test_specs_endpoints.py` with 10 tests
- [ ] Run `pytest tests/test_specs_endpoints.py -v` — all pass
- [ ] Run full suite: `pytest -v` — all pass
- [ ] Run `mypy apps/api` — clean
- [ ] Run `ruff check apps/api` — clean

### Step 11: Frontend deps
- [ ] Add to `apps/web/package.json`: `monaco-editor`, `@monaco-editor/react`, `react-resizable-panels`, `@radix-ui/react-{tabs,scroll-area,switch,toggle-group}`
- [ ] Add to devDependencies: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`
- [ ] Run `pnpm install`
- [ ] Add new shadcn primitives by copying from shadcn registry
- [ ] Set up Vitest config (`apps/web/vitest.config.ts`)

### Step 12: Frontend shared components
- [ ] Create `components/shared/http-method-badge.tsx` (color-coded by method)
- [ ] Create `components/shared/copy-to-clipboard.tsx`
- [ ] Create `components/shared/empty-state.tsx`
- [ ] Create `components/shared/loading-spinner.tsx`
- [ ] Write Vitest tests for each

### Step 13: Frontend types
- [ ] Add to `src/types/api.ts`: `ToolDefinition`, `SpecUploadResponse`, `SpecFetchErrorResponse`, `ToolSelectionRequest`, `ToolResponse`, `CredentialResponse`, etc.
- [ ] Add to `src/lib/validators.ts`: `specUrlSchema`, `toolSelectionSchema`

### Step 14: Frontend API client
- [ ] Update `src/lib/api.ts` to add `api.specs.*`, `api.servers.build`, `api.servers.listTools`, `api.servers.updateTool`, `api.servers.credentials.*`

### Step 15: Frontend hooks
- [ ] Create `src/hooks/use-spec.ts` (4 hooks)
- [ ] Create `src/hooks/use-tools.ts` (2 hooks)
- [ ] Create `src/hooks/use-credentials.ts` (4 hooks)
- [ ] Create `src/hooks/use-build-status.ts` (SSE-based, 1 hook)

### Step 16: Builder UI — Step 1 (Spec input)
- [ ] Create `components/builder/spec-input.tsx` (tabbed: URL vs Upload)
- [ ] Create `components/builder/spec-url-input.tsx`
- [ ] Create `components/builder/spec-upload-input.tsx`
- [ ] Create `components/builder/spec-validation-errors.tsx`

### Step 17: Builder UI — Step 2 (Tool workspace)
- [ ] Create `components/builder/tool-workspace.tsx`
- [ ] Create `components/builder/tool-tag-group.tsx` (collapsible)
- [ ] Create `components/builder/tool-row.tsx` (checkbox + method badge + path + warnings)
- [ ] Create `components/builder/tool-warnings.tsx`
- [ ] Create `components/builder/tool-summary.tsx`
- [ ] Create `components/builder/large-spec-warning.tsx`

### Step 18: Builder UI — Step 3 (Server config)
- [ ] Create `components/builder/server-config-form.tsx`
- [ ] Create `components/builder/auth-scheme-selector.tsx`
- [ ] Create `components/builder/credential-input.tsx`
- [ ] Create `components/builder/credential-test-result.tsx`

### Step 19: Builder UI — Step 4 (Build progress)
- [ ] Create `components/builder/build-progress-modal.tsx` (SSE-driven)
- [ ] Create `components/builder/build-step-indicator.tsx`

### Step 20: Refactor `/dashboard/servers/new` page
- [ ] Update `app/(dashboard)/servers/new/page.tsx` to use the new components
- [ ] Multi-step state machine: spec → tools → config → build
- [ ] Each step validates before allowing next
- [ ] On final submit, calls `select-tools` then `build` then redirects to server detail

### Step 21: Server detail page
- [ ] Replace placeholder at `app/(dashboard)/servers/[slug]/page.tsx`
- [ ] New layout: tabs for Tools / Playground / Analytics / Settings / Security
- [ ] F1 only fills the Tools tab; others are "Coming in F2/F3/F6"
- [ ] Tools tab shows: tool list with checkboxes, description editor (basic, no AI yet — F2)

### Step 22: Vitest tests for builder components
- [ ] Run `pnpm test` — all pass
- [ ] At least 1 test per new component

### Step 23: Playwright E2E
- [ ] Add `apps/web/playwright.config.ts`
- [ ] Add `tests/e2e/01-create-from-url.spec.ts`
- [ ] Add `tests/e2e/02-upload-spec.spec.ts`
- [ ] Add `tests/e2e/03-invalid-spec.spec.ts`
- [ ] Run `pnpm playwright test` — all pass

### Step 24: Update CI
- [ ] Update `.github/workflows/ci.yml` to run frontend tests
- [ ] Update CI to run Playwright
- [ ] Verify all green on a test PR

### Step 25: Update shared types
- [ ] Start backend, run `cd packages/shared-types && pnpm fetch && pnpm generate`
- [ ] Verify `api-types.d.ts` includes new endpoints

### Step 26: Update AGENTS.md
- [ ] Add to the "Phase 1 done" section: "✅ F1 OpenAPI Ingestion"
- [ ] Note any new conventions or patterns introduced

### Step 27: Manual end-to-end test
- [ ] Run `pnpm dev` (full stack)
- [ ] Register a new user
- [ ] Click "Create Server" → "From OpenAPI URL"
- [ ] Paste `https://petstore3.swagger.io/api/v3/openapi.json` (public test spec)
- [ ] Wait for parse
- [ ] Verify tool workspace shows ~19 tools grouped by tag
- [ ] Toggle DELETE endpoints off (default)
- [ ] Configure auth (none for petstore)
- [ ] Click "Build"
- [ ] Verify redirect to server detail
- [ ] Verify tools tab shows all selected tools with descriptions

**Total estimated time:** 4-6 days for one engineer.

---

## 12. Open Questions

- **Q1 (P1):** When user uploads a spec, should we auto-name the server from `info.title` (default) or require a name? (Decision: pre-fill, allow override.)
- **Q2 (P1):** When user pastes a URL that's an HTML page (not JSON/YAML), do we attempt to parse the HTML to find the spec link? (Decision: no for v1.0 — fail with clear error. Add in v1.1.)
- **Q3 (P2):** Should the builder pre-warm the spec fetch on URL paste (debounce 500ms) or require explicit button click? (Decision: require click. Less surprising, easier to debug.)
- **Q4 (P2):** What happens if user has 2 specs with same `info.title`? (Decision: server name must be unique per user. Show conflict error.)

---

*See `03-FEATURE-AI-DESCRIPTION-ENGINE.md` for how the AI Engine reads the tools_config this feature produces.*
