"use client";

import * as React from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Loader2, AlertTriangle, Wifi, WifiOff, RefreshCw } from "lucide-react";

import type { CallLogEntry } from "@/hooks/use-playground";
import { usePlayground } from "@/hooks/use-playground";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

import { ToolBrowser } from "./tool-browser";
import { ToolForm } from "./tool-form";
import { ResponseViewer } from "./response-viewer";
import { CallLog } from "./call-log";
import { ShareTestButton } from "./share-test-button";

export interface PlaygroundPageProps {
  /** Server ID (UUID) */
  serverId: string;
  /** Server slug for WebSocket connection and URL generation */
  serverSlug: string;
  /** Server display name */
  serverName: string;
  /** JWT access token for WebSocket auth (read server-side from httpOnly cookie) */
  accessToken: string | null;
}

/**
 * Main 4-panel playground layout.
 *
 * Layout:
 * ┌─────────┬──────────────────┬──────────┐
 * │  Tool   │   Tool Form      │ Call Log │
 * │ Browser │                  │          │
 * │         ├──────────────────┤          │
 * │         │ Response Viewer  │          │
 * └─────────┴──────────────────┴──────────┘
 *
 * Uses react-resizable-panels for draggable panel sizing.
 * Connects to the WebSocket playground backend via usePlayground hook.
 */
function PlaygroundPage({
  serverId: _serverId,
  serverSlug,
  serverName,
  accessToken,
}: PlaygroundPageProps) {
  const {
    tools,
    selectedTool,
    response,
    callLog,
    isConnected,
    reconnectAttempt,
    error,
    selectTool,
    callTool,
    clearLog,
    clearResponse,
    connect,
  } = usePlayground(serverSlug, accessToken ?? undefined);

  const [isCalling, setIsCalling] = React.useState(false);
  const [latencyMs, setLatencyMs] = React.useState<number | null>(null);
  const [lastCallToolName, setLastCallToolName] = React.useState<string | null>(
    null,
  );

  // Track parameters for share button
  const [lastCallParams, setLastCallParams] = React.useState<
    Record<string, unknown>
  >({});

  // Handle URL params to auto-select tool on load and on popstate
  React.useEffect(() => {
    if (tools.length === 0) return;

    const selectToolFromUrl = () => {
      const params = new URLSearchParams(window.location.search);
      const toolParam = params.get("tool");
      if (toolParam) {
        const tool = tools.find((t) => t.name === toolParam);
        if (tool) {
          selectTool(tool);
        }
      }
    };

    selectToolFromUrl();

    window.addEventListener("popstate", selectToolFromUrl);
    return () => window.removeEventListener("popstate", selectToolFromUrl);
  }, [tools, selectTool]);

  const handleCallTool = React.useCallback(
    async (toolName: string, args: Record<string, unknown>) => {
      console.log("[DBG] handleCallTool called", { toolName, args });
      setIsCalling(true);
      setLatencyMs(null);
      setLastCallToolName(toolName);
      setLastCallParams(args);

      const start = performance.now();
      try {
        await callTool(toolName, args);
        console.log("[DBG] callTool completed successfully");
      } catch (err) {
        console.log("[DBG] callTool threw", { error: String(err) });
      } finally {
        setLatencyMs(performance.now() - start);
        setIsCalling(false);
        console.log("[DBG] handleCallTool finally: isCalling set to false");
      }
    },
    [callTool],
  );

  const handleClear = React.useCallback(() => {
    clearResponse();
    setLatencyMs(null);
    setLastCallToolName(null);
    setLastCallParams({});
  }, [clearResponse]);

  const handleReplayEntry = React.useCallback(
    (entry: CallLogEntry) => {
      const tool = tools.find((t) => t.name === entry.toolName);
      if (tool) {
        selectTool(tool);
      }
    },
    [tools, selectTool],
  );

  // Has there been at least one successful call?
  const hasSuccessfulCall = React.useMemo(
    () => callLog.some((e) => !e.response?.isError),
    [callLog],
  );

  // Loading skeleton
  if (tools.length === 0 && isConnected && !error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            Loading tools…
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-border/50 px-4 py-2">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold">{serverName}</h1>
          <div className="flex items-center gap-1.5">
            {isConnected ? (
              <Wifi className="h-3 w-3 text-emerald-500" />
            ) : (
              <WifiOff className="h-3 w-3 text-muted-foreground" />
            )}
            <span className="text-[11px] text-muted-foreground">
              {isConnected
                ? "Connected"
                : reconnectAttempt > 0
                  ? `Reconnecting (${reconnectAttempt})…`
                  : "Disconnected"}
            </span>
          </div>
        </div>
        <ShareTestButton
          serverSlug={serverSlug}
          toolName={lastCallToolName}
          parameters={lastCallParams}
          enabled={hasSuccessfulCall && !isCalling}
        />
      </div>

      {/* Connection error banner */}
      {error && (
        <Alert variant="destructive" className="m-2 rounded-lg">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Connection Error</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={connect}
              className="ml-4 shrink-0"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* 4-panel resizable layout */}
      <div className="flex-1 overflow-hidden">
        <PanelGroup direction="horizontal" className="h-full">
          {/* Panel 1: Tool Browser (left) */}
          <Panel defaultSize={20} minSize={15} maxSize={35}>
            <ToolBrowser
              tools={tools}
              selectedTool={selectedTool}
              onSelectTool={selectTool}
              isConnected={isConnected}
              error={null}
            />
          </Panel>

          <PanelResizeHandle className="w-px bg-border/50 transition-colors hover:bg-border" />

          {/* Center: vertical split (Form + Response) */}
          <Panel defaultSize={55} minSize={30}>
            <PanelGroup direction="vertical" className="h-full">
            {/* Panel 2: Tool Form (center-top) */}
            <Panel defaultSize={50} minSize={30} maxSize={70}>
              <ToolForm
                tool={selectedTool}
                isCalling={isCalling}
                onCallTool={handleCallTool}
                onClear={handleClear}
              />
            </Panel>

            <PanelResizeHandle className="h-px bg-border/50 transition-colors hover:bg-border" />

            {/* Panel 3: Response Viewer (center-bottom) */}
            <Panel defaultSize={50} minSize={30} maxSize={70}>
              <ResponseViewer
                response={response}
                latencyMs={latencyMs}
                toolName={lastCallToolName}
              />
            </Panel>
          </PanelGroup>
          </Panel>

          <PanelResizeHandle className="w-px bg-border/50 transition-colors hover:bg-border" />

          {/* Panel 4: Call Log (right) */}
          <Panel defaultSize={25} minSize={20} maxSize={40}>
            <CallLog
              entries={callLog}
              onClear={clearLog}
              onReplayEntry={handleReplayEntry}
            />
          </Panel>
        </PanelGroup>
      </div>
    </div>
  );
}

export { PlaygroundPage };
