"use client";

import * as React from "react";
import { Search, Wrench, AlertCircle } from "lucide-react";

import type { ToolDefinition } from "@/types/api";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export interface ToolBrowserProps {
  /** List of available tools */
  tools: ToolDefinition[];
  /** Currently selected tool */
  selectedTool: ToolDefinition | null;
  /** Called when a tool is selected */
  onSelectTool: (tool: ToolDefinition) => void;
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Error message if connection failed */
  error: string | null;
}

/**
 * Left panel: browsable list of available MCP tools.
 *
 * Features search filtering, tool metadata display (method badge, path),
 * and keyboard navigation. Highlights the currently selected tool.
 */
function ToolBrowser({
  tools,
  selectedTool,
  onSelectTool,
  isConnected,
  error,
}: ToolBrowserProps) {
  const [search, setSearch] = React.useState("");

  const filteredTools = React.useMemo(() => {
    if (!search.trim()) return tools;
    const q = search.toLowerCase();
    return tools.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q),
    );
  }, [tools, search]);

  const methodColors: Record<string, string> = {
    GET: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
    POST: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
    PUT: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
    PATCH: "bg-orange-500/15 text-orange-600 dark:text-orange-400",
    DELETE: "bg-red-500/15 text-red-600 dark:text-red-400",
  };

  return (
    <Card className="flex h-full flex-col overflow-hidden border-0 rounded-none border-r border-border/50">
      <CardHeader className="space-y-3 p-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold">Tools</CardTitle>
          <Badge variant="secondary" className="text-xs tabular-nums">
            {tools.length}
          </Badge>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search tools…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 pl-8 text-xs"
            aria-label="Search tools"
          />
        </div>

        {/* Connection status */}
        {!isConnected && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <AlertCircle className="h-3 w-3" />
            <span>Disconnected</span>
          </div>
        )}
      </CardHeader>

      {/* Error banner */}
      {error && (
        <div className="mx-3 mb-2 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      {/* Tool list */}
      <ScrollArea className="flex-1">
        <div className="space-y-0.5 px-1.5 pb-3" role="listbox" aria-label="Available tools">
          {filteredTools.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-8 text-center text-xs text-muted-foreground">
              <Wrench className="h-5 w-5" />
              <span>
                {tools.length === 0
                  ? "No tools available"
                  : "No tools match your search"}
              </span>
            </div>
          )}

          {filteredTools.map((tool) => {
            const isSelected = selectedTool?.name === tool.name;
            const method = (tool.method ?? "GET").toUpperCase();
            const methodColor = methodColors[method] ?? methodColors.GET;

            return (
              <TooltipProvider key={tool.name} delayDuration={300}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => onSelectTool(tool)}
                      className={cn(
                        "flex w-full flex-col gap-1 rounded-md px-2.5 py-2 text-left text-xs transition-colors",
                        "hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                        isSelected && "bg-accent text-accent-foreground",
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            "inline-flex shrink-0 items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase leading-none",
                            methodColor,
                          )}
                        >
                          {method}
                        </span>
                        <span className="truncate font-medium">{tool.name}</span>
                      </div>
                      {tool.path && (
                        <span className="truncate pl-0.5 font-mono text-[10px] text-muted-foreground">
                          {tool.path}
                        </span>
                      )}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-64">
                    <p className="text-xs">{tool.description || "No description"}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            );
          })}
        </div>
      </ScrollArea>
    </Card>
  );
}

export { ToolBrowser };
