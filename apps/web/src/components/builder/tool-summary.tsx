"use client";

import * as React from "react";
import { Search, AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

export interface ToolSummaryProps {
  /** Total number of endpoints (visible after filtering). */
  total: number;
  /** Number of currently selected endpoints. */
  selected: number;
  /** Number of currently excluded endpoints. */
  excluded: number;
  /** Called with the search query string (debounced ~200ms). */
  onSearch?: (query: string) => void;
  /** Current search query value for controlled sync. */
  searchQuery?: string;
}

const ToolSummary = React.forwardRef<HTMLDivElement, ToolSummaryProps>(
  ({ total, selected, excluded, onSearch, searchQuery = "" }, ref) => {
    const [localQuery, setLocalQuery] = React.useState(searchQuery);
    const debounceRef = React.useRef<ReturnType<typeof setTimeout>>(
      undefined! as unknown as ReturnType<typeof setTimeout>,
    );

    // Sync external searchQuery prop changes
    React.useEffect(() => {
      setLocalQuery(searchQuery);
    }, [searchQuery]);

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setLocalQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        onSearch?.(value);
      }, 200);
    };

    // Cleanup debounce on unmount
    React.useEffect(() => {
      return () => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
      };
    }, []);

    return (
      <div ref={ref} className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Title + Counts */}
          <div className="flex items-center gap-3">
            <div>
              <h3 className="text-base font-semibold">Tool Workspace</h3>
              <p className="text-sm text-muted-foreground">
                {total} endpoint{total !== 1 ? "s" : ""} found
              </p>
            </div>

            {/* Status pills */}
            <div className="flex items-center gap-1.5">
              <Badge
                variant="default"
                className={cn(
                  "gap-1.5 pl-2 text-xs font-medium transition-all duration-200",
                  selected === 0 && "opacity-50",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    selected > 0 ? "bg-green-500" : "bg-muted-foreground/40",
                  )}
                  aria-hidden="true"
                />
                {selected} selected
              </Badge>

              <Badge
                variant="secondary"
                className={cn(
                  "gap-1.5 pl-2 text-xs font-medium transition-all duration-200",
                  excluded === 0 && "opacity-50",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    excluded > 0 ? "bg-muted-foreground/60" : "bg-muted-foreground/30",
                  )}
                  aria-hidden="true"
                />
                {excluded} excluded
              </Badge>
            </div>
          </div>

          {/* Search input */}
          {onSearch && (
            <div className="relative w-full sm:w-52">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Filter tools\u2026"
                value={localQuery}
                onChange={handleSearchChange}
                className="h-8 pl-8 text-sm"
                aria-label="Filter tools by name, path, or tag"
              />
            </div>
          )}
        </div>

        {/* Zero-selected warning */}
        {selected === 0 && total > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            <span>Select at least 1 tool to continue</span>
          </div>
        )}
      </div>
    );
  },
);
ToolSummary.displayName = "ToolSummary";

export { ToolSummary };
