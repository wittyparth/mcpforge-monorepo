"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface SecurityReportExportProps {
  serverId: string;
}

/**
 * Downloads the security report as a JSON file. Shows a loading state
 * while the report is being fetched from the API.
 */
export function SecurityReportExport({ serverId }: SecurityReportExportProps) {
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    try {
      const report = await api.servers.security.exportReport(serverId);
      const blob = new Blob([JSON.stringify(report, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `security-report-${serverId.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Silently fail — the button just resets
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleExport}
      disabled={loading}
    >
      {loading ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" />
          Exporting...
        </>
      ) : (
        <>
          <Download className="h-4 w-4" />
          Export Report
        </>
      )}
    </Button>
  );
}
