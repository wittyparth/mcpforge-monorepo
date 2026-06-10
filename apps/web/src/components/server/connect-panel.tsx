"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { CopyToClipboard } from "@/components/shared/copy-to-clipboard";
import { useConnectPanel } from "@/hooks/use-gateway";

interface ConnectPanelProps {
  serverSlug: string;
  serverId: string;
}

function ConfigBlock({ title, json }: { title: string; json: Record<string, unknown> }) {
  const formatted = JSON.stringify(json, null, 2);
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{title}</span>
        <CopyToClipboard value={formatted} label={`${title} config`} />
      </div>
      <pre className="overflow-x-auto rounded-lg border bg-muted/50 p-4 font-mono text-xs leading-relaxed">
        {formatted}
      </pre>
    </div>
  );
}

export function ConnectPanel({ serverId }: ConnectPanelProps) {
  const { data, isLoading, isError, error } = useConnectPanel(serverId);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <p className="text-sm text-muted-foreground">
        {error instanceof Error ? error.message : "Failed to load connect panel"}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Gateway URL */}
      <div className="space-y-2">
        <span className="text-sm font-medium">Gateway URL</span>
        <div className="flex items-center gap-2">
          <code className="flex-1 truncate rounded-lg border bg-muted/50 px-3 py-2 font-mono text-xs">
            {data.gateway_url}
          </code>
          <CopyToClipboard value={data.gateway_url} label="Gateway URL" />
        </div>
      </div>

      {/* Transport modes */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Transport:</span>
        {data.transport_modes.map((mode: string) => (
          <Badge key={mode} variant="secondary" className="text-xs">
            {mode.toUpperCase()}
          </Badge>
        ))}
      </div>

      {/* Client configs */}
      <div className="grid gap-6 sm:grid-cols-2">
        <ConfigBlock title="Claude Desktop" json={data.claude_desktop_config} />
        <ConfigBlock title="Cursor" json={data.cursor_config} />
      </div>
    </div>
  );
}
