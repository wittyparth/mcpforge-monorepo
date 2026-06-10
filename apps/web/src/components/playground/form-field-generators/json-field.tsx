"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import type { FieldProps } from "./types";

/**
 * JSON field — fallback for complex or unknown types.
 * Renders a textarea with JSON validation.
 */
export function JsonField({
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
  const [localError, setLocalError] = useState<string | null>(null);

  const describedBy = [
    description ? `${name}-desc` : null,
    error || localError ? `${name}-error` : null,
  ]
    .filter(Boolean)
    .join(" ") || undefined;

  const displayValue =
    typeof value === "string"
      ? value
      : value != null
        ? JSON.stringify(value, null, 2)
        : "";

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const raw = e.target.value;
    // Allow empty field unless required
    if (raw.trim() === "") {
      if (required) {
        setLocalError("Value is required");
        onChange(undefined);
      } else {
        setLocalError(null);
        onChange(undefined);
      }
      return;
    }

    try {
      const parsed = JSON.parse(raw) as unknown;
      setLocalError(null);
      onChange(parsed);
    } catch {
      setLocalError("Invalid JSON");
      // Store raw string so user can keep editing
      onChange(raw);
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
      <textarea
        id={name}
        name={name}
        value={displayValue}
        onChange={handleChange}
        required={required}
        aria-describedby={describedBy}
        aria-invalid={!!(error || localError)}
        spellCheck={false}
        className="flex min-h-[120px] w-full rounded-md border border-input bg-transparent px-3 py-2 font-mono text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        placeholder={
          schema.default != null
            ? JSON.stringify(schema.default, null, 2)
            : '{ "key": "value" }'
        }
      />
      {(error || localError) && (
        <p id={`${name}-error`} className="text-xs text-destructive" role="alert">
          {error ?? localError}
        </p>
      )}
    </div>
  );
}
