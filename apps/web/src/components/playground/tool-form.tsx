"use client";

import * as React from "react";
import { Play, Loader2, RotateCcw } from "lucide-react";

import type { ToolDefinition } from "@/types/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export interface ToolFormProps {
  /** The selected tool definition */
  tool: ToolDefinition | null;
  /** Whether a tool call is in progress */
  isCalling: boolean;
  /** Called when the user clicks "Call Tool" */
  onCallTool: (toolName: string, args: Record<string, unknown>) => void;
  /** Called to clear the current form values */
  onClear: () => void;
}

interface FieldDef {
  key: string;
  label: string;
  type: "string" | "number" | "boolean" | "object" | "array";
  required: boolean;
  description: string;
  defaultValue: string;
  enumValues?: string[];
}

/**
 * Extract form fields from a tool's input_schema (JSON Schema).
 */
function extractFields(
  schema: Record<string, unknown> | null | undefined,
): FieldDef[] {
  if (!schema || typeof schema !== "object") return [];

  const properties = schema.properties as Record<string, unknown> | undefined;
  const required = Array.isArray(schema.required)
    ? (schema.required as string[])
    : [];

  if (!properties) return [];

  return Object.entries(properties).map(([key, prop]) => {
    const p = prop as Record<string, unknown>;
    const type = inferType(p);
    const defaultValue = getDefaultValue(p, type);

    return {
      key,
      label: formatLabel(key),
      type,
      required: required.includes(key),
      description: (p.description as string) ?? "",
      defaultValue,
      enumValues: Array.isArray(p.enum)
        ? (p.enum as string[]).map(String)
        : undefined,
    };
  });
}

function inferType(
  prop: Record<string, unknown>,
): "string" | "number" | "boolean" | "object" | "array" {
  const t = prop.type;
  if (t === "integer" || t === "number") return "number";
  if (t === "boolean") return "boolean";
  if (t === "object") return "object";
  if (t === "array") return "array";
  return "string";
}

function getDefaultValue(
  prop: Record<string, unknown>,
  type: string,
): string {
  if (prop.default !== undefined) {
    return typeof prop.default === "string"
      ? prop.default
      : JSON.stringify(prop.default);
  }
  if (type === "boolean") return "false";
  if (type === "number") return "";
  if (type === "object" || type === "array") return "";
  return "";
}

