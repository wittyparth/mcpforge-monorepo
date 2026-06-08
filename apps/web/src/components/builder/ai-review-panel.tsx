"use client";

import * as React from "react";
import {
  Sparkles,
  DollarSign,
  RotateCcw,
  CheckCheck,
  Filter,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { AiReviewToolCard } from "./ai-review-tool-card";
import { AiCostDisplay } from "./ai-cost-display";
import { AiCreditsIndicator } from "./ai-credits-indicator";
import { QualityScoreBadge } from "./quality-score-badge";
import type { AIEnhancedTool } from "@/types/api";

export interface AiReviewPanelProps {
  /** The server ID being reviewed. */
  serverId: string;
  /** List of AI-enhanced tools to review. */
  tools: AIEnhancedTool[];
  /** Called when the user clicks "Re-run AI Enhancement". */
  onEnhanceAll: () => void;
  /** Called when the user clicks "Accept All". */
  onAcceptAll: () => void;
  /** Whether enhancement is currently in progress. */
  isEnhancing?: boolean;
  /** User's remaining credits (null = unlimited). */
  creditsRemaining?: number | null;
  /** User's plan name. */
  plan?: string;
}

type FilterMode = "all" | "accepted" | "rejected" | "pending";

/**
 * Main container panel for reviewing AI-enhanced tool descriptions.
 *
 * Renders a list of `AiReviewToolCard` components with summary stats,
 * filter controls, and bulk actions (Accept All, Re-run AI).
 *
 * State is managed locally for accept/reject decisions. The parent
 * component receives bulk actions via callbacks.
 */
const AiReviewPanel = React.forwardRef<HTMLDivElement, AiReviewPanelProps>(
  (
    {
      serverId: _serverId,
      tools,
      onEnhanceAll,
      onAcceptAll,
      isEnhancing = false,
      creditsRemaining = null,
      plan = "free",
    },
    ref,
  ) => {
    const [filter, setFilter] = React.useState<FilterMode>("all");
    const [decisions, setDecisions] = React.useState<
      Map<string, "accepted" | "rejected" | "pending">
    >(() => new Map(tools.map((t) => [t.name, "pending"])));

    // Sync decisions when tools list changes
    React.useEffect(() => {
      setDecisions((prev) => {
        const next = new Map(prev);
        for (const tool of tools) {
          if (!next.has(tool.name)) {
            next.set(tool.name, "pending");
          }
        }
        return next;
      });
    }, [tools]);

    const handleAccept = React.useCallback((toolName: string) => {
      setDecisions((prev) => {
        const next = new Map(prev);
        next.set(toolName, "accepted");
        return next;
      });
    }, []);

    const handleReject = React.useCallback((toolName: string) => {
      setDecisions((prev) => {
        const next = new Map(prev);
        next.set(toolName, "rejected");
        return next;
      });
    }, []);

    const handleEdit = React.useCallback((_toolName: string, _field: string, _value: string) => {
      // Edits are tracked locally within AiReviewToolCard
      // This callback exists for parent-level persistence if needed
    }, []);

    // ── Derived stats ──
    const stats = React.useMemo(() => {
      const total = tools.length;
      const accepted = Array.from(decisions.values()).filter((d) => d === "accepted").length;
      const rejected = Array.from(decisions.values()).filter((d) => d === "rejected").length;
      const pending = total - accepted - rejected;
      const totalCost = tools.reduce((sum, t) => sum + t.cost_cents, 0);
      const avgScore =
        total > 0
          ? Math.round(
              tools.reduce((sum, t) => sum + t.quality_score.total, 0) / total,
            )
          : 0;
      return { total, accepted, rejected, pending, totalCost, avgScore };
    }, [tools, decisions]);

    // ── Filtered tools ──
    const filteredTools = React.useMemo(() => {
      if (filter === "all") return tools;
      return tools.filter((t) => decisions.get(t.name) === filter);
    }, [tools, filter, decisions]);

    // ── Empty state ──
    if (tools.length === 0 && !isEnhancing) {
      return (
        <Card ref={ref}>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Sparkles className="h-12 w-12 text-muted-foreground/30" />
            <h3 className="mt-4 text-lg font-medium">No AI enhancements yet</h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Run the AI Description Engine to enhance your tool descriptions
              for better LLM selection probability.
            </p>
            <Button onClick={onEnhanceAll} className="mt-6 gap-2">
              <Sparkles className="h-4 w-4" />
              Run AI Enhancement
            </Button>
          </CardContent>
        </Card>
      );
    }

    return (
      <div ref={ref} className="space-y-4">
        {/* ── Summary stats ── */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Sparkles className="h-5 w-5 text-primary" />
                  AI Review
                </CardTitle>
                <CardDescription>
                  Review and accept AI-enhanced tool descriptions
                </CardDescription>
              </div>

              <div className="flex items-center gap-2">
                <AiCreditsIndicator
                  remaining={creditsRemaining}
                  plan={plan}
                  size="sm"
                />
              </div>
            </div>
          </CardHeader>

          <CardContent>
            {/* ── Stats grid ── */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg border bg-muted/30 p-3 text-center">
                <p className="text-2xl font-semibold tabular-nums">{stats.total}</p>
                <p className="text-[11px] text-muted-foreground">Total Tools</p>
              </div>
              <div className="rounded-lg border bg-emerald-500/5 p-3 text-center">
                <p className="text-2xl font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                  {stats.accepted}
                </p>
                <p className="text-[11px] text-muted-foreground">Accepted</p>
              </div>
              <div className="rounded-lg border bg-red-500/5 p-3 text-center">
                <p className="text-2xl font-semibold tabular-nums text-red-600 dark:text-red-400">
                  {stats.rejected}
                </p>
                <p className="text-[11px] text-muted-foreground">Rejected</p>
              </div>
              <div className="rounded-lg border bg-muted/30 p-3 text-center">
                <p className="text-2xl font-semibold tabular-nums">{stats.pending}</p>
                <p className="text-[11px] text-muted-foreground">Pending</p>
              </div>
            </div>

            {/* ── Cost + score row ── */}
            <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <DollarSign className="h-3.5 w-3.5 opacity-50" />
                <span>Total cost:</span>
                <AiCostDisplay costCents={stats.totalCost} />
              </div>
              <div className="flex items-center gap-1.5">
                <span>Avg score:</span>
                <QualityScoreBadge
                  score={stats.avgScore}
                  badge={
                    stats.avgScore >= 90
                      ? "Excellent"
                      : stats.avgScore >= 70
                        ? "Good"
                        : stats.avgScore >= 50
                          ? "Fair"
                          : "Poor"
                  }
                  size="sm"
                />
              </div>
            </div>

            {/* ── Actions ── */}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                onClick={onAcceptAll}
                disabled={isEnhancing || stats.pending === 0}
                className="gap-1"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Accept All ({stats.pending})
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={onEnhanceAll}
                disabled={isEnhancing}
                className="gap-1"
              >
                {isEnhancing ? (
                  <>
                    <RotateCcw className="h-3.5 w-3.5 animate-spin" />
                    Enhancing...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-3.5 w-3.5" />
                    Re-run AI
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* ── Filter bar ── */}
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-muted-foreground" />
          <div className="flex gap-1">
            {(["all", "pending", "accepted", "rejected"] as const).map((mode) => {
              const count =
                mode === "all"
                  ? stats.total
                  : mode === "pending"
                    ? stats.pending
                    : mode === "accepted"
                      ? stats.accepted
                      : stats.rejected;
              return (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setFilter(mode)}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
                    filter === mode
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
                  )}
                >
                  <span className="capitalize">{mode}</span>
                  <Badge
                    variant="secondary"
                    className="h-4 min-w-[1rem] justify-center px-1 text-[9px]"
                  >
                    {count}
                  </Badge>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Tool cards ── */}
        <ScrollArea className="max-h-[700px]">
          <div className="space-y-3 pr-4">
            {isEnhancing && tools.length === 0 ? (
              // Skeleton loading state
              Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="space-y-2 rounded-xl border p-4">
                  <Skeleton className="h-5 w-48" />
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ))
            ) : filteredTools.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  No tools match the selected filter.
                </p>
              </div>
            ) : (
              filteredTools.map((tool) => (
                <AiReviewToolCard
                  key={tool.name}
                  tool={tool}
                  onAccept={() => handleAccept(tool.name)}
                  onReject={() => handleReject(tool.name)}
                  onEdit={(field, value) => handleEdit(tool.name, field, value)}
                  isPending={isEnhancing}
                />
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    );
  },
);
AiReviewPanel.displayName = "AiReviewPanel";

export { AiReviewPanel };
