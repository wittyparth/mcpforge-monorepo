"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { FieldProps } from "./types";

/**
 * String field — renders a text input.
 * Falls back to textarea when maxLength > 100 or when explicitly marked.
 */
export function StringField({
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
  const maxLength = typeof schema.maxLength === "number" ? schema.maxLength : undefined;
  const minLength = typeof schema.minLength === "number" ? schema.minLength : undefined;
  const pattern = typeof schema.pattern === "string" ? schema.pattern : undefined;
  const useTextarea = (maxLength !== undefined && maxLength > 100) || (schema as Record<string, unknown>).format === "textarea";

  const describedBy = [
    description ? `${name}-desc` : null,
    error ? `${name}-error` : null,
  ]
    .filter(Boolean)
    .join(" ") || undefined;

  if (useTextarea) {
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
        <textarea
          id={name}
          name={name}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
          maxLength={maxLength}
          minLength={minLength}
          required={required}
          aria-describedby={describedBy}
          aria-invalid={!!error}
          className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
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
        type="text"
        value={typeof value === "string" ? value : ""}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        minLength={minLength}
        pattern={pattern}
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
