# OpenAPI Spec Parsing — Reference

> **For AI agents:** Reference for parsing and validating OpenAPI 3.0+ specs in F1. Use when building the `openapi_fetcher.py` and `spec_analyzer.py` services.

---

## 1. Libraries — Decision Matrix

### 1.1 `openapi-spec-validator`
- **Latest:** v0.9.0 (May 20, 2026)
- **PyPI:** https://pypi.org/project/openapi-spec-validator/0.9.0/
- **Supports:** OpenAPI 2.0, 3.0, 3.1, 3.2
- **Python:** >=3.10
- **Usage:** `validate(spec_dict)` — validates full spec compliance
- **Backend:** Supports `jsonschema` (pure Python) or `jsonschema-rs` (Rust, faster)
- **Env config:** `OPENAPI_SPEC_VALIDATOR_RESOLVED_CACHE_MAXSIZE=2048`
- **Gotcha:** v0.8.x had rapid releases (0.8.0 → 0.8.5 in 2 months) — v0.9.0 is stable

```python
from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

try:
    validate(spec_dict)
except OpenAPIValidationError as e:
    # e.errors is a list of ValidationError objects
    for err in e.errors:
        print(f"  at {'/'.join(str(p) for p in err.absolute_path)}: {err.message}")
```

### 1.2 `prance`
- **Latest:** v25.4.8.0
- **Docs:** https://prance.readthedocs.io/
- **Purpose:** Validates **AND resolves** `$ref` references
- **Key feature:** `ResolvingParser` inlines all `$ref` references into a single dict
- **Partial resolution:** `RESOLVE_HTTP` | `RESOLVE_FILES` — choose which refs to resolve
- **Backends:** `openapi-spec-validator` (recommended), `swagger-spec-validator`, `flex`
- **Gotcha:** Supports OpenAPI 2.0 and 3.0.x; may lag on 3.2

```python
from prance import ResolvingParser

parser = ResolvingParser(
    spec_dict=spec_dict,          # or spec_url=
    backend="openapi-spec-validator",
    strict=False,                  # don't fail on first error
    resolve_types=ResolvingParser.RESOLVE_ALL,  # or RESOLVE_HTTP / RESOLVE_FILES
)
spec = parser.specification  # fully resolved dict
```

### 1.3 `openapi-core`
- Companion to `openapi-spec-validator`
- Adds request/response validation at runtime
- Useful for validating MCP tool call arguments against the original OpenAPI schema
- **MCPForge decision:** Don't use. We do our own JSON Schema validation against the tool's `inputSchema`.

### 1.4 `jsonschema`
- Validate MCP tool call arguments against JSON Schema
- `jsonschema.validate(instance=args, schema=input_schema)`
- Supports draft-07, 2020-12

### 1.5 `jsonref` (fallback)
```python
import jsonref
resolved = jsonref.replace_refs(spec_dict, proxies=False)
# Cycle detection via proxies=False
```

## 2. Recommended Pipeline for MCPForge

```python
from prance import ResolvingParser
from openapi_spec_validator import validate as validate_spec
import yaml, json

# Step 1: Fetch (via httpx in our openapi_fetcher service)
# content: bytes, content_type: str

# Step 2: Detect format and parse
is_json = (
    content_type and "json" in content_type.lower()
) or content.lstrip().startswith(b"{")

try:
    if is_json:
        spec_dict = json.loads(content)
    else:
        spec_dict = yaml.safe_load(content)  # safe_load, NOT load
except (json.JSONDecodeError, yaml.YAMLError) as e:
    raise SpecParseError(str(e), line=...)

# Step 3: Validate
try:
    validate_spec(spec_dict)
except OpenAPIValidationError as e:
    raise SpecValidationError(
        message=str(e),
        details=[{"path": "...", "message": err.message} for err in e.errors]
    )

# Step 4: Check version
version = spec_dict.get("openapi", "")
if not version.startswith("3."):
    raise UnsupportedSpecVersionError(
        f"Only OpenAPI 3.0+ supported. Got: {version}",
        suggestion="Convert Swagger 2.0 to OpenAPI 3.0 using swagger2openapi",
    )

# Step 5: Resolve $refs
try:
    parser = ResolvingParser(spec_dict=spec_dict, backend="openapi-spec-validator", strict=False)
    resolved = parser.specification
except Exception as e:
    # Log and fall back to unresolved
    logger.warning("ref_resolution_failed", error=str(e))
    resolved = spec_dict

# Step 6: Extract tools
# ... (SpecAnalyzer logic)
```

## 3. Handling Large Specs (200+ endpoints)

- **Streaming:** OpenAPI specs are JSON/YAML — load the whole thing. Not designed for streaming.
- **Parallel processing:** Process endpoints in batches. Use `asyncio.gather()` for downstream API calls (AI Engine).
- **Prance caching:** `OPENAPI_SPEC_VALIDATOR_RESOLVED_CACHE_MAXSIZE=2048` helps with repeated resolution.
- **Memory:** A 200-endpoint spec is typically 1-5MB. Fine for a single process.

For very large specs (Stripe has ~700 endpoints, 5MB+):
- Loading: ~1-2 seconds
- $ref resolution: ~3-5 seconds
- Tool extraction: <1 second
- AI enhancement of 700 tools: ~10-15 minutes with 5-way concurrency at $0.008/tool = $5.60

