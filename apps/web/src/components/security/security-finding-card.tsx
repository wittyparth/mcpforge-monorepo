"use client";

import {
  AlertTriangle,
  ExternalLink,
  CheckCircle2,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/security/severity-badge";
import { cn } from "@/lib/utils";
import type { Finding, FindingSeverity } from "@/types/api";

/** Card background/border classes keyed by severity. */
const severityCardStyles: Record<FindingSeverity, string> = {
  critical:
    "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950",
  high:
    "border-orange-200 bg-orange-50 dark:border-orange-800 dark:bg-orange-950",
  medium:
    "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950",
  info: "border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950",
};

interface SecurityFindingCardProps {
  finding: Finding;
  onAcknowledge?: (findingId: string) => void;
  acknowledged?: boolean;
}

/**
 * A card showing a single security finding with severity badge,
 * title, description, affected tools, remediation, and an
 * acknowledge button (disabled for CRITICAL findings).
 */
export function SecurityFindingCard({
  finding,
  onAcknowledge,
  acknowledged = false,
}: SecurityFindingCardProps) {
  const isCritical = finding.severity === "critical";

  return (
    <Card
      className={cn(
        "transition-colors",
        isCritical && severityCardStyles.critical,
      )}
    >
      <CardHeader className="flex flex-row items-start justify-between gap-3 pb-3">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            {isCritical && (
              <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
            )}
          </div>
          <CardTitle className="text-sm font-medium leading-snug">
            {finding.title}
          </CardTitle>
        </div>
        {!isCritical && onAcknowledge && (
          <Button
            variant={acknowledged ? "outline" : "ghost"}
            size="sm"
            onClick={() => onAcknowledge(finding.id)}
            disabled={acknowledged}
            className="shrink-0"
          >
            {acknowledged ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                Acknowledged
              </>
            ) : (
              "Acknowledge"
            )}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <p className="text-sm text-muted-foreground">{finding.description}</p>

        {finding.affected_tools.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Affected Tools
            </span>
            <div className="flex flex-wrap gap-1">
              {finding.affected_tools.map((tool) => (
                <Badge key={tool} variant="secondary" className="text-[10px]">
                  {tool}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {finding.remediation && (
          <div className="space-y-1">
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Remediation
            </span>
            <p className="text-sm text-muted-foreground">
              {finding.remediation}
            </p>
          </div>
        )}

        {finding.references.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {finding.references.map((ref) => (
              <a
                key={ref}
                href={ref}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <ExternalLink className="h-3 w-3" />
                {new URL(ref).hostname}
              </a>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