function formatLabel(key: string): string {
  return key
    .replace(/[_-]/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Center-top panel: auto-generated form from the selected tool's inputSchema.
 *
 * Renders typed form fields with validation. Supports string, number, boolean,
 * object, and array types. Includes "Call Tool" button with loading state.
 */
function ToolForm({ tool, isCalling, onCallTool, onClear: _onClear }: ToolFormProps) {
  const fields = React.useMemo(
    () => extractFields(tool?.input_schema),
    [tool?.input_schema],
  );

  const [values, setValues] = React.useState<Record<string, string>>({});

  // Reset form when tool changes
  React.useEffect(() => {
    const initial: Record<string, string> = {};
    for (const field of fields) {
      initial[field.key] = field.defaultValue;
    }
    setValues(initial);
  }, [fields]);

  const updateValue = React.useCallback((key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSubmit = React.useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      console.log("[DBG] handleSubmit called", { toolName: tool?.name, isCalling });
      if (!tool) {
        console.log("[DBG] handleSubmit: tool is null, returning");
        return;
      }

      const args: Record<string, unknown> = {};
      for (const field of fields) {
        const raw = values[field.key] ?? "";
        if (raw === "") continue; // skip empty optional fields

        switch (field.type) {
          case "number":
            args[field.key] = Number(raw);
            break;
          case "boolean":
            args[field.key] = raw === "true";
            break;
          case "object":
          case "array":
            try {
              args[field.key] = JSON.parse(raw);
            } catch {
              args[field.key] = raw;
            }
            break;
          default:
            args[field.key] = raw;
        }
      }

      console.log("[DBG] handleSubmit calling onCallTool", { toolName: tool.name, args });
      onCallTool(tool.name, args);
    },
    [tool, fields, values, onCallTool, isCalling],
  );

  const handleReset = React.useCallback(() => {
    const initial: Record<string, string> = {};
    for (const field of fields) {
      initial[field.key] = field.defaultValue;
    }
    setValues(initial);
  }, [fields]);

  if (!tool) {
    return (
      <Card className="flex h-full items-center justify-center border-0 rounded-none border-b border-border/50">
        <div className="flex flex-col items-center gap-2 text-center text-sm text-muted-foreground">
          <Play className="h-5 w-5" />
          <span>Select a tool to configure and call it</span>
        </div>
      </Card>
    );
  }

  return (
    <Card className="flex h-full flex-col overflow-hidden border-0 rounded-none border-b border-border/50">
      <CardHeader className="p-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Play className="h-3.5 w-3.5" />
            {tool.name}
          </CardTitle>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={handleReset}
                  aria-label="Reset form values"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Reset form</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        {tool.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {tool.description}
          </p>
        )}
      </CardHeader>

      <Separator />

      <form onSubmit={handleSubmit} className="flex flex-1 flex-col overflow-hidden">
        <CardContent className="flex-1 space-y-3 overflow-y-auto p-3">
          {fields.length === 0 && (
            <p className="py-4 text-center text-xs text-muted-foreground">
              No input parameters required
            </p>
          )}

          {fields.map((field) => (
            <div key={field.key} className="space-y-1.5">
              <Label
                htmlFor={`tool-field-${field.key}`}
                className="flex items-center gap-1.5 text-xs"
              >
                {field.label}
                {field.required && (
                  <span className="text-destructive">*</span>
                )}
                <span className="font-normal text-muted-foreground">
                  ({field.type})
                </span>
              </Label>

              {field.description && (
                <p className="text-[11px] text-muted-foreground">
                  {field.description}
                </p>
              )}

              {field.enumValues ? (
                <select
                  id={`tool-field-${field.key}`}
                  value={values[field.key] ?? ""}
                  onChange={(e) => updateValue(field.key, e.target.value)}
                  className={cn(
                    "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors",
                    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                  )}
                  aria-required={field.required}
                >
                  <option value="">Select…</option>
                  {field.enumValues.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              ) : field.type === "boolean" ? (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={values[field.key] === "true"}
                    onClick={() =>
                      updateValue(
                        field.key,
                        values[field.key] === "true" ? "false" : "true",
                      )
                    }
                    className={cn(
                      "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent shadow-sm transition-colors",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                      values[field.key] === "true"
                        ? "bg-primary"
                        : "bg-input",
                    )}
                  >
                    <span
                      className={cn(
                        "pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform",
                        values[field.key] === "true"
                          ? "translate-x-4"
                          : "translate-x-0",
                      )}
                    />
                  </button>
                  <span className="text-xs text-muted-foreground">
                    {values[field.key] === "true" ? "true" : "false"}
                  </span>
                </div>
              ) : field.type === "object" || field.type === "array" ? (
                <Input
                  id={`tool-field-${field.key}`}
                  type="text"
                  placeholder={`JSON ${field.type}`}
                  value={values[field.key] ?? ""}
                  onChange={(e) => updateValue(field.key, e.target.value)}
                  className="font-mono text-xs"
                  aria-required={field.required}
                />
              ) : (
                <Input
                  id={`tool-field-${field.key}`}
                  type={field.type === "number" ? "number" : "text"}
                  placeholder={field.type === "number" ? "0" : `Enter ${field.label.toLowerCase()}…`}
                  value={values[field.key] ?? ""}
                  onChange={(e) => updateValue(field.key, e.target.value)}
                  className="text-xs"
                  aria-required={field.required}
                />
              )}
            </div>
          ))}
        </CardContent>

        <div className="border-t border-border/50 p-3">
          <Button
            type="submit"
            className="w-full"
            size="sm"
            disabled={isCalling}
            aria-label={isCalling ? "Calling tool…" : `Call ${tool.name}`}
          >
            {isCalling ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Calling…
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                Call Tool
              </>
            )}
          </Button>
        </div>
      </form>
    </Card>
  );
}

export { ToolForm };
