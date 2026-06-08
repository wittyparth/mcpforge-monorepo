# ruff: noqa: E501
"""Prompt templates for the AI Description Engine (F2).

These prompts implement the quality framework from arxiv 2602.18914
to rewrite MCP tool descriptions for maximum LLM selection probability.
"""

SYSTEM_PROMPT = """You are an expert AI tool description engineer specializing in the Model Context Protocol (MCP) ecosystem.

Your task is to rewrite tool descriptions so that LLMs (Claude, GPT, Gemini, etc.) select the correct tool with high reliability. Every tool description you write directly affects whether an AI agent picks the right tool in complex scenarios.

Quality dimensions (from arxiv 2602.18914 — each must be explicitly addressed):

1. FUNCTIONALITY (0-30): Does the description accurately convey WHAT the tool does and WHEN to use it? Include the specific action the tool performs, the data it operates on, and the conditions under which it should be invoked. Highest weight because LLMs most frequently fail on selecting the wrong tool for the intended task.

2. ACCURACY (0-25): Are parameter names, types, constraints, and defaults described correctly? Every parameter in the schema must be accounted for. Do NOT fabricate parameters that do not exist in the original schema. Do NOT omit required parameters.

3. COMPLETENESS (0-25): Are ALL parameters described (including optionals)? Is the return value described? Missing return value descriptions are one of the top-3 failure modes in production MCP servers.

4. CONTEXT (0-20): Does the description help an LLM decide BETWEEN this tool and its siblings? Include disambiguation cues: "Use this when...", "Do NOT use this for...", and comparisons with related tools. This dimension separates good descriptions from great ones.

Output rules:
- Respond ONLY with a valid JSON object. No preamble, no explanation, no markdown fences.
- Every field in the output schema must be present. Empty strings and empty lists are acceptable defaults.
- Be concise — every token costs money and consumes context window. One to three sentences per description is ideal.
- For parameter descriptions: one clear sentence per parameter. Include an example value when the format is non-obvious.
- The return description should describe what the caller receives, including edge cases (empty results, error structures, pagination metadata)."""

USER_PROMPT_TEMPLATE = """<original_tool>
Name: {tool_name}
Description: {tool_description}
HTTP Method: {method}
Path: {path}
Tags: {tags}
Parameters:
{parameters_formatted}
Request Body Schema:
{request_body_schema}
Response Schemas:
{response_schemas}
Security Requirements:
{security_requirements}
</original_tool>

<sibling_tools_for_disambiguation>
{sibling_tools_formatted}
</sibling_tools_for_disambiguation>

<examples>
{few_shot_examples}
</examples>

<instructions>
Follow these steps in order:

1. Analyze the original tool. Understand exactly what it does — read the HTTP method, path, parameters, and response schema thoroughly.

2. Evaluate the original description against the four quality dimensions:
   - FUNCTIONALITY: Does it say what the tool does and when to use it?
   - ACCURACY: Are parameters described correctly?
   - COMPLETENESS: Are all parameters and return value described?
   - CONTEXT: Can an LLM distinguish this from its siblings?

3. Decide whether to rename the tool. The name should be a verb_noun pair (e.g., "get_user", "search_products", "create_order"). If the original name is too generic (e.g., "get", "list", "search"), rename it. If the original name is already descriptive (e.g., "getUserById"), keep it or make minor adjustments.

4. Rewrite the tool description to address ALL four quality dimensions:
   - Start with what the tool does and when to use it (FUNCTIONALITY)
   - Include parameter context inline where helpful (ACCURACY)
   - Mention the return value briefly (COMPLETENESS)
   - Add disambiguation from siblings (CONTEXT)

5. For each parameter, write a clear description. Include the expected format, constraints (min/max, enum values), and an example when helpful. Mark required parameters clearly.

6. Write the return value description. Describe the structure of what is returned, including pagination fields, error shapes, and edge cases like empty results.

7. Score your own output on all four dimensions and provide a total (0-100) and a badge ("excellent", "good", "fair", "poor"). List the concrete improvements you made.

Respond with valid JSON matching this schema exactly:
{{
  "enhanced_name": "suggested new name or null if unchanged",
  "enhanced_description": "your rewritten description",
  "enhanced_parameters": [
    {{"name": "...", "description": "...", "required": true, "type": "..."}}
  ],
  "enhanced_return_description": "description of return value",
  "quality_score": {{
    "functionality": 0-30,
    "accuracy": 0-25,
    "completeness": 0-25,
    "context": 0-20,
    "total": 0-100,
    "badge": "excellent|good|fair|poor"
  }},
  "improvements": ["improvement 1", "improvement 2"]
}}
</instructions>"""

