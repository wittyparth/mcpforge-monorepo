"use client";

import { useState } from "react";
import { Shield, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useScan } from "@/hooks/use-security";
import type { ScanResultResponse } from "@/types/api";

interface SecurityScanButtonProps {
  serverId: string;
  onScanComplete?: (result: ScanResultResponse) => void;
}

/**
 * Triggers a security scan on the given server.
 *
 * Displays three states: idle (show "Run Security Scan"), scanning
 * (show spinner + "Scanning..."), and a post-scan summary with
 * finding counts.
 */
export function SecurityScanButton({
  serverId,
  onScanComplete,
}: SecurityScanButtonProps) {
  const scan = useScan(serverId);
  const [lastResult, setLastResult] = useState<ScanResultResponse | null>(
    null,
  );

  const handleScan = () => {
    scan.mutate(undefined, {
      onSuccess: (data: ScanResultResponse) => {
        setLastResult(data);
        onScanComplete?.(data);
      },
      onError: () => {
        toast.error("Failed to start security scan");
      },
    });
  };

  const isScanning = scan.isPending;

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <Button
        size="sm"
        onClick={handleScan}
        disabled={isScanning}
      >
        {isScanning ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Scanning...
          </>
        ) : (
          <>
            <Shield className="h-4 w-4" />
            Run Security Scan
          </>
        )}
      </Button>
      {lastResult && !isScanning && (
        <span className="text-xs text-muted-foreground">
          {lastResult.critical_count} critical, {lastResult.high_count} high,{" "}
          {lastResult.medium_count} medium, {lastResult.info_count} info
        </span>
      )}
    </div>
  );
}
