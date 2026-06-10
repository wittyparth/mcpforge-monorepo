"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { FieldProps } from "./types";

/**
 * Number/integer field — renders a number input.
 * Respects minimum, maximum, and step from JSON Schema.
 */
export function NumberField({
  schema,
  name,
  value,
  onChange,
  required = false,
  description,
  error,
  label,
}: FieldProps) {
  const displayLabel = label ?? name.split(".").pop() ?? name;
  const minimum = typeof schema.minimum === "number" ? schema.minimum : undefined;
  const maximum = typeof schema.maximum === "number" ? schema.maximum : undefined;
  const exclusiveMinimum =
    typeof schema.exclusiveMinimum === "number" ? schema.exclusiveMinimum : undefined;
  const exclusiveMaximum =
    typeof schema.exclusiveMaximum === "number" ? schema.exclusiveMaximum : undefined;
  const multipleOf =
    typeof schema.multipleOf === "number" ? schema.multipleOf : undefined;
  const isInteger = schema.type === "integer";

  const describedBy = [
    description ? `${name}-desc` : null,
    error ? `${name}-error` : null,
  ]
    .filter(Boolean)
    .join(" ") || undefined;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    if (raw === "" || raw === "-") {
      onChange(raw === "-" ? raw : undefined);
      return;
    }
    const num = isInteger ? parseInt(raw, 10) : parseFloat(raw);
    if (!Number.isNaN(num)) {
      onChange(num);
    }
  };

  return (
    <div className="space-y-1.5">
      <Label htmlFor={name}>
        {displayLabel}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {description && (
        <p id={`${name}-desc`} className="text-xs text-muted-foreground">
          {description}
        </p>
      )}
      <Input
        id={name}
        name={name}
        type="number"
        value={value != null ? String(value) : ""}
        onChange={handleChange}
        min={exclusiveMinimum !== undefined ? exclusiveMinimum + 1 : minimum}
        max={exclusiveMaximum !== undefined ? exclusiveMaximum - 1 : maximum}
        step={multipleOf ?? (isInteger ? 1 : "any")}
        required={required}
        aria-describedby={describedBy}
        aria-invalid={!!error}
        placeholder={schema.default != null ? String(schema.default) : undefined}
      />
      {error && (
        <p id={`${name}-error`} className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
