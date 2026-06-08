"use client";

import * as React from "react";
import { ChevronDown, Check } from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ToolRow } from "./tool-row";
import type { ToolDefinition } from "@/types/api";

export interface ToolTagGroupProps {
  /** Tag name for this group. */
  tag: string;
  /** Tools belonging to this tag. */
  tools: ToolDefinition[];
  /** Currently selected tool names across the workspace. */
  selected: Set<string>;
  /** Toggle a single tool by name. */
  onToggle: (name: string) => void;
  /** Select all tools in this group (called with their names). */
  onSelectAll: (names: string[]) => void;
  /** Deselect all tools in this group (called with their names). */
  onDeselectAll: (names: string[]) => void;
  /** Whether the group starts expanded. @default true */
  defaultOpen?: boolean;
}

const ToolTagGroup = React.forwardRef<HTMLDivElement, ToolTagGroupProps>(
  (
    {
      tag,
      tools,
      selected,
      onToggle,
      onSelectAll,
      onDeselectAll,
      defaultOpen = true,
    },
    ref,
  ) => {
    const [isOpen, setIsOpen] = React.useState(defaultOpen);

    const groupToolNames = React.useMemo(() => tools.map((t) => t.name), [tools]);
    const selectedCount = tools.filter((t) => selected.has(t.name)).length;
    const allSelected = selectedCount === tools.length;
    const noneSelected = selectedCount === 0;

    if (tools.length === 0) return null;

    return (
      <div ref={ref} className="rounded-lg border bg-card">
        {/* ── Collapsible Header ── */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => setIsOpen(!isOpen)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setIsOpen(!isOpen); } }}
          className={cn(
            "flex w-full items-center justify-between px-4 py-3",
            "text-sm font-medium",
            "hover:bg-muted/50 transition-colors duration-150",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
            "rounded-t-lg",
            !isOpen && "rounded-b-lg",
            "cursor-pointer",
          )}
          aria-expanded={isOpen}
        >
          <div className="flex items-center gap-2">
            <ChevronDown
              className={cn(
                "h-4 w-4 text-muted-foreground transition-transform duration-200",
                !isOpen && "-rotate-90",
              )}
              aria-hidden="true"
            />
            <span className="font-semibold">{tag}</span>
            <Badge
              variant="secondary"
              className="ml-1 text-[10px] font-normal leading-none"
            >
              {tools.length} tool{tools.length !== 1 ? "s" : ""}
            </Badge>
          </div>

          <div className="flex items-center gap-3">
            {/* Selection status text */}
            <span className="text-xs text-muted-foreground">
              {allSelected && (
                <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                  <Check className="h-3 w-3" />
                  All selected
                </span>
              )}
              {noneSelected && "None selected"}
              {!allSelected && !noneSelected && (
                <span>
                  <span className="font-medium text-foreground">
                    {selectedCount}
                  </span>{" "}
                  of {tools.length} selected
                </span>
              )}
            </span>

            {/* Quick select/deselect all toggle */}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (allSelected) {
                  onDeselectAll(groupToolNames);
                } else {
                  onSelectAll(groupToolNames);
                }
              }}
              className={cn(
                "rounded px-1 py-0.5 text-xs font-medium",
                "text-muted-foreground hover:text-foreground",
                "transition-colors duration-150",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              {allSelected ? "Deselect all" : "Select all"}
            </button>
          </div>
        </div>

        {/* ── Collapsible Body ── */}
        <div
          className={cn(
            "overflow-hidden transition-all duration-300 ease-in-out",
            isOpen ? "max-h-[2000px]" : "max-h-0",
          )}
        >
          <div className="px-2 pb-2">
            {tools.map((tool, index) => (
              <React.Fragment key={tool.name}>
                {index > 0 && <Separator className="my-1" />}
                <ToolRow
                  tool={tool}
                  selected={selected.has(tool.name)}
                  onToggle={() => onToggle(tool.name)}
                />
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    );
  },
);
ToolTagGroup.displayName = "ToolTagGroup";

export { ToolTagGroup };
