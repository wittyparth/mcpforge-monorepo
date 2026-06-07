"use client";

import * as React from "react";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";
import { HttpMethodBadge } from "@/components/shared/http-method-badge";
import { ToolWarnings } from "./tool-warnings";
import type { ToolDefinition } from "@/types/api";

export interface ToolRowProps {
  /** The tool definition to display. */
  tool: ToolDefinition;
  /** Whether this tool is currently selected. */
  selected: boolean;
  /** Called when the user clicks the row to toggle selection. */
  onToggle: () => void;
}

const ToolRow = React.forwardRef<HTMLDivElement, ToolRowProps>(
  ({ tool, selected, onToggle }, ref) => {
    return (
      <div
        ref={ref}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
        role="checkbox"
        aria-checked={selected}
        tabIndex={0}
        className={cn(
          "group flex cursor-pointer items-center gap-3 rounded-md px-3 py-2.5",
          "border-l-2 ml-3 pl-4",
          "transition-all duration-200",
          selected
            ? "border-l-primary bg-primary/5"
            : "border-l-muted hover:border-l-muted-foreground/30",
          "hover:bg-muted/50",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        )}
      >
        {/* ── Custom Checkbox ── */}
        <div
          className={cn(
            "flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-colors duration-200",
            selected
              ? "border-primary bg-primary text-primary-foreground"
              : "border-input bg-background group-hover:border-muted-foreground/50",
          )}
          aria-hidden="true"
        >
          {selected && <Check className="h-3 w-3" strokeWidth={3} />}
        </div>

        {/* ── HTTP Method Badge ── */}
        <HttpMethodBadge method={tool.method} />

        {/* ── Tool Info ── */}
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate font-mono text-sm font-semibold">
            {tool.name}
          </span>
          <span className="truncate font-mono text-xs text-muted-foreground/70">
            {tool.path}
          </span>
          {tool.summary && (
            <span className="line-clamp-2 text-xs text-muted-foreground">
              {tool.summary}
            </span>
          )}
        </div>

        {/* ── Warnings ── */}
        {tool.warnings.length > 0 && (
          <div
            onClick={(e) => {
              // Prevent row toggle when interacting with the warnings popover
              e.stopPropagation();
            }}
            className="shrink-0"
          >
            <ToolWarnings warnings={tool.warnings} size="sm" />
          </div>
        )}
      </div>
    );
  },
);
ToolRow.displayName = "ToolRow";

export { ToolRow };
