"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Shield,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Clock,
  CheckCircle2,
  History,
  RotateCw,
} from "lucide-react";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { SecurityScanButton } from "@/components/security/security-scan-button";
import { SecurityFindingsList } from "@/components/security/security-findings-list";
import { ScanProgress } from "@/components/security/scan-progress";
import { SecurityReportExport } from "@/components/security/security-report-export";
import {
  useLatestScan,
  useScanHistory,
  useAcknowledgmentList,
  useAcknowledgeFinding,
  useRemoveAcknowledgment,
  useScan,
} from "@/hooks/use-security";
import type { ScanResultResponse, AcknowledgeResponse } from "@/types/api";

function fmtDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtTime(raw: string): string {
  return new Date(raw).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function SecurityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: scanData, isLoading, isError, error, refetch } = useLatestScan(id);
  const { data: historyData, isLoading: historyLoading } = useScanHistory(id);
  const { data: acksData, isLoading: acksLoading } = useAcknowledgmentList(id);
  const acknowledgeFinding = useAcknowledgeFinding(id);
  const removeAck = useRemoveAcknowledgment(id);
  const triggerScan = useScan(id);

  const [tab, setTab] = useState("findings");
  const [scanStatus, setScanStatus] = useState<"idle" | "scanning" | "completed" | "failed">("idle");

  const handleScanComplete = (result: ScanResultResponse) => {
    if (result.scan_status === "completed") {
      setScanStatus("completed");
    } else if (result.scan_status === "failed") {
      setScanStatus("failed");
    }
    void refetch();
  };

  const handleAcknowledge = (findingId: string) => {
    acknowledgeFinding.mutate({ findingId });
  };

  const handleRemoveAck = (findingId: string) => {
    removeAck.mutate(findingId);
  };

  const acknowledgedIds = new Set<string>(
    (acksData?.items ?? []).map((a: AcknowledgeResponse) => a.finding_id),
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-5 w-32" />
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-9 w-36" />
            <Skeleton className="h-9 w-32" />
          </div>
        </div>
        <Skeleton className="h-10 w-96" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="space-y-6">
        <Link
          href={`/dashboard/servers/${id}`}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to server
        </Link>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <AlertTriangle className="h-12 w-12 text-destructive/50" />
            <h3 className="mt-4 text-lg font-medium">
              Failed to load security data
            </h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              {error instanceof Error
                ? error.message
                : "An unexpected error occurred"}
            </p>
            <Button
              variant="outline"
              className="mt-6"
              onClick={() => refetch()}
            >
              <RotateCw className="h-4 w-4" />
              Try again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Empty state: no scans have been run
  const hasNoScan = !scanData;

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/servers/${id}`}
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to server
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              Security Scanner
            </h1>
            <ShieldCheck className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-sm text-muted-foreground">
            Identify security issues in your MCP server tools and API
            configurations.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SecurityScanButton
            serverId={id}
            onScanComplete={handleScanComplete}
          />
          <SecurityReportExport serverId={id} />
        </div>
      </div>

      {/* Scan progress */}
      <ScanProgress
        status={scanStatus}
        criticalCount={scanData?.critical_count}
        highCount={scanData?.high_count}
        mediumCount={scanData?.medium_count}
        infoCount={scanData?.info_count}
      />

      {/* Empty state */}
      {hasNoScan && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Shield className="h-12 w-12 text-muted-foreground/30" />
            <h3 className="mt-4 text-lg font-medium">
              No security scans have been run yet
            </h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Run a security scan to analyze your MCP server tools for common
              vulnerabilities and misconfigurations.
            </p>
              <Button
                className="mt-6"
                onClick={() => {
                  setScanStatus("scanning");
                  triggerScan.mutate(undefined, {
                    onSuccess: () => {
                      setScanStatus("completed");
                      void refetch();
                    },
                    onError: () => {
                      setScanStatus("failed");
                    },
                  });
                }}
                disabled={triggerScan.isPending}
              >
                <Shield className="h-4 w-4" />
                {triggerScan.isPending ? "Scanning..." : "Run Scan"}
              </Button>
          </CardContent>
        </Card>
      )}

      {/* Scan results */}
      {scanData && (
        <>
          {/* Severity counts */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              {
                label: "Critical",
                count: scanData.critical_count,
                variant: "destructive" as const,
                icon: AlertTriangle,
              },
              {
                label: "High",
                count: scanData.high_count,
                variant: "outline" as const,
                icon: ShieldAlert,
              },
              {
                label: "Medium",
                count: scanData.medium_count,
                variant: "secondary" as const,
                icon: Clock,
              },
              {
                label: "Info",
                count: scanData.info_count,
                variant: "secondary" as const,
                icon: CheckCircle2,
              },
            ].map((stat) => (
              <Card key={stat.label}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {stat.label}
                  </CardTitle>
                  <stat.icon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-semibold">{stat.count}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Tabs */}
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="w-full sm:w-auto">
              <TabsTrigger value="findings">Findings</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
              <TabsTrigger value="acknowledged">Acknowledged</TabsTrigger>
            </TabsList>

            {/* Findings tab */}
            <TabsContent value="findings" className="space-y-4">
              <SecurityFindingsList
                findings={scanData.findings}
                acknowledgedIds={acknowledgedIds}
                onAcknowledge={handleAcknowledge}
              />
            </TabsContent>

            {/* History tab */}
            <TabsContent value="history" className="space-y-4">
              {historyLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full rounded-lg" />
                  ))}
                </div>
              ) : (historyData?.items ?? []).length === 0 ? (
                <EmptyState
                  icon={History}
                  title="No scan history"
                  description="Run a security scan to build up a history of results."
                />
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <div className="divide-y divide-border/50">
                      {historyData!.items.map((item: ScanResultResponse) => (
                        <div
                          key={item.id}
                          className="flex items-center justify-between px-4 py-3"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`flex h-2 w-2 rounded-full ${
                                item.scan_status === "completed"
                                  ? "bg-emerald-500"
                                  : item.scan_status === "failed"
                                    ? "bg-red-500"
                                    : "bg-amber-500"
                              }`}
                            />
                            <div className="flex flex-col">
                              <span className="text-sm font-medium">
                                {fmtTime(item.scanned_at)}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                {fmtDuration(item.scan_duration_ms)} &middot;{" "}
                                {item.findings.length} findings
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="secondary" className="text-[10px]">
                              {item.critical_count}C / {item.high_count}H /{" "}
                              {item.medium_count}M / {item.info_count}I
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Acknowledged tab */}
            <TabsContent value="acknowledged" className="space-y-4">
              {acksLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 2 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full rounded-lg" />
                  ))}
                </div>
              ) : (acksData?.items ?? []).length === 0 ? (
                <EmptyState
                  icon={CheckCircle2}
                  title="No acknowledged findings"
                  description="Acknowledge findings to track which issues have been reviewed."
                />
              ) : (
                <Card>
                  <CardContent className="p-0">
                    <div className="divide-y divide-border/50">
                      {acksData!.items.map((ack: AcknowledgeResponse) => (
                        <div
                          key={ack.finding_id}
                          className="flex items-center justify-between px-4 py-3"
                        >
                          <div className="flex items-center gap-3">
                            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                            <div className="flex flex-col">
                              <span className="text-sm font-medium">
                                {ack.finding_id}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                Acknowledged {fmtTime(ack.acknowledged_at)}
                              </span>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRemoveAck(ack.finding_id)}
                          >
                            Remove
                          </Button>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
