"use client";

/**
 * Minimal JSON Schema 7 type — covers the subset used by MCP tool input schemas.
 * Avoids adding a `json-schema` dependency.
 */
export interface JSONSchema7 {
  type?: string | string[];
  description?: string;
  default?: unknown;
  enum?: unknown[];
  const?: unknown;

  // String constraints
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  format?: string;

  // Number constraints
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  multipleOf?: number;

  // Array constraints
  items?: JSONSchema7 | JSONSchema7[];
  minItems?: number;
  maxItems?: number;
  uniqueItems?: boolean;

  // Object constraints
  properties?: Record<string, JSONSchema7>;
  required?: string[];
  additionalProperties?: boolean | JSONSchema7;
  minProperties?: number;
  maxProperties?: number;

  // Composition
  allOf?: JSONSchema7[];
  oneOf?: JSONSchema7[];
  anyOf?: JSONSchema7[];
  not?: JSONSchema7;
  $ref?: string;
  $defs?: Record<string, JSONSchema7>;
}

/** Props shared by all form field generators */
export interface FieldProps {
  /** JSON Schema for this field */
  schema: JSONSchema7;
  /** Dot-notation field path (e.g. "address.city") */
  name: string;
  /** Current value */
  value: unknown;
  /** Callback when value changes */
  onChange: (value: unknown) => void;
  /** Whether the field is required */
  required?: boolean;
  /** Human-readable description */
  description?: string;
  /** Inline error message */
  error?: string | null;
  /** Field label (defaults to name) */
  label?: string;
  /** Nesting depth — increases indentation */
  depth?: number;
}
