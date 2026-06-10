"use client";

import { ShieldAlert } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import { SecurityFindingCard } from "@/components/security/security-finding-card";
import type { Finding, FindingSeverity } from "@/types/api";

const SEVERITY_ORDER: FindingSeverity[] = [
  "critical",
  "high",
  "medium",
  "info",
];

const SEVERITY_LABELS: Record<FindingSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  info: "Info",
};

interface SecurityFindingsListProps {
  findings: Finding[];
  acknowledgedIds?: Set<string>;
  onAcknowledge?: (findingId: string) => void;
}

/**
 * Displays a list of findings grouped by severity (CRITICAL first,
 * then HIGH, MEDIUM, INFO). Each group shows a section header with
 * a count badge and uses SecurityFindingCard for individual items.
 */
export function SecurityFindingsList({
  findings,
  acknowledgedIds = new Set(),
  onAcknowledge,
}: SecurityFindingsListProps) {
  if (findings.length === 0) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="No findings found"
        description="Run a scan to check for security issues."
      />
    );
  }

  const grouped = SEVERITY_ORDER.map((severity) => ({
    severity,
    items: findings.filter((f) => f.severity === severity),
  })).filter((group) => group.items.length > 0);

  return (
    <div className="space-y-4">
      {grouped.map((group) => (
        <Card key={group.severity}>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-sm font-semibold">
              {SEVERITY_LABELS[group.severity]}
            </CardTitle>
            <Badge variant="secondary" className="text-[10px]">
              {group.items.length}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            {group.items.map((finding) => (
              <SecurityFindingCard
                key={finding.id}
                finding={finding}
                acknowledged={acknowledgedIds.has(finding.id)}
                onAcknowledge={onAcknowledge}
              />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