## 4. Circular $ref Safety

**Prance** handles circular refs by limiting depth. Default behavior is to handle them safely.

**openapi-spec-validator** also handles them.

**Manual approach** (if needed):
```python
import jsonref
try:
    resolved = jsonref.replace_refs(spec_dict, proxies=False)
except jsonref.JsonRefError as e:
    # Circular ref detected
    logger.warning("circular_ref", error=str(e))
    # Fall back to partial resolution
    resolved = spec_dict
```

## 5. Common Spec Issues (real-world)

From analyzing 10,831 OpenAPI specs (per the MCP quality study ecosystem):

1. **Malformed YAML with tabs** — `yaml.safe_load` catches with line/column
2. **Circular `$ref` definitions** — handle gracefully
3. **Missing `operationId`** — auto-generate from `{method}_{path_segments}`
4. **Duplicate operation IDs** — auto-suffix `_2`, `_3`
5. **HTTP method in lowercase** — normalize to UPPERCASE
6. **`requestBody` without content-type** — skip
7. **Parameter in both `parameters` and `requestBody`** — prefer body
8. **`oneOf`/`anyOf`/`allOf` not handled** — flatten if possible
9. **Empty `paths`** — show warning
10. **200+ endpoints** — warn user

## 6. SSRF Prevention (for spec fetch)

When fetching user-provided URLs:

```python
def _is_valid_url(self, url: str) -> bool:
    parsed = urlparse(url)
    # Must be HTTPS (or http for localhost dev)
    if parsed.scheme not in ("https", "http"):
        return False
    # Resolve hostname
    try:
        ip = socket.gethostbyname(parsed.hostname)
    except socket.gaierror:
        return False
    # Block internal IPs (SSRF prevention)
    if ipaddress.ip_address(ip).is_private:
        return False
    return True
```

**Block list:**
- `10.0.0.0/8` (private)
- `172.16.0.0/12` (private)
- `192.168.0.0/16` (private)
- `127.0.0.0/8` (loopback)
- `169.254.0.0/16` (AWS metadata)
- `0.0.0.0/8`
- `::1/128` (IPv6 loopback)
- `fc00::/7` (IPv6 ULA)
- `fe80::/10` (IPv6 link-local)

## 7. From OpenAPI Operation to MCP Tool Definition

```python
def build_tool_from_operation(path: str, method: str, operation: dict, spec: dict) -> ToolDefinition:
    op_id = operation.get("operationId")
    name = op_id or name_from_path(method, path)
    
    params = extract_parameters(operation.get("parameters", []), spec)
    body_schema = extract_request_body_schema(operation.get("requestBody"), spec)
    response_schemas = extract_responses(operation.get("responses", {}), spec)
    
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
```

## 8. MCP inputSchema Generation

The tool's `inputSchema` (JSON Schema 2020-12) combines:
- Path parameters → top-level properties
- Query parameters → top-level properties
- Header parameters → top-level properties
- Body parameters → top-level properties (prefixed with `body_` to avoid collision)

```python
def build_input_schema(tool: ToolDefinition) -> dict:
    properties = {}
    required = []
    
    for param in tool.parameters:
        properties[param.name] = {**param.schema_, "description": param.description}
        if param.example is not None:
            properties[param.name]["example"] = param.example
        if param.required:
            required.append(param.name)
    
    if tool.request_body_schema:
        body_props = tool.request_body_schema.get("properties", {})
        for prop_name, prop_schema in body_props.items():
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

## 9. MCP Annotations

Each tool gets annotations per MCP spec:

```python
annotations = {
    "readOnlyHint": tool.method in {"GET", "HEAD", "OPTIONS"},
    "destructiveHint": tool.method == "DELETE",
    "idempotentHint": tool.method in {"GET", "PUT", "DELETE", "HEAD", "OPTIONS"},
    "openWorldHint": False,  # we control the API surface
}
```

## 10. Testing Patterns

### 10.1 Test fixtures
Save real spec files in `tests/fixtures/openapi/`:
- `petstore.json` (small, ~5 endpoints)
- `github.json` (medium, ~50 endpoints)
- `stripe.json` (large, ~150 endpoints, real-world)
- `malformed-yaml-tabs.json` (parse error case)
- `unsupported-2.0.json` (Swagger 2.0 case)
- `circular-refs.json` (circular $ref case)
- `private-ip-ssrf.json` (security test)

### 10.2 Mocking
- `respx` for httpx mocking (spec fetch)
- Real spec files for parser tests (no mocking needed)
- `moto` for S3/R2 mocking (storage)

### 10.3 Performance benchmark
- Parse 200-endpoint spec in <2 seconds
- Extract tools in <500ms
- Detect 200+ endpoint warning in <100ms

## 11. References

- **openapi-spec-validator:** https://pypi.org/project/openapi-spec-validator/
- **prance:** https://prance.readthedocs.io/
- **openapi-core:** https://openapi-core.readthedocs.io/
- **OpenAPI 3.0 spec:** https://swagger.io/specification/v3/
- **OpenAPI 3.1 spec:** https://spec.openapis.org/oas/v3.1.0
- **JSON Schema 2020-12:** https://json-schema.org/draft/2020-12
- **swagger2openapi:** https://www.npmjs.com/package/swagger2openapi (for Swagger 2.0 → 3.0 conversion)
