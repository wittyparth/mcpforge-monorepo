"use client";

import * as React from "react";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Copy,
  ArrowDownToLine,
  AlertTriangle,
} from "lucide-react";

import type { CallResponse } from "@/hooks/use-playground";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { JsonViewer } from "./json-viewer";

export interface ResponseViewerProps {
  /** The latest tool call response */
  response: CallResponse | null;
  /** Latency in milliseconds for the last call */
  latencyMs: number | null;
  /** Name of the tool that was called */
  toolName: string | null;
}

interface ResponseMeta {
  latencyMs: number | null;
  status: "success" | "error" | null;
  responseSize: number;
  contentCount: number;
}

/**
 * Center-bottom panel: JSON response viewer with tabs.
 *
 * Shows Formatted (Monaco), Raw (Monaco), and Meta (timing, size) tabs.
 * Displays error messages with actionable context.
 */
function ResponseViewer({ response, latencyMs, toolName }: ResponseViewerProps) {
  const meta = React.useMemo((): ResponseMeta => {
    if (!response) {
      return { latencyMs: null, status: null, responseSize: 0, contentCount: 0 };
    }

    const rawJson = JSON.stringify(response, null, 2);
    const bytes = new TextEncoder().encode(rawJson).length;

    // Response carries _meta.elapsed_ms; use as fallback for React batching edge cases
    const responseLatency =
      (
        (response as unknown as Record<string, unknown>)._meta as
          | Record<string, unknown>
          | undefined
      )?.elapsed_ms as number | undefined;
    const effectiveLatency = responseLatency ?? latencyMs;

    return {
      latencyMs: effectiveLatency,
      status: response.isError ? "error" : "success",
      responseSize: bytes,
      contentCount: response.content?.length ?? 0,
    };
  }, [response, latencyMs]);

  const formattedJson = React.useMemo(() => {
    if (!response) return "";
    try {
      return JSON.stringify(response, null, 2);
    } catch {
      return String(response);
    }
  }, [response]);

  const rawJson = React.useMemo(() => {
    if (!response) return "";
    return JSON.stringify(response);
  }, [response]);

  const plainText = React.useMemo(() => {
    if (!response?.content) return "";
    return response.content
      .filter((c) => c.type === "text" && c.text)
      .map((c) => c.text)
      .join("\n\n");
  }, [response]);

  const handleCopy = React.useCallback(() => {
    navigator.clipboard.writeText(formattedJson).then(
      () => toast.success("Response copied"),
      () => toast.error("Failed to copy"),
    );
  }, [formattedJson]);

  const handleDownload = React.useCallback(() => {
    const blob = new Blob([formattedJson], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tool-response-${toolName ?? "unknown"}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [formattedJson, toolName]);

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatLatency = (ms: number): string => {
    if (ms < 1000) return `${Math.round(ms)} ms`;
    return `${(ms / 1000).toFixed(2)} s`;
  };

  // Empty state
  if (!response) {
    return (
      <Card className="flex h-full items-center justify-center border-0 rounded-none">
        <div className="flex flex-col items-center gap-2 text-center text-sm text-muted-foreground">
          <ArrowDownToLine className="h-5 w-5" />
          <span>Response will appear here after a tool call</span>
        </div>
      </Card>
    );
  }

  return (
    <Card className="flex h-full flex-col overflow-hidden border-0 rounded-none">
      <CardHeader className="p-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            {meta.status === "error" ? (
              <XCircle className="h-3.5 w-3.5 text-destructive" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
            )}
            Response
          </CardTitle>
          <div className="flex items-center gap-1.5">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleCopy}
              aria-label="Copy response"
            >
              <Copy className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleDownload}
              aria-label="Download response as JSON"
            >
              <ArrowDownToLine className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Quick meta bar */}
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          {meta.status && (
            <Badge
              variant={meta.status === "error" ? "destructive" : "secondary"}
              className="text-[10px]"
            >
              {meta.status === "error" ? "Error" : "200 OK"}
            </Badge>
          )}
          {meta.latencyMs !== null && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatLatency(meta.latencyMs)}
            </span>
          )}
          <span>{formatBytes(meta.responseSize)}</span>
          <span>{meta.contentCount} content block(s)</span>
        </div>
      </CardHeader>

      <Separator />

      <CardContent className="flex-1 overflow-hidden p-0">
        <Tabs defaultValue="formatted" className="flex h-full flex-col">
          <div className="border-b border-border/50 px-3 pt-2">
            <TabsList className="h-8">
              <TabsTrigger value="formatted" className="text-xs">
                Formatted
              </TabsTrigger>
              <TabsTrigger value="raw" className="text-xs">
                Raw
              </TabsTrigger>
              <TabsTrigger value="text" className="text-xs">
                Text
              </TabsTrigger>
              <TabsTrigger value="meta" className="text-xs">
                Meta
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent
            value="formatted"
            className="m-0 flex-1 flex flex-col overflow-hidden"
          >
            {response.isError && (
              <div className="mx-3 mt-3 flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive shrink-0">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div>
                  <p className="font-medium">Tool call returned an error</p>
                  <p className="mt-1 text-destructive/80">{plainText}</p>
                </div>
              </div>
            )}
            <div className="flex-1 min-h-0">
              <JsonViewer value={formattedJson} height="100%" />
            </div>
          </TabsContent>

          <TabsContent value="raw" className="m-0 flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 min-h-0">
              <JsonViewer value={rawJson} height="100%" />
            </div>
          </TabsContent>

          <TabsContent value="text" className="m-0 flex-1 overflow-hidden">
            <pre className="h-full overflow-auto p-4 font-mono text-xs text-foreground whitespace-pre-wrap">
              {plainText || "(no text content)"}
            </pre>
          </TabsContent>

          <TabsContent value="meta" className="m-0 flex-1 overflow-auto p-4">
            <div className="space-y-4">
              <div className="grid gap-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Tool Name</span>
                  <span className="font-mono font-medium">{toolName ?? "—"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Status</span>
                  <Badge
                    variant={meta.status === "error" ? "destructive" : "secondary"}
                  >
                    {meta.status === "error" ? "Error" : "Success"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Latency</span>
                  <span className="font-mono">
                    {meta.latencyMs !== null ? formatLatency(meta.latencyMs) : "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Response Size</span>
                  <span className="font-mono">{formatBytes(meta.responseSize)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Content Blocks</span>
                  <span className="font-mono">{meta.contentCount}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Request ID</span>
                  <span className="font-mono text-[10px]">
                    {response.request_id ?? "—"}
                  </span>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

export { ResponseViewer };
