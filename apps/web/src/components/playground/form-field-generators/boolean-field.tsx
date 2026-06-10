"use client";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { FieldProps } from "./types";

/**
 * Boolean field — renders a switch toggle.
 */
export function BooleanField({
  schema: _schema,
  name,
  value,
  onChange,
  required = false,
  description,
  error,
  label,
}: FieldProps) {
  const displayLabel = label ?? name.split(".").pop() ?? name;
  const checked = typeof value === "boolean" ? value : false;

  const describedBy = [
    description ? `${name}-desc` : null,
    error ? `${name}-error` : null,
  ]
    .filter(Boolean)
    .join(" ") || undefined;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <Switch
          id={name}
          checked={checked}
          onCheckedChange={(checked) => onChange(checked)}
          aria-describedby={describedBy}
          aria-invalid={!!error}
        />
        <Label htmlFor={name} className="cursor-pointer">
          {displayLabel}
          {required && <span className="ml-0.5 text-destructive">*</span>}
        </Label>
      </div>
      {description && (
        <p id={`${name}-desc`} className="text-xs text-muted-foreground">
          {description}
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
