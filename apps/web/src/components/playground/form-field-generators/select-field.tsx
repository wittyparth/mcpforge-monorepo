"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { FieldProps } from "./types";

/**
 * Select field — renders a dropdown for enum values.
 */
export function SelectField({
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
  const options = Array.isArray(schema.enum) ? schema.enum : [];

  const describedBy = [
    description ? `${name}-desc` : null,
    error ? `${name}-error` : null,
  ]
    .filter(Boolean)
    .join(" ") || undefined;

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
      <Select
        value={value != null ? String(value) : ""}
        onValueChange={(v) => onChange(v)}
      >
        <SelectTrigger
          id={name}
          aria-describedby={describedBy}
          aria-invalid={!!error}
        >
          <SelectValue
            placeholder={
              schema.default != null ? String(schema.default) : "Select..."
            }
          />
        </SelectTrigger>
        <SelectContent>
          {options.map((opt) => {
            const strVal = String(opt);
            return (
              <SelectItem key={strVal} value={strVal}>
                {strVal}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
      {error && (
        <p id={`${name}-error`} className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
