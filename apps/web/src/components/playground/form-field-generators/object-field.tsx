"use client";

import { Label } from "@/components/ui/label";
import { FormField } from "./index";
import type { FieldProps, JSONSchema7 } from "./types";

/**
 * Object field — renders a nested group of fields from `properties`.
 * Recursively generates child fields via FormField.
 */
export function ObjectField({
  schema,
  name,
  value,
  onChange,
  required = false,
  description,
  error,
  label,
  depth = 0,
}: FieldProps) {
  const displayLabel = label ?? name.split(".").pop() ?? name;
  const properties = (schema.properties as Record<string, JSONSchema7>) ?? {};
  const requiredFields = Array.isArray(schema.required) ? schema.required : [];
  const objValue = (typeof value === "object" && value !== null && !Array.isArray(value))
    ? (value as Record<string, unknown>)
    : {};

  const updateProperty = (key: string, propValue: unknown) => {
    const next = { ...objValue, [key]: propValue };
    onChange(next);
  };

  const propertyEntries = Object.entries(properties);

  return (
    <div
      className="space-y-3 rounded-md border border-dashed border-border p-3"
      style={{ marginLeft: depth * 16 }}
    >
      <Label className="text-sm font-medium">
        {displayLabel}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {description && (
        <p id={`${name}-desc`} className="text-xs text-muted-foreground">
          {description}
        </p>
      )}

      {propertyEntries.map(([key, propSchema]) => {
        const propName = name ? `${name}.${key}` : key;
        const isRequired = requiredFields.includes(key);
        const propDescription =
          typeof propSchema === "object" && propSchema !== null
            ? (propSchema as JSONSchema7).description
            : undefined;

        return (
          <FormField
            key={key}
            schema={propSchema}
            name={propName}
            value={objValue[key]}
            onChange={(v) => updateProperty(key, v)}
            required={isRequired}
            description={propDescription}
            label={key}
            depth={depth + 1}
          />
        );
      })}

      {propertyEntries.length === 0 && (
        <p className="text-xs text-muted-foreground italic">
          No properties defined
        </p>
      )}

      {error && (
        <p id={`${name}-error`} className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
