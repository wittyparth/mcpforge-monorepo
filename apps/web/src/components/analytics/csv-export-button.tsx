"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { AnalyticsRange } from "@/hooks/use-analytics";

interface CsvExportButtonProps {
  serverId: string;
  range: AnalyticsRange;
}

/**
 * Downloads the analytics CSV export for a given server and date range.
 * Follows the same pattern as SecurityReportExport.
 */
export function CsvExportButton({ serverId, range }: CsvExportButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    try {
      const url = api.servers.analytics.exportCsvUrl(serverId, range);
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error(`CSV fetch failed: ${res.status}`);
      const blob = await res.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `analytics-${serverId.slice(0, 8)}.csv`;
      a.click();
      URL.revokeObjectURL(downloadUrl);
    } catch {
      toast.error("Failed to export CSV");
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
          Export CSV
        </>
      )}
    </Button>
  );
}
