"use client";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Plus, X } from "lucide-react";
import { FormField } from "./index";
import type { FieldProps, JSONSchema7 } from "./types";

/**
 * Array field — renders a repeatable list of items.
 * Each item is generated from the schema's `items` definition.
 * Supports nested types via FormField recursion.
 */
export function ArrayField({
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
  const itemsSchema = (schema.items as JSONSchema7) ?? { type: "string" };
  const items = Array.isArray(value) ? value : [];

  const addItem = () => {
    const defaultVal = getDefaultForSchema(itemsSchema);
    onChange([...items, defaultVal]);
  };

  const removeItem = (index: number) => {
    const next = items.filter((_, i) => i !== index);
    onChange(next);
  };

  const updateItem = (index: number, itemValue: unknown) => {
    const next = [...items];
    next[index] = itemValue;
    onChange(next);
  };

  return (
    <div className="space-y-1.5">
      <Label>
        {displayLabel}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {description && (
        <p id={`${name}-desc`} className="text-xs text-muted-foreground">
          {description}
        </p>
      )}

      <div className="space-y-2">
        {items.map((item, index) => {
          const itemName = `${name}[${index}]`;
          return (
            <div
              key={itemName}
              className="flex items-start gap-2"
              style={{ paddingLeft: depth * 16 }}
            >
              <div className="flex-1 min-w-0">
                <FormField
                  schema={itemsSchema}
                  name={itemName}
                  value={item}
                  onChange={(v) => updateItem(index, v)}
                  label={`[${index}]`}
                  depth={depth + 1}
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="mt-7 shrink-0 h-8 w-8"
                onClick={() => removeItem(index)}
                aria-label={`Remove item ${index}`}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          );
        })}
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={addItem}
        className="mt-1"
      >
        <Plus className="h-4 w-4 mr-1" />
        Add item
      </Button>

      {error && (
        <p id={`${name}-error`} className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

// ── Helper ──────────────────────────────────────────────────────

function getDefaultForSchema(schema: JSONSchema7): unknown {
  if (schema.default !== undefined) return schema.default;
  switch (schema.type) {
    case "string":
      return "";
    case "number":
    case "integer":
      return 0;
    case "boolean":
      return false;
    case "array":
      return [];
    case "object":
      return {};
    default:
      return "";
  }
}
