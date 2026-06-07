"use client";

import * as React from "react";
import { Wrench } from "lucide-react";

import {
  Card,
  CardHeader,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { EmptyState } from "@/components/shared/empty-state";
import { ToolSummary } from "./tool-summary";
import { ToolTagGroup } from "./tool-tag-group";
import { LargeSpecWarning } from "./large-spec-warning";
import type { ToolDefinition } from "@/types/api";

export interface ToolWorkspaceProps {
  /** Full list of tool definitions from the spec. */
  tools: ToolDefinition[];
  /** Set of currently selected tool names. */
  selected: Set<string>;
  /** Toggle a single tool by name. */
  onToggle: (name: string) => void;
  /** Select all tools with the given names. */
  onSelectAll: (names: string[]) => void;
  /** Deselect all tools with the given names. */
  onDeselectAll: (names: string[]) => void;
  /** Called when the user clicks the "Continue" button. */
  onConfirm?: () => void;
  /** Disables the "Continue" button. */
  onConfirmDisabled?: boolean;
}

/**
 * Group tools by their first tag. Tools without tags fall into "Untagged".
 */
function groupToolsByTag(
  tools: ToolDefinition[],
): [string, ToolDefinition[]][] {
  const map = new Map<string, ToolDefinition[]>();
  for (const tool of tools) {
    const tag = tool.tags[0] ?? "Untagged";
    const existing = map.get(tag);
    if (existing) {
      existing.push(tool);
    } else {
      map.set(tag, [tool]);
    }
  }
  return Array.from(map.entries());
}

const ToolWorkspace = React.forwardRef<HTMLDivElement, ToolWorkspaceProps>(
  (
    {
      tools,
      selected,
      onToggle,
      onSelectAll,
      onDeselectAll,
      onConfirm,
      onConfirmDisabled,
    },
    ref,
  ) => {
    const [searchQuery, setSearchQuery] = React.useState("");
    const [showLargeSpecWarning, setShowLargeSpecWarning] =
      React.useState(false);

    const allToolNames = React.useMemo(
      () => tools.map((t) => t.name),
      [tools],
    );

    const filteredTools = React.useMemo(() => {
      if (!searchQuery.trim()) return tools;
      const q = searchQuery.toLowerCase();
      return tools.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.path.toLowerCase().includes(q) ||
          t.summary?.toLowerCase().includes(q) ||
          t.tags.some((tag) => tag.toLowerCase().includes(q)),
      );
    }, [tools, searchQuery]);

    const selectedInView = React.useMemo(
      () => filteredTools.filter((t) => selected.has(t.name)).length,
      [filteredTools, selected],
    );

    const groupedTools = React.useMemo(
      () => groupToolsByTag(filteredTools),
      [filteredTools],
    );

    // Show large spec warning on mount if the spec has >200 endpoints
    React.useEffect(() => {
      if (tools.length > 200) {
        setShowLargeSpecWarning(true);
      }
    }, [tools.length]);

    // ── Empty state ──
    if (tools.length === 0) {
      return (
        <Card ref={ref}>
          <CardContent className="pt-6">
            <EmptyState
              icon={Wrench}
              title="No tools found"
              description="This spec doesn't define any operations."
            />
          </CardContent>
        </Card>
      );
    }

    return (
      <>
        <LargeSpecWarning
          endpointCount={tools.length}
          open={showLargeSpecWarning}
          onOpenChange={setShowLargeSpecWarning}
          onConfirm={() => {
            onSelectAll(allToolNames);
            setShowLargeSpecWarning(false);
          }}
        />

        <Card ref={ref}>
          {/* ── Header ── */}
          <CardHeader className="pb-3">
            <ToolSummary
              total={filteredTools.length}
              selected={selectedInView}
              excluded={filteredTools.length - selectedInView}
              searchQuery={searchQuery}
              onSearch={setSearchQuery}
            />
          </CardHeader>

          {/* ── Scrollable tool groups ── */}
          <CardContent>
            <ScrollArea className="h-[500px] pr-4">
              <div className="space-y-3">
                {groupedTools.map(([tag, tagTools]) => (
                  <ToolTagGroup
                    key={tag}
                    tag={tag}
                    tools={tagTools}
                    selected={selected}
                    onToggle={onToggle}
                    onSelectAll={onSelectAll}
                    onDeselectAll={onDeselectAll}
                  />
                ))}
              </div>
            </ScrollArea>
          </CardContent>

          {/* ── Footer actions ── */}
          <CardFooter className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onSelectAll(allToolNames)}
              >
                Select All
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onDeselectAll(allToolNames)}
              >
                Deselect All
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={onConfirm} disabled={onConfirmDisabled}>
                Continue
              </Button>
            </div>
          </CardFooter>
        </Card>
      </>
    );
  },
);
ToolWorkspace.displayName = "ToolWorkspace";

export { ToolWorkspace };
