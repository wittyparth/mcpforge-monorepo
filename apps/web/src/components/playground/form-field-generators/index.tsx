"use client";

import { useState } from "react";
import { StringField } from "./string-field";
import { NumberField } from "./number-field";
import { BooleanField } from "./boolean-field";
import { SelectField } from "./select-field";
import { ArrayField } from "./array-field";
import { ObjectField } from "./object-field";
import { JsonField } from "./json-field";
import type { FieldProps, JSONSchema7 } from "./types";

// Re-export types and individual generators
export type { FieldProps, JSONSchema7 } from "./types";
export { StringField } from "./string-field";
export { NumberField } from "./number-field";
export { BooleanField } from "./boolean-field";
export { SelectField } from "./select-field";
export { ArrayField } from "./array-field";
export { ObjectField } from "./object-field";
export { JsonField } from "./json-field";

// ── Validation ───────────────────────────────────────────────────

function validateField(
  schema: JSONSchema7,
  value: unknown,
): string | null {
  // Required check
  if (value === undefined || value === null || value === "") {
    return null; // required is handled at the field level
  }

  // Type validation
  switch (schema.type) {
    case "string":
      if (typeof value !== "string") return "Expected a string";
      if (schema.minLength !== undefined && value.length < schema.minLength)
        return `Minimum ${schema.minLength} characters`;
      if (schema.maxLength !== undefined && value.length > schema.maxLength)
        return `Maximum ${schema.maxLength} characters`;
      if (schema.pattern !== undefined) {
        try {
          const regex = new RegExp(schema.pattern);
          if (!regex.test(value)) return `Must match pattern: ${schema.pattern}`;
        } catch {
          // Invalid pattern in schema — skip validation
        }
      }
      break;
    case "number":
    case "integer": {
      const num = typeof value === "number" ? value : parseFloat(String(value));
      if (Number.isNaN(num)) return "Expected a number";
      if (schema.type === "integer" && !Number.isInteger(num))
        return "Expected an integer";
      if (schema.minimum !== undefined && num < schema.minimum)
        return `Minimum is ${schema.minimum}`;
      if (schema.maximum !== undefined && num > schema.maximum)
        return `Maximum is ${schema.maximum}`;
      if (
        typeof schema.exclusiveMinimum === "number" &&
        num <= schema.exclusiveMinimum
      )
        return `Must be greater than ${schema.exclusiveMinimum}`;
      if (
        typeof schema.exclusiveMaximum === "number" &&
        num >= schema.exclusiveMaximum
      )
        return `Must be less than ${schema.exclusiveMaximum}`;
      break;
    }
    case "array":
      if (!Array.isArray(value)) return "Expected an array";
      if (schema.minItems !== undefined && value.length < schema.minItems)
        return `Minimum ${schema.minItems} items`;
      if (schema.maxItems !== undefined && value.length > schema.maxItems)
        return `Maximum ${schema.maxItems} items`;
      break;
    case "object":
      if (typeof value !== "object" || Array.isArray(value))
        return "Expected an object";
      break;
  }

  // Enum validation
  if (Array.isArray(schema.enum) && !schema.enum.includes(value as string)) {
    return `Must be one of: ${schema.enum.join(", ")}`;
  }

  return null;
}

// ── Main FormField Dispatcher ────────────────────────────────────

/**
 * Dynamic form field that auto-generates the appropriate input
 * based on the JSON Schema type.
 */
export function FormField({
  schema,
  name,
  value,
  onChange,
  required = false,
  description,
  error: externalError,
  label,
  depth = 0,
}: FieldProps) {
  const [localError, setLocalError] = useState<string | null>(null);
  const errorMessage = externalError ?? localError;

  const handleChange = (newValue: unknown) => {
    const validationError = validateField(schema, newValue);
    setLocalError(validationError);
    if (!validationError) {
      onChange(newValue);
    }
  };

  const effectiveDescription = description ?? (schema as JSONSchema7).description;

  // Enum → Select
  if (Array.isArray(schema.enum)) {
    return (
      <SelectField
        schema={schema}
        name={name}
        value={value}
        onChange={handleChange}
        required={required}
        description={effectiveDescription}
        error={errorMessage}
        label={label}
        depth={depth}
      />
    );
  }

  // Type-based dispatch
  switch (schema.type) {
    case "string":
      return (
        <StringField
          schema={schema}
          name={name}
          value={value}
          onChange={handleChange}
          required={required}
          description={effectiveDescription}
          error={errorMessage}
          label={label}
          depth={depth}
        />
      );

    case "number":
    case "integer":
      return (
        <NumberField
          schema={schema}
          name={name}
          value={value}
          onChange={handleChange}
          required={required}
          description={effectiveDescription}
          error={errorMessage}
          label={label}
          depth={depth}
        />
      );

    case "boolean":
      return (
        <BooleanField
          schema={schema}
          name={name}
          value={value}
          onChange={handleChange}
          required={required}
          description={effectiveDescription}
          error={errorMessage}
          label={label}
          depth={depth}
        />
      );

    case "array":
      return (
        <ArrayField
          schema={schema}
          name={name}
          value={value}
          onChange={handleChange}
          required={required}
          description={effectiveDescription}
          error={errorMessage}
          label={label}
          depth={depth}
        />
      );

    case "object":
      return (
        <ObjectField
          schema={schema}
          name={name}
          value={value}
          onChange={handleChange}
          required={required}
          description={effectiveDescription}
          error={errorMessage}
          label={label}
          depth={depth}
        />
      );

    default:
      // Complex/unknown types → JSON textarea fallback
      return (
        <JsonField
          schema={schema}
          name={name}
          value={value}
          onChange={handleChange}
          required={required}
          description={effectiveDescription}
          error={errorMessage}
          label={label}
          depth={depth}
        />
      );
  }
}

// ── Auto-Form Generator ──────────────────────────────────────────

export interface AutoFormProps {
  /** JSON Schema with `properties` defining the form fields */
  schema: JSONSchema7;
  /** Current form values */
  values: Record<string, unknown>;
  /** Callback when any field changes */
  onChange: (field: string, value: unknown) => void;
  /** Validation errors keyed by field name */
  errors?: Record<string, string>;
  /** Field name prefix (for nested objects) */
  prefix?: string;
  /** Nesting depth */
  depth?: number;
}

/**
 * Auto-generates a complete form from a JSON Schema object.
 * Uses FormField for each property.
 */
export function AutoForm({
  schema,
  values,
  onChange,
  errors = {},
  prefix = "",
  depth = 0,
}: AutoFormProps) {
  const properties = (schema.properties as Record<string, JSONSchema7>) ?? {};
  const requiredFields = Array.isArray(schema.required) ? schema.required : [];

  return (
    <div className="space-y-4">
      {Object.entries(properties).map(([key, propSchema]) => {
        const fieldName = prefix ? `${prefix}.${key}` : key;
        const isRequired = requiredFields.includes(key);

        return (
          <FormField
            key={fieldName}
            schema={propSchema}
            name={fieldName}
            value={values[key]}
            onChange={(v) => onChange(key, v)}
            required={isRequired}
            error={errors[fieldName]}
            label={key}
            depth={depth}
          />
        );
      })}
    </div>
  );
}