FEW_SHOT_EXAMPLES: list[dict[str, object]] = [
    {
        "input": {
            "tool_name": "get",
            "tool_description": "Retrieves a resource by its unique identifier",
            "method": "GET",
            "path": "/api/v1/items/{item_id}",
            "tags": ["Items"],
            "parameters": [
                {
                    "name": "item_id",
                    "type": "string",
                    "required": True,
                    "description": "The unique identifier of the item",
                }
            ],
            "request_body": None,
            "responses": {
                "200": {
                    "description": "The requested item",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "price": {"type": "number"},
                        },
                    },
                }
            },
            "security": [{"api_key": []}],
        },
        "output": {
            "enhanced_name": "get_item_by_id",
            "enhanced_description": "Retrieve a single item from the catalog by its unique ID. Use this when you know the specific item ID and need full details including name, price, and availability. Do NOT use this for searching or listing items — use search_items or list_items instead.",
            "enhanced_parameters": [
                {
                    "name": "item_id",
                    "description": "The unique identifier (UUID) of the item to retrieve. Example: 'prod_abc123'. Required.",
                    "required": True,
                    "type": "string",
                }
            ],
            "enhanced_return_description": "Returns the full item object with id, name, price, currency, in_stock, and category fields. Returns null with a 404 status if no item matches the given ID.",
            "quality_score": {
                "functionality": 28,
                "accuracy": 23,
                "completeness": 22,
                "context": 18,
                "total": 91,
                "badge": "excellent",
            },
            "improvements": [
                "Renamed from generic 'get' to descriptive 'get_item_by_id'",
                "Added disambiguation guidance ('Do NOT use this for searching')",
                "Added return value description with edge case handling",
                "Enhanced parameter description with example value and explicit 'Required' label",
            ],
        },
    },
    {
        "input": {
            "tool_name": "create",
            "tool_description": "Creates a new resource",
            "method": "POST",
            "path": "/api/v1/items",
            "tags": ["Items"],
            "parameters": [
                {
                    "name": "name",
                    "type": "string",
                    "required": True,
                    "description": "Item name",
                },
                {
                    "name": "price",
                    "type": "number",
                    "required": True,
                    "description": "Item price",
                },
                {
                    "name": "category",
                    "type": "string",
                    "required": False,
                    "description": "Item category",
                },
                {
                    "name": "description",
                    "type": "string",
                    "required": False,
                    "description": "Item description",
                },
            ],
            "request_body": {
                "type": "object",
                "required": ["name", "price"],
                "properties": {
                    "name": {"type": "string", "maxLength": 200},
                    "price": {"type": "number", "minimum": 0},
                    "category": {"type": "string", "enum": ["electronics", "clothing", "food"]},
                    "description": {"type": "string", "maxLength": 2000},
                },
            },
            "responses": {
                "201": {
                    "description": "Item created successfully",
                    "schema": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}},
                },
                "400": {"description": "Validation error"},
            },
            "security": [{"bearer_auth": []}],
        },
        "output": {
            "enhanced_name": "create_item",
            "enhanced_description": "Create a new item in the catalog with name, price, and optional category and description. Use this to add new products to the inventory. Returns the created item with its assigned ID. Requires authentication. Do NOT use this to update existing items — use update_item instead.",
            "enhanced_parameters": [
                {
                    "name": "name",
                    "description": "Display name of the item. Max 200 characters. Required.",
                    "required": True,
                    "type": "string",
                },
                {
                    "name": "price",
                    "description": "Price of the item in the smallest currency unit (e.g., cents). Must be zero or positive. Required.",
                    "required": True,
                    "type": "number",
                },
                {
                    "name": "category",
                    "description": "Product category. Must be one of: electronics, clothing, food. Optional — defaults to None.",
                    "required": False,
                    "type": "string",
                },
                {
                    "name": "description",
                    "description": "Detailed description of the item. Max 2000 characters. Optional.",
                    "required": False,
                    "type": "string",
                },
            ],
            "enhanced_return_description": "Returns the newly created item object with its server-assigned id and the submitted fields. Returns a 400 validation error if required fields are missing or constraints are violated.",
            "quality_score": {
                "functionality": 29,
                "accuracy": 25,
                "completeness": 25,
                "context": 18,
                "total": 97,
                "badge": "excellent",
            },
            "improvements": [
                "Renamed from generic 'create' to 'create_item'",
                "Added disambiguation from update_item",
                "Documented all optional parameters with defaults",
                "Added constraint details (maxLength, enum values, minimum) inline in parameter descriptions",
                "Added return value description covering both success and error responses",
            ],
        },
    },
    {
        "input": {
            "tool_name": "search",
            "tool_description": "Search for items",
            "method": "GET",
            "path": "/api/v1/items/search",
            "tags": ["Items"],
            "parameters": [
                {
                    "name": "q",
                    "type": "string",
                    "required": True,
                    "description": "Search query",
                },
                {
                    "name": "category",
                    "type": "string",
                    "required": False,
                    "description": "Filter by category",
                },
                {
                    "name": "min_price",
                    "type": "number",
                    "required": False,
                    "description": "Minimum price filter",
                },
                {
                    "name": "max_price",
                    "type": "number",
                    "required": False,
                    "description": "Maximum price filter",
                },
                {
                    "name": "sort",
                    "type": "string",
                    "required": False,
                    "description": "Sort order",
                },
                {
                    "name": "page",
                    "type": "integer",
                    "required": False,
                    "description": "Page number",
                },
                {
                    "name": "per_page",
                    "type": "integer",
                    "required": False,
                    "description": "Results per page",
                },
            ],
            "request_body": None,
            "responses": {
                "200": {
                    "description": "Paginated search results",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "items": {"type": "array", "items": {"type": "object"}},
                            "total": {"type": "integer"},
                            "page": {"type": "integer"},
                            "per_page": {"type": "integer"},
                            "has_more": {"type": "boolean"},
                        },
                    },
                }
            },
            "security": [{"api_key": []}],
        },
        "output": {
            "enhanced_name": "search_items",
            "enhanced_description": "Search the item catalog by keyword with optional filters for category and price range. Supports pagination and sorting. Use this when users want to find items matching specific criteria like 'wireless headphones under $50'. Do NOT use this to retrieve a single known item — use get_item_by_id instead.",
            "enhanced_parameters": [
                {
                    "name": "q",
                    "description": "Free-text search query matching against item name and description. Supports partial and fuzzy matches. Example: 'blue running shoes'. Required.",
                    "required": True,
                    "type": "string",
                },
                {
                    "name": "category",
                    "description": "Filter results to a specific category. Must be one of: electronics, clothing, food. Optional.",
                    "required": False,
                    "type": "string",
                },
                {
                    "name": "min_price",
                    "description": "Minimum price in cents. Filters out items priced below this value. Optional.",
                    "required": False,
                    "type": "number",
                },
                {
                    "name": "max_price",
                    "description": "Maximum price in cents. Filters out items priced above this value. Optional.",
                    "required": False,
                    "type": "number",
                },
                {
                    "name": "sort",
                    "description": "Sort order for results. One of: 'price_asc', 'price_desc', 'name_asc', 'name_desc', 'newest'. Defaults to 'newest'. Optional.",
                    "required": False,
                    "type": "string",
                },
                {
                    "name": "page",
                    "description": "Page number for paginated results. Starts at 1. Defaults to 1. Optional.",
                    "required": False,
                    "type": "integer",
                },
                {
                    "name": "per_page",
                    "description": "Number of results per page. Max 100. Defaults to 20. Optional.",
                    "required": False,
                    "type": "integer",
                },
            ],
            "enhanced_return_description": "Returns a paginated result set with: items (array of matching item objects), total (total match count across all pages), page (current page number), per_page (results per page), and has_more (boolean indicating additional pages). Returns empty items array with total=0 if no matches found.",
            "quality_score": {
                "functionality": 30,
                "accuracy": 24,
                "completeness": 25,
                "context": 20,
                "total": 99,
                "badge": "excellent",
            },
            "improvements": [
                "Renamed from generic 'search' to 'search_items'",
                "Added disambiguation from get_item_by_id with explicit 'Do NOT use' guidance",
                "Documented ALL optional parameters with defaults and constraints",
                "Added sort enum values explicitly",
                "Documented pagination fields in return description",
                "Added example values for key parameters (q, min_price, max_price, sort)",
                "Added return value description covering empty results edge case",
            ],
        },
    },
]
