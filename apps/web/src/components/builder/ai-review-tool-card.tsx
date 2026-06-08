"use client";

import * as React from "react";
import { Check, X, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { QualityScoreBadge } from "./quality-score-badge";
import { QualityScoreBreakdown } from "./quality-score-breakdown";
import { ImprovementsBadges } from "./improvements-badges";
import { AiCostDisplay } from "./ai-cost-display";
import { InlineEditField } from "./inline-edit-field";
import { RevertFieldButton } from "./revert-field-button";
import { OriginalVsEnhanced } from "./original-vs-enhanced";
import type { AIEnhancedTool } from "@/types/api";

export interface AiReviewToolCardProps {
  /** The AI-enhanced tool data. */
  tool: AIEnhancedTool;
  /** Called when the user accepts the AI enhancement. */
  onAccept: () => void;
  /** Called when the user rejects the AI enhancement. */
  onReject: () => void;
  /** Called when the user edits a field on the enhanced tool. */
  onEdit: (field: string, value: string) => void;
  /** Whether the card is in a pending/processing state. */
  isPending?: boolean;
}

/**
 * Review card for a single AI-enhanced tool.
 *
 * Displays the quality score badge, improvement badges, side-by-side
 * comparison of original vs. enhanced descriptions, and inline editing
 * capabilities. The user can accept or reject the enhancement.
 *
 * The card has a collapsible detail section to keep the list view clean
 * while allowing deep inspection when needed.
 */
const AiReviewToolCard = React.forwardRef<HTMLDivElement, AiReviewToolCardProps>(
  ({ tool, onAccept, onReject, onEdit, isPending = false }, ref) => {
    const [expanded, setExpanded] = React.useState(false);
    const [editedDesc, setEditedDesc] = React.useState(tool.enhanced_description);
    const [editedName, setEditedName] = React.useState(tool.enhanced_name ?? tool.name);

    // Sync local state when tool prop changes
    React.useEffect(() => {
      setEditedDesc(tool.enhanced_description);
      setEditedName(tool.enhanced_name ?? tool.name);
    }, [tool.enhanced_description, tool.enhanced_name, tool.name]);

    const handleSaveDescription = (val: string) => {
      setEditedDesc(val);
      onEdit("description", val);
    };

    const handleSaveName = (val: string) => {
      setEditedName(val);
      onEdit("name", val);
    };

    const handleRevertDescription = () => {
      setEditedDesc(tool.original_description);
      onEdit("description", tool.original_description);
    };

    const handleRevertName = () => {
      setEditedName(tool.name);
      onEdit("name", tool.name);
    };

    const isDirty =
      editedDesc !== tool.enhanced_description ||
      editedName !== (tool.enhanced_name ?? tool.name);

    return (
      <div
        ref={ref}
        className={cn(
          "rounded-xl border bg-card text-card-foreground shadow transition-all",
          isPending && "opacity-60",
        )}
      >
        {/* ── Header ── */}
        <div className="flex items-center gap-3 px-4 py-3">
          <Sparkles className="h-4 w-4 shrink-0 text-primary" />

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-mono text-sm font-semibold">
                {tool.name}
              </span>
              {tool.enhanced_name && tool.enhanced_name !== tool.name && (
                <Badge variant="secondary" className="shrink-0 text-[10px]">
                  renamed → {tool.enhanced_name}
                </Badge>
              )}
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
              <AiCostDisplay costCents={tool.cost_cents} size="sm" />
              <span className="opacity-30">·</span>
              <span>{tool.model}</span>
            </div>
          </div>

          <QualityScoreBadge
            score={tool.quality_score.total}
            badge={tool.quality_score.badge}
            size="sm"
          />

          {/* ── Expand toggle ── */}
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className={cn(
              "rounded p-1 text-muted-foreground transition-colors hover:text-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
            )}
            aria-label={expanded ? "Collapse details" : "Expand details"}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* ── Improvement badges (always visible) ── */}
        {tool.improvements && tool.improvements.length > 0 && (
          <div className="border-t border-border/50 px-4 py-2">
            <ImprovementsBadges
              improvements={tool.improvements}
              size="sm"
              maxVisible={4}
            />
          </div>
        )}

        {/* ── Expanded detail section ── */}
        {expanded && (
          <div className="border-t border-border/50 px-4 py-4 space-y-5">
            {/* Quality breakdown */}
            <QualityScoreBreakdown
              functionality={tool.quality_score.functionality}
              accuracy={tool.quality_score.accuracy}
              completeness={tool.quality_score.completeness}
              context={tool.quality_score.context}
              size="sm"
            />

            {/* Side-by-side comparison */}
            <OriginalVsEnhanced
              original={tool.original_description}
              enhanced={tool.enhanced_description}
              title="Description"
            />

            {/* Inline name edit */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <InlineEditField
                  value={editedName}
                  onChange={handleSaveName}
                  label="Tool Name"
                  rows={1}
                />
                <RevertFieldButton
                  onRevert={handleRevertName}
                  original={tool.name}
                  current={editedName}
                  size="sm"
                />
              </div>
            </div>

            {/* Inline description edit */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <InlineEditField
                  value={editedDesc}
                  onChange={handleSaveDescription}
                  label="Description"
                  rows={4}
                />
                <RevertFieldButton
                  onRevert={handleRevertDescription}
                  original={tool.original_description}
                  current={editedDesc}
                  size="sm"
                />
              </div>
            </div>

            {/* Improved parameters */}
            {tool.enhanced_parameters && tool.enhanced_parameters.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Enhanced Parameters
                </span>
                <div className="rounded-md border border-border/50 bg-muted/30 p-3">
                  <pre className="overflow-x-auto whitespace-pre-wrap text-[11px] leading-relaxed text-muted-foreground font-mono">
                    {JSON.stringify(tool.enhanced_parameters, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Return description */}
            {tool.enhanced_return_description && (
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Return Description
                </span>
                <p className="text-xs text-foreground/80">
                  {tool.enhanced_return_description}
                </p>
              </div>
            )}
          </div>
        )}

        {/* ── Footer actions ── */}
        <div className="flex items-center justify-end gap-2 border-t border-border/50 px-4 py-2.5">
          {isDirty && (
            <span className="mr-auto text-[10px] text-orange-600 dark:text-orange-400">
              Unsaved edits
            </span>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onReject}
            disabled={isPending}
            className="gap-1 text-muted-foreground hover:text-destructive"
          >
            <X className="h-3.5 w-3.5" />
            Reject
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={onAccept}
            disabled={isPending}
            className="gap-1"
          >
            <Check className="h-3.5 w-3.5" />
            Accept
          </Button>
        </div>
      </div>
    );
  },
);
AiReviewToolCard.displayName = "AiReviewToolCard";

export { AiReviewToolCard };
